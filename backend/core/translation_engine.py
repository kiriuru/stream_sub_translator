from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import unescape
import logging
import socket
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx

from backend.core.cache_manager import CacheManager
from backend.models import TranslationDiagnostics, TranslationItem

DEFAULT_SUBTITLE_TRANSLATION_PROMPT = (
    "You are a subtitle translator for livestream captions. "
    "Translate only the user subtitle text into the requested target language. "
    "Do not explain anything. Do not add notes, prefixes, or assistant-style chatter. "
    "Keep the output concise, readable, and subtitle-friendly. "
    "Preserve names, game terms, UI labels, and obvious proper nouns when appropriate."
)

PROVIDER_GROUP_STABLE = "stable"
PROVIDER_GROUP_LLM = "llm"
PROVIDER_GROUP_LOCAL_LLM = "local_llm"
PROVIDER_GROUP_EXPERIMENTAL = "experimental"

logger = logging.getLogger(__name__)


class TranslationProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class TranslationProviderInfo:
    name: str
    group: str
    stable: bool = False
    experimental: bool = False
    local_provider: bool = False


class BaseTranslationProvider:
    info = TranslationProviderInfo(name="base", group=PROVIDER_GROUP_STABLE)

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

    def diagnostics(self, provider_settings: dict[str, str]) -> dict[str, Any]:
        return {
            "provider": self.info.name,
            "provider_group": self.info.group,
            "experimental": self.info.experimental,
            "local_provider": self.info.local_provider,
            "used_default_prompt": False,
            "status_message": None,
        }

    def _mask_secret(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def _normalize_source_lang(self, source_lang: str) -> str:
        normalized = str(source_lang or "auto").strip().lower()
        return normalized or "auto"

    def _http_error(self, prefix: str, exc: Exception) -> TranslationProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return TranslationProviderError(f"{prefix}: request timed out.", retryable=True)
        if isinstance(exc, httpx.NetworkError):
            return TranslationProviderError(f"{prefix}: network error: {exc}", retryable=True)
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            detail = exc.response.text.strip()
            retryable = status_code >= 500 or status_code == 429
            message = f"{prefix}: HTTP {status_code}"
            if detail:
                message = f"{message} - {detail[:280]}"
            return TranslationProviderError(message, retryable=retryable)
        if isinstance(exc, TranslationProviderError):
            return exc
        return TranslationProviderError(f"{prefix}: {exc}", retryable=False)

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        error_prefix: str,
    ) -> Any:
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise self._http_error(error_prefix, exc) from exc


class GoogleTranslateV2Provider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_translate_v2",
        group=PROVIDER_GROUP_STABLE,
        stable=True,
    )

    def _normalize_google_api_key(self, raw_value: str) -> tuple[str, dict[str, Any]]:
        trimmed = str(raw_value or "").strip()
        normalized = trimmed
        extracted_from_query = False
        removed_trailing_query = False

        if "key=" in trimmed:
            parsed = urlparse(trimmed)
            query_values = parse_qs(parsed.query or trimmed)
            candidate = (query_values.get("key") or [""])[0].strip()
            if candidate:
                normalized = candidate
                extracted_from_query = candidate != trimmed

        if normalized.startswith("AIza") and "&" in normalized:
            candidate = normalized.split("&", 1)[0].strip()
            if candidate and candidate != normalized:
                normalized = candidate
                removed_trailing_query = True

        diagnostics = {
            "api_key_present": bool(normalized),
            "api_key_length": len(normalized),
            "api_key_masked_preview": self._mask_secret(normalized),
            "api_key_trimmed_changed": raw_value != trimmed,
            "api_key_sanitized_changed": trimmed != normalized,
            "api_key_extracted_from_query": extracted_from_query,
            "api_key_removed_trailing_query": removed_trailing_query,
        }
        return normalized, diagnostics

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        raw_api_key = str(provider_settings.get("api_key", ""))
        api_key, key_diagnostics = self._normalize_google_api_key(raw_api_key)
        if not api_key:
            raise TranslationProviderError("Google Translate v2 API key is missing.")

        endpoint = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": api_key}
        data: dict[str, str] = {"q": text, "target": target_lang, "format": "text"}
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            data["source"] = normalized_source

        diagnostics = self.diagnostics(provider_settings)
        diagnostics.update(
            {
                "endpoint_used": endpoint,
                **key_diagnostics,
                "http_method": "POST",
            }
        )

        async with httpx.AsyncClient() as client:
            try:
                payload = await self._get_json(
                    client,
                    url=endpoint,
                    method="POST",
                    params=params,
                    data=data,
                    error_prefix="Google Translate v2 request failed",
                )
            except TranslationProviderError as exc:
                debug_message = (
                    f"{exc} | provider=google_translate_v2"
                    f" | endpoint={endpoint}"
                    f" | api_key_present={key_diagnostics['api_key_present']}"
                    f" | api_key_length={key_diagnostics['api_key_length']}"
                    f" | api_key_preview={key_diagnostics['api_key_masked_preview']}"
                    f" | trim_changed={key_diagnostics['api_key_trimmed_changed']}"
                    f" | sanitized_changed={key_diagnostics['api_key_sanitized_changed']}"
                    f" | extracted_from_query={key_diagnostics['api_key_extracted_from_query']}"
                    f" | removed_trailing_query={key_diagnostics['api_key_removed_trailing_query']}"
                )
                logger.warning(debug_message)
                raise TranslationProviderError(debug_message, retryable=exc.retryable) from exc

        translated = payload.get("data", {}).get("translations", [{}])[0].get("translatedText")
        if not translated:
            raise TranslationProviderError("Google Translate v2 returned an empty translation.")
        diagnostics["status_message"] = (
            f"Google Translate v2 request succeeded. endpoint={endpoint} "
            f"api_key_present={key_diagnostics['api_key_present']} key_length={key_diagnostics['api_key_length']} "
            f"key_preview={key_diagnostics['api_key_masked_preview']} trim_changed={key_diagnostics['api_key_trimmed_changed']} "
            f"sanitized_changed={key_diagnostics['api_key_sanitized_changed']}"
        )
        return unescape(str(translated)), diagnostics


class GoogleCloudTranslationV3Provider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_cloud_translation_v3",
        group=PROVIDER_GROUP_STABLE,
        stable=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        project_id = provider_settings.get("project_id", "").strip()
        access_token = provider_settings.get("access_token", "").strip()
        location = provider_settings.get("location", "").strip() or "global"
        model = provider_settings.get("model", "").strip()

        if not project_id:
            raise TranslationProviderError("Google Cloud Translation v3 project ID is missing.")
        if not access_token:
            raise TranslationProviderError("Google Cloud Translation v3 access token is missing.")

        endpoint = f"https://translation.googleapis.com/v3/projects/{project_id}/locations/{location}:translateText"
        payload: dict[str, Any] = {
            "contents": [text],
            "targetLanguageCode": target_lang,
            "mimeType": "text/plain",
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            payload["sourceLanguageCode"] = normalized_source
        if model:
            payload["model"] = model

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-user-project": project_id,
        }
        diagnostics = self.diagnostics(provider_settings)
        diagnostics.update(
            {
                "endpoint_used": endpoint,
                "http_method": "POST",
                "location": location,
                "project_id_present": True,
                "access_token_present": True,
                "access_token_masked_preview": self._mask_secret(access_token),
                "model_requested": model or None,
                "status_message": (
                    "Cloud Translation - Advanced (v3) via REST. "
                    "Requires OAuth access token; API keys are not supported."
                ),
            }
        )

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=endpoint,
                method="POST",
                json=payload,
                headers=headers,
                error_prefix="Google Cloud Translation v3 request failed",
            )

        translations = data.get("translations", [])
        translated = translations[0].get("translatedText") if translations else None
        if not translated:
            raise TranslationProviderError("Google Cloud Translation v3 returned an empty translation.")
        return unescape(str(translated)), diagnostics


class GoogleGasUrlProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_gas_url",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        gas_url = provider_settings.get("gas_url", "").strip()
        if not gas_url:
            raise TranslationProviderError("Google GAS URL is missing.")

        payload = {
            "text": text,
            "source_lang": self._normalize_source_lang(source_lang),
            "target_lang": target_lang,
        }

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=gas_url,
                method="POST",
                json=payload,
                error_prefix="Google GAS URL request failed",
            )

        translated = (
            data.get("translatedText")
            or data.get("text")
            or data.get("translation")
            or data.get("output")
        )
        if not translated:
            raise TranslationProviderError(
                "Google GAS URL returned no translated text. Expected one of: translatedText, text, translation, output."
            )
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental Google GAS URL provider. Reliability depends on your script."
        return str(translated), diagnostics


class GoogleWebProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_web",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        normalized_source = self._normalize_source_lang(source_lang)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={quote_plus(normalized_source)}&tl={quote_plus(target_lang)}&dt=t&q={quote_plus(text)}"
        )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=20.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise self._http_error("Google Web request failed", exc) from exc

        translated_parts: list[str] = []
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        translated_parts.append(str(item[0]))
        translated = "".join(translated_parts).strip()
        if not translated:
            raise TranslationProviderError("Google Web returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental Google Web provider. Best-effort only."
        return translated, diagnostics


class AzureTranslatorProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="azure_translator",
        group=PROVIDER_GROUP_STABLE,
        stable=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_key = provider_settings.get("api_key", "").strip()
        endpoint = provider_settings.get("endpoint", "").strip() or "https://api.cognitive.microsofttranslator.com"
        region = provider_settings.get("region", "").strip()
        if not api_key:
            raise TranslationProviderError("Azure Translator API key is missing.")
        if not endpoint:
            raise TranslationProviderError("Azure Translator endpoint is missing.")

        params: dict[str, str] = {
            "api-version": "3.0",
            "to": target_lang,
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            params["from"] = normalized_source

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json",
        }
        if region:
            headers["Ocp-Apim-Subscription-Region"] = region

        async with httpx.AsyncClient() as client:
            payload = await self._get_json(
                client,
                url=f"{endpoint.rstrip('/')}/translate",
                method="POST",
                params=params,
                json=[{"Text": text}],
                headers=headers,
                error_prefix="Azure Translator request failed",
            )

        translations = payload[0].get("translations", []) if isinstance(payload, list) and payload else []
        translated = translations[0].get("text") if translations else None
        if not translated:
            raise TranslationProviderError("Azure Translator returned an empty translation.")
        return str(translated), self.diagnostics(provider_settings)


class DeepLProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="deepl",
        group=PROVIDER_GROUP_STABLE,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_key = provider_settings.get("api_key", "").strip()
        if not api_key:
            raise TranslationProviderError("DeepL API key is missing.")

        api_url = provider_settings.get("api_url", "").strip() or "https://api-free.deepl.com/v2/translate"
        data: dict[str, str] = {
            "auth_key": api_key,
            "text": text,
            "target_lang": target_lang.upper(),
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            data["source_lang"] = normalized_source.upper()

        async with httpx.AsyncClient() as client:
            payload = await self._get_json(
                client,
                url=api_url,
                method="POST",
                data=data,
                error_prefix="DeepL request failed",
            )

        translations = payload.get("translations", [])
        if not translations:
            raise TranslationProviderError("DeepL returned an empty translation.")
        return str(translations[0].get("text", "")), self.diagnostics(provider_settings)


class LibreTranslateProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="libretranslate",
        group=PROVIDER_GROUP_STABLE,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_url = provider_settings.get("api_url", "").strip() or "https://libretranslate.com/translate"
        payload: dict[str, str] = {
            "q": text,
            "source": self._normalize_source_lang(source_lang),
            "target": target_lang,
            "format": "text",
        }
        api_key = provider_settings.get("api_key", "").strip()
        if api_key:
            payload["api_key"] = api_key

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=api_url,
                method="POST",
                json=payload,
                error_prefix="LibreTranslate request failed",
            )

        translated = data.get("translatedText")
        if not translated:
            raise TranslationProviderError("LibreTranslate returned an empty translation.")
        return str(translated), self.diagnostics(provider_settings)


class OpenAICompatibleChatProvider(BaseTranslationProvider):
    def __init__(
        self,
        *,
        name: str,
        group: str,
        default_base_url: str,
        requires_api_key: bool,
        local_provider: bool = False,
    ) -> None:
        self.info = TranslationProviderInfo(
            name=name,
            group=group,
            stable=group == PROVIDER_GROUP_STABLE,
            local_provider=local_provider,
        )
        self.default_base_url = default_base_url
        self.requires_api_key = requires_api_key

    def diagnostics(self, provider_settings: dict[str, str]) -> dict[str, Any]:
        custom_prompt = provider_settings.get("custom_prompt", "").strip()
        diagnostics = super().diagnostics(provider_settings)
        diagnostics["used_default_prompt"] = not bool(custom_prompt)
        diagnostics["status_message"] = (
            "Using built-in subtitle translation prompt."
            if not custom_prompt
            else "Using custom subtitle translation prompt."
        )
        return diagnostics

    def _build_endpoint(self, provider_settings: dict[str, str]) -> str:
        base_url = provider_settings.get("base_url", "").strip() or self.default_base_url
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    def _build_prompt_messages(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[list[dict[str, str]], bool]:
        custom_prompt = provider_settings.get("custom_prompt", "").strip()
        system_prompt = custom_prompt or DEFAULT_SUBTITLE_TRANSLATION_PROMPT
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source == "auto":
            user_prompt = (
                f"Detect the source language and translate the subtitle text into '{target_lang}'. "
                "Return only the translated subtitle text.\n\n"
                f"Subtitle text:\n{text}"
            )
        else:
            user_prompt = (
                f"Translate the subtitle text from '{normalized_source}' into '{target_lang}'. "
                "Return only the translated subtitle text.\n\n"
                f"Subtitle text:\n{text}"
            )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], not bool(custom_prompt)

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_key = provider_settings.get("api_key", "").strip()
        if self.requires_api_key and not api_key:
            raise TranslationProviderError(f"{self.info.name} API key is missing.")

        model = provider_settings.get("model", "").strip()
        if not model:
            raise TranslationProviderError(f"{self.info.name} model is missing.")

        messages, used_default_prompt = self._build_prompt_messages(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            provider_settings=provider_settings,
        )
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self.info.name == "openrouter":
            headers.setdefault("HTTP-Referer", "http://127.0.0.1:8765")
            headers.setdefault("X-Title", "Stream Subtitle Translator")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "stream": False,
        }

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=self._build_endpoint(provider_settings),
                method="POST",
                json=payload,
                headers=headers,
                timeout=45.0,
                error_prefix=f"{self.info.name} translation request failed",
            )

        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            content = "".join(text_parts).strip()
        if not content:
            raise TranslationProviderError(f"{self.info.name} returned an empty translation.")

        diagnostics = self.diagnostics(provider_settings)
        diagnostics["used_default_prompt"] = used_default_prompt
        return str(content).strip(), diagnostics


class PublicLibreTranslateMirrorProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="public_libretranslate_mirror",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_url = provider_settings.get("api_url", "").strip() or "https://translate.fedilab.app/translate"
        payload = {
            "q": text,
            "source": self._normalize_source_lang(source_lang),
            "target": target_lang,
            "format": "text",
        }

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=api_url,
                method="POST",
                json=payload,
                error_prefix="Public LibreTranslate mirror request failed",
            )

        translated = data.get("translatedText")
        if not translated:
            raise TranslationProviderError("Public LibreTranslate mirror returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental public mirror. Availability may vary."
        return str(translated), diagnostics


class FreeWebTranslateProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="free_web_translate",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        normalized_source = self._normalize_source_lang(source_lang)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={quote_plus(normalized_source)}&tl={quote_plus(target_lang)}&dt=t&q={quote_plus(text)}"
        )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=20.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise self._http_error("Free Web Translate request failed", exc) from exc

        translated_parts: list[str] = []
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        translated_parts.append(str(item[0]))
        translated = "".join(translated_parts).strip()
        if not translated:
            raise TranslationProviderError("Free Web Translate returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental no-key web provider. Behavior may change without notice."
        return translated, diagnostics


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
class PreparedTranslationRequest:
    provider_name: str
    provider: BaseTranslationProvider | None
    provider_settings: dict[str, str]
    target_languages: list[str]
    provider_group: str
    experimental: bool = False
    local_provider: bool = False


class TranslationEngine:
    def __init__(self, cache_manager: CacheManager) -> None:
        self.cache_manager = cache_manager
        self.providers: dict[str, BaseTranslationProvider] = {
            GoogleTranslateV2Provider.info.name: GoogleTranslateV2Provider(),
            GoogleCloudTranslationV3Provider.info.name: GoogleCloudTranslationV3Provider(),
            GoogleGasUrlProvider.info.name: GoogleGasUrlProvider(),
            GoogleWebProvider.info.name: GoogleWebProvider(),
            AzureTranslatorProvider.info.name: AzureTranslatorProvider(),
            DeepLProvider.info.name: DeepLProvider(),
            LibreTranslateProvider.info.name: LibreTranslateProvider(),
            "openai": OpenAICompatibleChatProvider(
                name="openai",
                group=PROVIDER_GROUP_LLM,
                default_base_url="https://api.openai.com/v1",
                requires_api_key=True,
            ),
            "openrouter": OpenAICompatibleChatProvider(
                name="openrouter",
                group=PROVIDER_GROUP_LLM,
                default_base_url="https://openrouter.ai/api/v1",
                requires_api_key=True,
            ),
            "lm_studio": OpenAICompatibleChatProvider(
                name="lm_studio",
                group=PROVIDER_GROUP_LOCAL_LLM,
                default_base_url="http://127.0.0.1:1234/v1",
                requires_api_key=False,
                local_provider=True,
            ),
            "ollama": OpenAICompatibleChatProvider(
                name="ollama",
                group=PROVIDER_GROUP_LOCAL_LLM,
                default_base_url="http://127.0.0.1:11434/v1",
                requires_api_key=False,
                local_provider=True,
            ),
            PublicLibreTranslateMirrorProvider.info.name: PublicLibreTranslateMirrorProvider(),
            FreeWebTranslateProvider.info.name: FreeWebTranslateProvider(),
        }
        self._last_settings_signature: tuple[tuple[str, str], ...] | None = None

    def _required_fields_for_provider(self, provider_name: str) -> list[str]:
        if provider_name == "google_translate_v2":
            return ["api_key"]
        if provider_name == "google_cloud_translation_v3":
            return ["project_id", "access_token"]
        if provider_name == "google_gas_url":
            return ["gas_url"]
        if provider_name == "azure_translator":
            return ["api_key", "endpoint"]
        if provider_name in {"deepl"}:
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

        provider_name = str(translation_config.get("provider", "google_translate_v2")).strip()
        provider = self.providers.get(provider_name)
        target_languages = [
            str(item).strip().lower()
            for item in translation_config.get("target_languages", [])
            if str(item).strip()
        ]
        provider_settings_map = translation_config.get("provider_settings", {})
        provider_settings = provider_settings_map.get(provider_name, {}) if isinstance(provider_settings_map, dict) else {}
        if not isinstance(provider_settings, dict):
            provider_settings = {}
        normalized_settings = {str(k): str(v).strip() for k, v in provider_settings.items()}

        if provider is None:
            return TranslationDiagnostics(
                enabled=True,
                provider=provider_name,
                status="error",
                summary=f"Translation provider '{provider_name}' is not supported.",
                reason="Unsupported provider.",
                target_languages=target_languages,
                configured=False,
                ready=False,
                degraded=True,
            )

        missing_fields = [
            field_name
            for field_name in self._required_fields_for_provider(provider_name)
            if not normalized_settings.get(field_name, "").strip()
        ]
        diagnostics = provider.diagnostics(normalized_settings)
        endpoint = self._provider_endpoint_for_summary(provider_name, normalized_settings)
        uses_default_prompt = bool(diagnostics.get("used_default_prompt", False))

        if not target_languages:
            return TranslationDiagnostics(
                enabled=True,
                provider=provider_name,
                provider_group=str(diagnostics.get("provider_group", provider.info.group)),
                experimental=bool(diagnostics.get("experimental", provider.info.experimental)),
                local_provider=bool(diagnostics.get("local_provider", provider.info.local_provider)),
                configured=False,
                ready=False,
                degraded=True,
                status="partial",
                summary="Translation enabled, but no target languages are configured.",
                reason="Add at least one target language.",
                missing_fields=[],
                target_languages=target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=uses_default_prompt,
            )

        if missing_fields:
            return TranslationDiagnostics(
                enabled=True,
                provider=provider_name,
                provider_group=str(diagnostics.get("provider_group", provider.info.group)),
                experimental=bool(diagnostics.get("experimental", provider.info.experimental)),
                local_provider=bool(diagnostics.get("local_provider", provider.info.local_provider)),
                configured=False,
                ready=False,
                degraded=True,
                status="partial",
                summary=f"Translation provider '{provider_name}' is partially configured.",
                reason=f"Missing required settings: {', '.join(missing_fields)}.",
                missing_fields=missing_fields,
                target_languages=target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=uses_default_prompt,
            )

        if provider.info.local_provider:
            reachable, reason = self._check_local_endpoint(endpoint)
            return TranslationDiagnostics(
                enabled=True,
                provider=provider_name,
                provider_group=str(diagnostics.get("provider_group", provider.info.group)),
                experimental=bool(diagnostics.get("experimental", provider.info.experimental)),
                local_provider=True,
                configured=True,
                ready=reachable,
                degraded=not reachable,
                status="ready" if reachable else "degraded",
                summary=(
                    f"Local translation provider '{provider_name}' is ready."
                    if reachable
                    else f"Local translation provider '{provider_name}' is configured but unreachable."
                ),
                reason=reason,
                missing_fields=[],
                target_languages=target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=uses_default_prompt,
            )

        if provider.info.experimental:
            return TranslationDiagnostics(
                enabled=True,
                provider=provider_name,
                provider_group=str(diagnostics.get("provider_group", provider.info.group)),
                experimental=True,
                local_provider=bool(diagnostics.get("local_provider", provider.info.local_provider)),
                configured=True,
                ready=True,
                degraded=True,
                status="experimental",
                summary=f"Experimental translation provider '{provider_name}' is configured best-effort.",
                reason="Experimental providers may fail or change behavior without notice.",
                missing_fields=[],
                target_languages=target_languages,
                provider_endpoint=endpoint,
                uses_default_prompt=uses_default_prompt,
            )

        return TranslationDiagnostics(
            enabled=True,
            provider=provider_name,
            provider_group=str(diagnostics.get("provider_group", provider.info.group)),
            experimental=bool(diagnostics.get("experimental", provider.info.experimental)),
            local_provider=bool(diagnostics.get("local_provider", provider.info.local_provider)),
            configured=True,
            ready=True,
            degraded=False,
            status="ready",
            summary=f"Translation provider '{provider_name}' is configured.",
            reason=diagnostics.get("status_message"),
            missing_fields=[],
            target_languages=target_languages,
            provider_endpoint=endpoint,
            uses_default_prompt=uses_default_prompt,
        )

    def _build_settings_signature(self, translation_config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
        if not isinstance(translation_config, dict):
            return ()
        provider = str(translation_config.get("provider", "")).strip()
        provider_settings_map = translation_config.get("provider_settings", {})
        provider_settings = provider_settings_map.get(provider, {}) if isinstance(provider_settings_map, dict) else {}
        if not isinstance(provider_settings, dict):
            provider_settings = {}
        target_languages = translation_config.get("target_languages", [])
        if not isinstance(target_languages, list):
            target_languages = []
        signature_payload: dict[str, str] = {
            "enabled": str(bool(translation_config.get("enabled", False))),
            "provider": provider,
            "targets": ",".join(str(item).strip().lower() for item in target_languages if str(item).strip()),
        }
        for key, value in provider_settings.items():
            signature_payload[f"provider_setting:{key}"] = str(value)
        return tuple(sorted(signature_payload.items()))

    def apply_live_settings(self, translation_config: dict[str, Any]) -> None:
        new_signature = self._build_settings_signature(translation_config)
        if self._last_settings_signature is not None and new_signature != self._last_settings_signature:
            self.cache_manager.clear_translation_cache()
        self._last_settings_signature = new_signature

    @staticmethod
    def _normalize_target_languages(target_languages: list[str]) -> list[str]:
        clean_target_languages = [
            str(item).strip().lower()
            for item in target_languages
            if str(item).strip()
        ]
        return list(dict.fromkeys(clean_target_languages))

    def prepare_request(self, translation_config: dict[str, Any]) -> PreparedTranslationRequest:
        provider_name = str(translation_config.get("provider", "google_translate_v2"))
        provider_settings_map = translation_config.get("provider_settings", {})
        if not isinstance(provider_settings_map, dict):
            provider_settings_map = {}
        provider_settings = provider_settings_map.get(provider_name, {})
        if not isinstance(provider_settings, dict):
            provider_settings = {}
        provider = self.providers.get(provider_name)
        target_languages = self._normalize_target_languages(translation_config.get("target_languages", []))
        provider_group = provider.info.group if provider is not None else PROVIDER_GROUP_EXPERIMENTAL
        experimental = bool(provider.info.experimental) if provider is not None else True
        local_provider = bool(provider.info.local_provider) if provider is not None else False
        return PreparedTranslationRequest(
            provider_name=provider_name,
            provider=provider,
            provider_settings={str(k): str(v) for k, v in provider_settings.items()},
            target_languages=target_languages,
            provider_group=provider_group,
            experimental=experimental,
            local_provider=local_provider,
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
    ) -> tuple[TranslationItem, dict[str, Any]]:
        provider = self.providers.get(provider_name)
        normalized_target_lang = str(target_lang).strip().lower()
        normalized_settings = {str(k): str(v) for k, v in provider_settings.items()}
        if provider is None:
            diagnostics = {
                "provider": provider_name,
                "provider_group": PROVIDER_GROUP_EXPERIMENTAL,
                "experimental": True,
                "local_provider": False,
                "status_message": f"Unsupported translation provider: {provider_name}",
                "used_default_prompt": False,
            }
            return (
                TranslationItem(
                    target_lang=normalized_target_lang,
                    text="",
                    provider=provider_name,
                    cached=False,
                    success=False,
                    error=diagnostics["status_message"],
                ),
                diagnostics,
            )
        cached = self.cache_manager.get_translation(source_text, source_lang, normalized_target_lang)
        if cached is not None:
            return (
                TranslationItem(
                    target_lang=normalized_target_lang,
                    text=cached,
                    provider=provider_name,
                    cached=True,
                    success=True,
                ),
                provider.diagnostics(normalized_settings),
            )
        translated_item, diagnostics = await self._translate_with_retry(
            provider=provider,
            source_text=source_text,
            source_lang=source_lang,
            target_lang=normalized_target_lang,
            provider_settings=normalized_settings,
            retries=retries,
        )
        if translated_item.success and translated_item.text:
            self.cache_manager.set_translation(source_text, source_lang, normalized_target_lang, translated_item.text)
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
        normalized_settings = {str(k): str(v) for k, v in provider_settings.items()}
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
