from __future__ import annotations

import importlib
import sys
from pathlib import Path

from backend.config import LocalConfigManager, settings
from backend.core.cache_manager import CacheManager
from backend.core.translation_engine import TranslationEngine


def _torch_summary() -> dict[str, object]:
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:
        return {
            "available": False,
            "version": f"unavailable ({exc})",
            "cuda_build": None,
            "cuda_available": False,
            "device_count": 0,
            "gpu_name": None,
        }

    cuda_build = getattr(getattr(torch, "version", None), "cuda", None)
    cuda_available = bool(torch.cuda.is_available())
    device_count = int(torch.cuda.device_count()) if cuda_available else int(getattr(torch.cuda, "device_count", lambda: 0)())
    gpu_name = None
    if device_count > 0:
        try:
            gpu_name = str(torch.cuda.get_device_name(0))
        except Exception:
            gpu_name = None

    return {
        "available": True,
        "version": str(getattr(torch, "__version__", "unknown")),
        "cuda_build": cuda_build,
        "cuda_available": cuda_available,
        "device_count": device_count,
        "gpu_name": gpu_name,
    }


def _likely_asr_mode(config: dict, model_path: Path, torch_info: dict[str, object]) -> tuple[str, str | None]:
    asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
    asr_mode = str(asr_config.get("mode", "local")).strip().lower() if isinstance(asr_config, dict) else "local"
    if asr_mode == "browser_google":
        browser = asr_config.get("browser", {}) if isinstance(asr_config, dict) else {}
        browser_lang = str(browser.get("recognition_language", "ru-RU")).strip() if isinstance(browser, dict) else "ru-RU"
        return (
            "browser speech worker",
            f"Browser speech recognition mode is configured. Recognition will run in a separate browser window using {browser_lang}.",
        )
    provider_preference = str(asr_config.get("provider_preference", "official_eu_parakeet_realtime"))
    prefer_gpu = bool(asr_config.get("prefer_gpu", True))

    if not model_path.exists():
        return (
            "ASR cold-start download pending",
            "The first Start in the dashboard will download the official EU Parakeet model automatically.",
        )

    cuda_build = bool(torch_info.get("cuda_build"))
    cuda_available = bool(torch_info.get("cuda_available"))

    if provider_preference == "official_eu_parakeet":
        if prefer_gpu and cuda_build and cuda_available:
            return "baseline compatibility", "Baseline provider selected explicitly; realtime is not the active default."
        return "baseline fallback", "Baseline provider selected explicitly."

    if provider_preference in {"official_eu_parakeet_realtime", "auto"}:
        if prefer_gpu and cuda_build and cuda_available:
            return "realtime GPU", None
        if prefer_gpu:
            if not cuda_build:
                return "realtime CPU fallback", "CPU-only PyTorch build detected in this project venv."
            if not cuda_available:
                return "realtime CPU fallback", "CUDA build is installed, but torch.cuda.is_available() is false."
        return "realtime CPU fallback", "GPU preference is off or CUDA is unavailable."

    return "unknown", "ASR provider preference is not recognized."


def main() -> None:
    config_manager = LocalConfigManager(settings)
    config = config_manager.load()
    translation_engine = TranslationEngine(CacheManager(settings.data_dir / "cache"))
    translation_summary = translation_engine.summarize_readiness(config.get("translation", {}))
    torch_info = _torch_summary()
    model_path = settings.models_dir / "parakeet-tdt-0.6b-v3" / "parakeet-tdt-0.6b-v3.nemo"
    mode_label, mode_reason = _likely_asr_mode(config, model_path, torch_info)

    print("[preflight] Local environment summary")
    print(f"[preflight] Python: {sys.executable}")
    print(f"[preflight] Venv: {Path(sys.executable).parent.parent}")
    print(f"[preflight] Config: {settings.config_path}")
    print(f"[preflight] Model file: {'present' if model_path.exists() else 'missing'} -> {model_path}")
    print(
        f"[preflight] Torch: {torch_info['version']} | CUDA build: {torch_info['cuda_build'] or 'no'} | "
        f"CUDA available: {'yes' if torch_info['cuda_available'] else 'no'}"
    )
    print(
        f"[preflight] GPU count: {torch_info['device_count']} | "
        f"GPU0: {torch_info['gpu_name'] or 'n/a'}"
    )
    print(
        f"[preflight] ASR policy: mode={config.get('asr', {}).get('mode', 'local')} | "
        f"provider={config.get('asr', {}).get('provider_preference', 'official_eu_parakeet_realtime')} | "
        f"prefer_gpu={'yes' if config.get('asr', {}).get('prefer_gpu', True) else 'no'}"
    )
    print(f"[preflight] Likely runtime mode: {mode_label}")
    if mode_reason:
        print(f"[preflight] ASR note: {mode_reason}")
    print(
        f"[preflight] Translation: {translation_summary.status} | "
        f"provider={translation_summary.provider or 'none'} | "
        f"targets={', '.join(translation_summary.target_languages) if translation_summary.target_languages else 'none'}"
    )
    print(f"[preflight] Translation summary: {translation_summary.summary}")
    if translation_summary.reason:
        print(f"[preflight] Translation note: {translation_summary.reason}")


if __name__ == "__main__":
    main()
