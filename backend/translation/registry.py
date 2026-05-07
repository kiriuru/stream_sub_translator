from __future__ import annotations

from backend.translation.base import (
    PROVIDER_GROUP_LLM,
    PROVIDER_GROUP_LOCAL_LLM,
    BaseTranslationProvider,
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


def build_default_provider_registry() -> dict[str, BaseTranslationProvider]:
    providers = [
        GoogleTranslateV2Provider(),
        GoogleCloudTranslationV3Provider(),
        GoogleGasUrlProvider(),
        GoogleWebProvider(),
        AzureTranslatorProvider(),
        DeepLProvider(),
        LibreTranslateProvider(),
        OpenAICompatibleChatProvider(
            name="openai",
            group=PROVIDER_GROUP_LLM,
            default_base_url="https://api.openai.com/v1",
            requires_api_key=True,
        ),
        OpenAICompatibleChatProvider(
            name="openrouter",
            group=PROVIDER_GROUP_LLM,
            default_base_url="https://openrouter.ai/api/v1",
            requires_api_key=True,
        ),
        OpenAICompatibleChatProvider(
            name="lm_studio",
            group=PROVIDER_GROUP_LOCAL_LLM,
            default_base_url="http://127.0.0.1:1234/v1",
            requires_api_key=False,
            local_provider=True,
        ),
        OpenAICompatibleChatProvider(
            name="ollama",
            group=PROVIDER_GROUP_LOCAL_LLM,
            default_base_url="http://127.0.0.1:11434/v1",
            requires_api_key=False,
            local_provider=True,
        ),
        PublicLibreTranslateMirrorProvider(),
        FreeWebTranslateProvider(),
    ]
    return {provider.info.name: provider for provider in providers}


__all__ = ["build_default_provider_registry"]
