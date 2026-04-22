from __future__ import annotations

import argparse
import sys

from backend.config import settings
from backend.core.parakeet_provider import (
    OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME,
    OFFICIAL_EU_PARAKEET_REPO,
    OFFICIAL_EU_PARAKEET_URL,
    ensure_official_eu_parakeet_model,
)


def install_official_eu_model():
    return ensure_official_eu_parakeet_model(settings.models_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the official EU multilingual Parakeet model locally.")
    parser.add_argument("--model", default="eu", choices=["eu"], help="ASR model bundle to install.")
    args = parser.parse_args()

    if args.model != "eu":
        print("Only the official EU multilingual model is supported in this installer.")
        return 1

    print(f"Installing official model: {OFFICIAL_EU_PARAKEET_REPO}")
    print(f"Source: {OFFICIAL_EU_PARAKEET_URL}")
    print(f"Destination: {settings.models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME}")

    try:
        target_file = install_official_eu_model()
    except Exception as exc:
        print(f"Model install failed: {exc}")
        return 1

    print(f"Installed official EU multilingual model to: {target_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
