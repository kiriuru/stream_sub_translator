from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import socket
from typing import Any
from urllib.parse import urlparse

from backend.core.cache_manager import CacheManager
from backend.models import TranslationDiagnostics, TranslationItem
from backend.translation.base import (
    PROVIDER_GROUP_EXPERIMENTAL,
    PROVIDER_GROUP_STABLE,
    BaseTranslationProvider,
    SUPPORTED_TRANSLATION_PROVIDERS,
    TranslationProviderError,
    TranslationProviderInfo,
)
from backend.translation.providers.azure import AzureTranslatorProvider
from backend.translation.providers.deepl import DeepLProvider
from backend.translation.providers.experimental_google_web import FreeWebTranslateProvider, GoogleWebProvider
from backend.translation.providers.google_gas import GoogleGasUrlProvider
from backend.translation.providers.google_v2 import GoogleTranslateV2Provider
from backend.translation.providers.google_v3 import GoogleCloudTranslationV3Provider
from backend.translation.providers.libretranslate import LibreTranslateProvider
from backend.translation.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.translation.providers.public_mirrors import PublicLibreTranslateMirrorProvider
from backend.translation.registry import build_default_provider_registry


logger = logging.getLogger(__name__)

_DEFAULT_PROVIDER_NAME = "google_translate_v2"
_CANONICAL_TRANSLATION_SLOTS = tuple(f"translation_{index}" for index in range(1, 6))


@dataclass
class TranslationBatch:
    provider: str
    source_lang: str
    target_languages: list[str]
    items: list[TranslationItem]
    provider_group: str
    experimental: bool = False
    local_provider: bool = False
    used_default_prompt: bool = False
    status_message: str | None = None


@dataclass
class PreparedTranslationLine:
    slot_id: str
    target_lang: str
    provider_name: str
    provider: BaseTranslationProvider | None
    provider_settings: dict[str, str]
    provider_group: str
    experimental: bool = False
    local_provider: bool = False
    label: str | None = None


@dataclass
class PreparedTranslationRequest:
    provider_name: str
    provider: BaseTranslationProvider | None
    provider_settings: dict[str, str]
    target_languages: list[str]
    provider_group: str
    experimental: bool = False
    local_provider: bool = False
    lines: list[PreparedTranslationLine] = field(default_factory=list)


class TranslationEngine:
    def __init__(self, cache_manager: CacheManager) -> None:
        self.cache_manager = cache_manager
        self.providers: dict[str, BaseTranslationProvider] = build_default_provider_registry()
        self._last_settings_signature: tuple[tuple[str, str], ...] | None = None

    def _supported_provider_name(self, raw_provider_name: Any) -> str:
        provider_name = str(raw_provider_name or _DEFAULT_PROVIDER_NAME).strip()
        if provider_name not in SUPPORTED_TRANSLATION_PROVIDERS:
            return _DEFAULT_PROVIDER_NAME
        return provider_name

    def _normalized_provider_settings_map(self, translation_config: dict[str, Any]) -> dict[str, dict[str, str]]:
        provider_settings_map = translation_config.get("provider_settings", {})
        if not isinstance(provider_settings_map, dict):
            return {}
        normalized: dict[str, dict[str, str]] = {}
        for provider_name, provider_settings in provider_settings_map.items():
            if not isinstance(provider_settings, dict):
                continue
            normalized[str(provider_name)] = {str(key): str(value) for key, value in provider_settings.items()}
        return normalized

    def _normalize_target_languages(self, target_languages: list[str]) -> list[str]:
        clean_target_languages = [
            str(item).strip().lower()
            for item in target_languages
            if str(item).strip()
        ]
        return list(dict.fromkeys(clean_target_languages))

    def _normalized_configured_lines(self, translation_config: dict[str, Any]) -> list[dict[str, Any]]:
        default_provider = self._supported_provider_name(translation_config.get("provider", _DEFAULT_PROVIDER_NAME))
        raw_lines = translation_config.get("lines", [])
        normalized_lines: list[dict[str, Any]] = []

        if isinstance(raw_lines, list) and raw_lines:
            for index, raw_line in enumerate(raw_lines):
                if not isinstance(raw_line, dict):
                    continue
                slot_id = str(raw_line.get("slot_id") or "").strip().lower()
                if slot_id not in _CANONICAL_TRANSLATION_SLOTS:
                    slot_id = _CANONICAL_TRANSLATION_SLOTS[index] if index < len(_CANONICAL_TRANSLATION_SLOTS) else ""
                target_lang = str(raw_line.get("target_lang") or "").strip().lower()
                provider_name = self._supported_provider_name(raw_line.get("provider", default_provider))
                if not slot_id or not target_lang:
                    continue
                normalized_lines.append(
                    {
                        "slot_id": slot_id,
                        "enabled": bool(raw_line.get("enabled", True)),
                        "target_lang": target_lang,
                        "provider": provider_name,
                        "label": str(raw_line.get("label") or "").strip() or target_lang.upper(),
                    }
                )

        if not normalized_lines:
            legacy_targets = self._normalize_target_languages(translation_config.get("target_languages", []))
            if not legacy_targets:
                legacy_targets = ["en"]
            normalized_lines = [
                {
                    "slot_id": _CANONICAL_TRANSLATION_SLOTS[index],
                    "enabled": True,
                    "target_lang": target_lang,
                    "provider": default_provider,
                    "label": target_lang.upper(),
                }
                for index, target_lang in enumerate(legacy_targets[: len(_CANONICAL_TRANSLATION_SLOTS)])
            ]

        return normalized_lines[: len(_CANONICAL_TRANSLATION_SLOTS)]

    def _required_fields_for_provider(self, provider_name: str) -> list[str]:
        if provider_name == "google_translate_v2":
            return ["api_key"]
        if provider_name == "google_cloud_translation_v3":
            return ["project_id", "access_token"]
        if provider_name == "google_gas_url":
            return ["gas_url"]
        if provider_name == "azure_translator":
            return ["api_key", "endpoint"]
        if provider_name == "deepl":
            return ["api_key"]
        if provider_name in {"openai", "openrouter"}:
            return ["api_key", "model"]
        if provider_name in {"lm_studio", "ollama"}:
            return ["base_url", "model"]
        return []

    def _provider_endpoint_for_summary(self, provider_name: str, provider_settings: dict[str, str]) -> str | None:
        if provider_name == "google_translate_v2":
            return "https://translation.googleapis.com/language/translate/v2"
        if provider_name == "google_cloud_translation_v3":
            project_id = provider_settings.get("project_id", "").strip()
            location = provider_settings.get("location", "").strip() or "global"
            if not project_id:
                return None
            return f"https://translation.googleapis.com/v3/projects/{project_id}/locations/{location}:translateText"
        if provider_name == "google_gas_url":
            return provider_settings.get("gas_url", "").strip() or None
        if provider_name == "azure_translator":
            return provider_settings.get("endpoint", "").strip() or "https://api.cognitive.microsofttranslator.com"
        if provider_name in {"deepl", "libretranslate", "public_libretranslate_mirror"}:
            return provider_settings.get("api_url", "").strip() or None
        if provider_name in {"openai", "openrouter", "lm_studio", "ollama"}:
            return provider_settings.get("base_url", "").strip() or None
        return None

    def _check_local_endpoint(self, endpoint: str | None) -> tuple[bool, str | None]:
        if not endpoint:
            return False, "Local provider endpoint is missing."
        try:
            parsed = urlparse(endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == "https" else 80
            with socket.create_connection((host, port), timeout=0.35):
                return True, None
        except Exception as exc:
            return False, f"Local provider endpoint is not reachable: {exc}"

    def summarize_readiness(self, translation_config: dict[str, Any]) -> TranslationDiagnostics:
        if not isinstance(translation_config, dict) or not translation_config.get("enabled", False):
            return TranslationDiagnostics(
                enabled=False,
                status="disabled",
                summary="Translation disabled.",
            )

        configured_lines = self._normalized_configured_lines(translation_config)
        enabled_lines = [line for line in configured_lines if line.get("enabled", True)]
        provider_settings_map = self._normalized_provider_settings_map(translation_config)
        missing_by_line: dict[str, list[str]] = {}
        missing_fields: list[str] = []
        line_providers: list[str] = []
        line_target_languages: list[str] = []
        line_missing_fields: dict[str, list[str]] = {}
        unreachable_local_providers: dict[str, str] = {}
        used_default_prompt = False
        any_experimental = False
        any_local = False
        all_ready = True
        any_configured = bool(enabled_lines)

        if not enabled_lines:
            return TranslationDiagnostics(
                enabled=True,
                provider=self._supported_provider_name(translation_config.get("provider", _DEFAULT_PROVIDER_NAME)),
                configured=False,
                ready=False,
                degraded=True,
                status="partial",
                summary="Translation enabled, but no translation lines are configured.",
                reason="Enable at least one translation line.",
                target_languages=[],
                line_count=len(configured_lines),
                enabled_line_count=0,
                line_providers=[],
                line_target_languages=[],
                line_missing_fields={},
            )

        diagnostics_by_provider: list[dict[str, Any]] = []
        for line in enabled_lines:
            provider_name = self._supported_provider_name(line["provider"])
            provider = self.providers.get(provider_name)
            provider_settings = provider_settings_map.get(provider_name, {})
            normalized_settings = {str(key): str(value).strip() for key, value in provider_settings.items()}
            line_providers.append(provider_name)
            line_target_languages.append(str(line["target_lang"]))

            if provider is None:
                missing = ["provider"]
                missing_by_line[line["slot_id"]] = missing
                line_missing_fields[line["slot_id"]] = missing
                missing_fields.extend(missing)
                all_ready = False
                continue

            diagnostics = provider.diagnostics(normalized_settings)
            diagnostics_by_provider.append(diagnostics)
            used_default_prompt = used_default_prompt or bool(diagnostics.get("used_default_prompt", False))
            any_experimental = any_experimental or bool(provider.info.experimental)
            any_local = any_local or bool(provider.info.local_provider)

            missing = [
                field_name
                for field_name in self._required_fields_for_provider(provider_name)
                if not normalized_settings.get(field_name, "").strip()
            ]
            if missing:
                missing_by_line[line["slot_id"]] = missing
                line_missing_fields[line["slot_id"]] = missing
                missing_fields.extend(missing)
                all_ready = False
                continue

            if provider.info.local_provider:
                endpoint = self._provider_endpoint_for_summary(provider_name, normalized_settings)
                reachable, reason = self._check_local_endpoint(endpoint)
                if not reachable and reason:
                    unreachable_local_providers[line["slot_id"]] = reason
                    all_ready = False

        primary_provider = line_providers[0] if line_providers and len(set(line_providers)) == 1 else "mixed"
        primary_group = (
            diagnostics_by_provider[0].get("provider_group")
            if diagnostics_by_provider and len({item.get("provider_group") for item in diagnostics_by_provider}) == 1
            else "mixed"
        )
        endpoint = None
        if line_providers:
            first_provider = line_providers[0]
            endpoint = self._provider_endpoint_for_summary(first_provider, provider_settings_map.get(first_provider, {}))

        if missing_by_line:
            summary = (
                f"Translation providers are partially configured across {len(enabled_lines)} enabled line(s)."
                if len(set(line_providers)) > 1
                else f"Translation provider '{primary_provider}' is partially configured."
            )
            return TranslationDiagnostics(
                enabled=True,
                provider=primary_provider,
                provider_group=str(primary_group),
                experimental=any_experimental,
                local_provider=any_local,
                configured=any_configured,
                ready=False,
                degraded=True,
                status="partial",
                summary=summary,
                reason="Missing required settings on one or more translation lines.",
                missing_fields=list(dict.fromkeys(missing_fields)),
                target_languages=line_target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=used_default_prompt,
                line_count=len(configured_lines),
                enabled_line_count=len(enabled_lines),
                line_providers=line_providers,
                line_target_languages=line_target_languages,
                line_missing_fields=line_missing_fields,
            )

        if unreachable_local_providers:
            return TranslationDiagnostics(
                enabled=True,
                provider=primary_provider,
                provider_group=str(primary_group),
                experimental=any_experimental,
                local_provider=any_local,
                configured=True,
                ready=False,
                degraded=True,
                status="degraded",
                summary="One or more local translation providers are configured but unreachable.",
                reason="; ".join(
                    f"{slot_id}: {reason}"
                    for slot_id, reason in unreachable_local_providers.items()
                ),
                missing_fields=[],
                target_languages=line_target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=used_default_prompt,
                line_count=len(configured_lines),
                enabled_line_count=len(enabled_lines),
                line_providers=line_providers,
                line_target_languages=line_target_languages,
                line_missing_fields={},
            )

        if any_experimental and not any_local:
            return TranslationDiagnostics(
                enabled=True,
                provider=primary_provider,
                provider_group=str(primary_group),
                experimental=True,
                local_provider=any_local,
                configured=True,
                ready=True,
                degraded=True,
                status="experimental",
                summary="Experimental translation provider configuration is active on one or more lines.",
                reason="Experimental providers may fail or change behavior without notice.",
                missing_fields=[],
                target_languages=line_target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=used_default_prompt,
                line_count=len(configured_lines),
                enabled_line_count=len(enabled_lines),
                line_providers=line_providers,
                line_target_languages=line_target_languages,
                line_missing_fields={},
            )

        return TranslationDiagnostics(
            enabled=True,
            provider=primary_provider,
            provider_group=str(primary_group),
            experimental=any_experimental,
            local_provider=any_local,
            configured=True,
            ready=all_ready,
            degraded=False,
            status="ready",
            summary=(
                f"Translation provider '{primary_provider}' is configured."
                if primary_provider != "mixed"
                else f"Mixed-provider translation is configured across {len(enabled_lines)} enabled line(s)."
            ),
            reason=None,
            missing_fields=[],
            target_languages=line_target_languages,
            provider_endpoint=endpoint,
            uses_default_prompt=used_default_prompt,
            line_count=len(configured_lines),
            enabled_line_count=len(enabled_lines),
            line_providers=line_providers,
            line_target_languages=line_target_languages,
            line_missing_fields={},
        )

    def _build_settings_signature(self, translation_config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
        if not isinstance(translation_config, dict):
            return ()
        signature_payload: dict[str, str] = {
            "enabled": str(bool(translation_config.get("enabled", False))),
            "provider": self._supported_provider_name(translation_config.get("provider", "")),
        }
        for index, line in enumerate(self._normalized_configured_lines(translation_config)):
            signature_payload[f"line:{index}:slot_id"] = str(line.get("slot_id", ""))
            signature_payload[f"line:{index}:enabled"] = str(bool(line.get("enabled", True)))
            signature_payload[f"line:{index}:target_lang"] = str(line.get("target_lang", ""))
            signature_payload[f"line:{index}:provider"] = str(line.get("provider", ""))
            signature_payload[f"line:{index}:label"] = str(line.get("label", ""))
        provider_settings_map = self._normalized_provider_settings_map(translation_config)
        for provider_name, provider_settings in sorted(provider_settings_map.items()):
            for key, value in sorted(provider_settings.items()):
                signature_payload[f"provider_setting:{provider_name}:{key}"] = str(value)
        return tuple(sorted(signature_payload.items()))

    def apply_live_settings(self, translation_config: dict[str, Any]) -> None:
        new_signature = self._build_settings_signature(translation_config)
        if self._last_settings_signature is not None and new_signature != self._last_settings_signature:
            self.cache_manager.clear_translation_cache()
        self._last_settings_signature = new_signature

    def prepare_request(self, translation_config: dict[str, Any]) -> PreparedTranslationRequest:
        provider_settings_map = self._normalized_provider_settings_map(translation_config)
        prepared_lines: list[PreparedTranslationLine] = []

        for line in self._normalized_configured_lines(translation_config):
            if not line.get("enabled", True):
                continue
            provider_name = self._supported_provider_name(line.get("provider", _DEFAULT_PROVIDER_NAME))
            provider = self.providers.get(provider_name)
            provider_settings = provider_settings_map.get(provider_name, {})
            provider_group = provider.info.group if provider is not None else PROVIDER_GROUP_EXPERIMENTAL
            experimental = bool(provider.info.experimental) if provider is not None else True
            local_provider = bool(provider.info.local_provider) if provider is not None else False
            prepared_lines.append(
                PreparedTranslationLine(
                    slot_id=str(line["slot_id"]),
                    target_lang=str(line["target_lang"]),
                    provider_name=provider_name,
                    provider=provider,
                    provider_settings={str(key): str(value) for key, value in provider_settings.items()},
                    provider_group=provider_group,
                    experimental=experimental,
                    local_provider=local_provider,
                    label=str(line.get("label") or "").strip() or str(line["target_lang"]).upper(),
                )
            )

        provider_names = [line.provider_name for line in prepared_lines]
        provider_groups = [line.provider_group for line in prepared_lines]
        provider_name = provider_names[0] if provider_names and len(set(provider_names)) == 1 else ("mixed" if provider_names else self._supported_provider_name(translation_config.get("provider", _DEFAULT_PROVIDER_NAME)))
        provider_group = provider_groups[0] if provider_groups and len(set(provider_groups)) == 1 else ("mixed" if provider_groups else PROVIDER_GROUP_EXPERIMENTAL)
        first_line = prepared_lines[0] if prepared_lines else None

        return PreparedTranslationRequest(
            provider_name=provider_name,
            provider=first_line.provider if first_line is not None and provider_name != "mixed" else first_line.provider if first_line is not None else None,
            provider_settings=dict(first_line.provider_settings) if first_line is not None and provider_name != "mixed" else {},
            target_languages=[line.target_lang for line in prepared_lines],
            provider_group=provider_group,
            experimental=any(line.experimental for line in prepared_lines),
            local_provider=any(line.local_provider for line in prepared_lines),
            lines=prepared_lines,
        )

    async def translate_target(
        self,
        *,
        source_text: str,
        source_lang: str,
        provider_name: str,
        provider_settings: dict[str, Any],
        target_lang: str,
        retries: int = 2,
        slot_id: str | None = None,
        label: str | None = None,
        provider_group: str | None = None,
        experimental: bool | None = None,
        local_provider: bool | None = None,
    ) -> tuple[TranslationItem, dict[str, Any]]:
        provider = self.providers.get(provider_name)
        normalized_target_lang = str(target_lang).strip().lower()
        normalized_settings = {str(key): str(value) for key, value in provider_settings.items()}
        if provider is None:
            diagnostics = {
                "provider": provider_name,
                "provider_group": provider_group or PROVIDER_GROUP_EXPERIMENTAL,
                "experimental": experimental if experimental is not None else True,
                "local_provider": local_provider if local_provider is not None else False,
                "status_message": f"Unsupported translation provider: {provider_name}",
                "used_default_prompt": False,
            }
            return (
                TranslationItem(
                    target_lang=normalized_target_lang,
                    text="",
                    provider=provider_name,
                    provider_group=diagnostics["provider_group"],
                    experimental=bool(diagnostics["experimental"]),
                    local_provider=bool(diagnostics["local_provider"]),
                    slot_id=slot_id,
                    label=label,
                    cached=False,
                    success=False,
                    error=diagnostics["status_message"],
                ),
                diagnostics,
            )

        cached = self.cache_manager.get_translation(
            source_text,
            source_lang,
            normalized_target_lang,
            provider_name=provider_name,
        )
        if cached is not None:
            cached_diagnostics = provider.diagnostics(normalized_settings)
            return (
                TranslationItem(
                    target_lang=normalized_target_lang,
                    text=cached,
                    provider=provider_name,
                    provider_group=cached_diagnostics.get("provider_group"),
                    experimental=bool(cached_diagnostics.get("experimental", False)),
                    local_provider=bool(cached_diagnostics.get("local_provider", False)),
                    slot_id=slot_id,
                    label=label,
                    cached=True,
                    success=True,
                ),
                cached_diagnostics,
            )

        translated_item, diagnostics = await self._translate_with_retry(
            provider=provider,
            source_text=source_text,
            source_lang=source_lang,
            target_lang=normalized_target_lang,
            provider_settings=normalized_settings,
            retries=retries,
            slot_id=slot_id,
            label=label,
        )
        if translated_item.success and translated_item.text:
            self.cache_manager.set_translation(
                source_text,
                source_lang,
                normalized_target_lang,
                translated_item.text,
                provider_name=provider_name,
            )
        return translated_item, diagnostics

    async def translate_targets(
        self,
        *,
        source_text: str,
        source_lang: str,
        provider_name: str,
        provider_settings: dict[str, Any],
        target_languages: list[str],
        retries: int = 2,
    ) -> TranslationBatch:
        provider = self.providers.get(provider_name)
        clean_target_languages = self._normalize_target_languages(target_languages)

        if provider is None:
            return self._failed_batch(
                provider_name=provider_name,
                source_lang=source_lang,
                target_languages=clean_target_languages,
                error=f"Unsupported translation provider: {provider_name}",
            )

        items: list[TranslationItem] = []
        normalized_settings = {str(key): str(value) for key, value in provider_settings.items()}
        batch_diagnostics = provider.diagnostics(normalized_settings)
        translated_by_lang: dict[str, tuple[TranslationItem, dict[str, Any]]] = {}

        if clean_target_languages:
            async def _translate_target(target_lang: str) -> tuple[str, TranslationItem, dict[str, Any]]:
                translated_item, item_diagnostics = await self.translate_target(
                    source_text=source_text,
                    source_lang=source_lang,
                    provider_name=provider_name,
                    provider_settings=normalized_settings,
                    target_lang=target_lang,
                    retries=retries,
                )
                return target_lang, translated_item, item_diagnostics

            translated_results = await asyncio.gather(
                *(_translate_target(target_lang) for target_lang in clean_target_languages)
            )
            for target_lang, translated_item, item_diagnostics in translated_results:
                if item_diagnostics.get("status_message"):
                    batch_diagnostics["status_message"] = item_diagnostics["status_message"]
                if item_diagnostics.get("used_default_prompt", False):
                    batch_diagnostics["used_default_prompt"] = True
                translated_by_lang[target_lang] = (translated_item, item_diagnostics)

        for target_lang in clean_target_languages:
            translated_item, _item_diagnostics = translated_by_lang[target_lang]
            items.append(translated_item)

        return TranslationBatch(
            provider=provider_name,
            source_lang=source_lang,
            target_languages=clean_target_languages,
            items=items,
            provider_group=str(batch_diagnostics.get("provider_group", PROVIDER_GROUP_STABLE)),
            experimental=bool(batch_diagnostics.get("experimental", False)),
            local_provider=bool(batch_diagnostics.get("local_provider", False)),
            used_default_prompt=bool(batch_diagnostics.get("used_default_prompt", False)),
            status_message=batch_diagnostics.get("status_message"),
        )

    async def _translate_with_retry(
        self,
        *,
        provider: BaseTranslationProvider,
        source_text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
        retries: int,
        slot_id: str | None = None,
        label: str | None = None,
    ) -> tuple[TranslationItem, dict[str, Any]]:
        attempt = 0
        last_error = "Translation failed."
        last_diagnostics = provider.diagnostics(provider_settings)
        while attempt <= retries:
            try:
                translated, diagnostics = await provider.translate(
                    text=source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider_settings=provider_settings,
                )
                return (
                    TranslationItem(
                        target_lang=target_lang,
                        text=translated,
                        provider=provider.info.name,
                        provider_group=diagnostics.get("provider_group"),
                        experimental=bool(diagnostics.get("experimental", False)),
                        local_provider=bool(diagnostics.get("local_provider", False)),
                        slot_id=slot_id,
                        label=label,
                        cached=False,
                        success=True,
                    ),
                    diagnostics,
                )
            except Exception as exc:
                provider_error = exc if isinstance(exc, TranslationProviderError) else TranslationProviderError(str(exc))
                last_error = str(provider_error)
                last_diagnostics = provider.diagnostics(provider_settings)
                last_diagnostics["status_message"] = last_error
                attempt += 1
                if attempt <= retries and getattr(provider_error, "retryable", False):
                    await asyncio.sleep(0.35 * attempt)
                    continue
                break

        return (
            TranslationItem(
                target_lang=target_lang,
                text="",
                provider=provider.info.name,
                provider_group=last_diagnostics.get("provider_group"),
                experimental=bool(last_diagnostics.get("experimental", False)),
                local_provider=bool(last_diagnostics.get("local_provider", False)),
                slot_id=slot_id,
                label=label,
                cached=False,
                success=False,
                error=last_error,
            ),
            last_diagnostics,
        )

    def _failed_batch(
        self,
        *,
        provider_name: str,
        source_lang: str,
        target_languages: list[str],
        error: str,
    ) -> TranslationBatch:
        return TranslationBatch(
            provider=provider_name,
            source_lang=source_lang,
            target_languages=target_languages,
            items=[
                TranslationItem(
                    target_lang=target_lang,
                    text="",
                    provider=provider_name,
                    provider_group=PROVIDER_GROUP_EXPERIMENTAL,
                    experimental=True,
                    local_provider=False,
                    cached=False,
                    success=False,
                    error=error,
                )
                for target_lang in target_languages
            ],
            provider_group=PROVIDER_GROUP_EXPERIMENTAL,
            experimental=True,
            local_provider=False,
            used_default_prompt=False,
            status_message=error,
        )


__all__ = [
    "AzureTranslatorProvider",
    "BaseTranslationProvider",
    "DeepLProvider",
    "FreeWebTranslateProvider",
    "GoogleCloudTranslationV3Provider",
    "GoogleGasUrlProvider",
    "GoogleTranslateV2Provider",
    "GoogleWebProvider",
    "LibreTranslateProvider",
    "OpenAICompatibleChatProvider",
    "PreparedTranslationLine",
    "PreparedTranslationRequest",
    "PublicLibreTranslateMirrorProvider",
    "TranslationBatch",
    "TranslationEngine",
    "TranslationProviderError",
    "TranslationProviderInfo",
]
