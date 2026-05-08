from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Callable
import urllib.error
import urllib.request
from datetime import datetime, timezone


OFFICIAL_EU_PARAKEET_REPO = "nvidia/parakeet-tdt-0.6b-v3"
OFFICIAL_EU_PARAKEET_FILENAME = "parakeet-tdt-0.6b-v3.nemo"
OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME = "parakeet-tdt-0.6b-v3"
OFFICIAL_EU_PARAKEET_URL = (
    f"https://huggingface.co/{OFFICIAL_EU_PARAKEET_REPO}/resolve/main/{OFFICIAL_EU_PARAKEET_FILENAME}?download=true"
)
_MODEL_INSTALL_LOCK = threading.Lock()
ProgressCallback = Callable[[str], None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def read_official_eu_parakeet_manifest(models_dir: Path) -> dict | None:
    target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
    manifest_file = target_dir / "manifest.json"
    if not manifest_file.exists():
        return None
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def official_eu_parakeet_integrity_state(models_dir: Path) -> tuple[str, str | None]:
    target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
    target_file = target_dir / OFFICIAL_EU_PARAKEET_FILENAME
    if not target_file.exists():
        return "missing", None
    manifest = read_official_eu_parakeet_manifest(models_dir) or {}
    expected_sha = str(manifest.get("sha256", "") or "").strip().lower()
    if not expected_sha:
        return "checksum_unknown", None
    try:
        actual_sha = _sha256_file(target_file)
    except Exception as exc:
        return "corrupt", f"checksum read failed: {type(exc).__name__}: {exc}"
    if actual_sha != expected_sha:
        return "corrupt", "sha256 mismatch"
    return "valid", None


def ensure_official_eu_parakeet_model(
    models_dir: Path,
    *,
    progress_callback: ProgressCallback | None = None,
    max_attempts: int = 3,
) -> Path:
    target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / OFFICIAL_EU_PARAKEET_FILENAME
    manifest_file = target_dir / "manifest.json"

    if target_file.exists():
        integrity, _detail = official_eu_parakeet_integrity_state(models_dir)
        if integrity == "corrupt":
            corrupt_name = f"{target_file.stem}.corrupt.{int(time.time())}{target_file.suffix}"
            try:
                shutil.move(str(target_file), str(target_dir / corrupt_name))
            except Exception:
                try:
                    target_file.unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            return target_file

    with _MODEL_INSTALL_LOCK:
        if target_file.exists():
            return target_file

        max_attempts = max(1, int(max_attempts or 1))
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            with tempfile.NamedTemporaryFile(
                suffix=f".{OFFICIAL_EU_PARAKEET_FILENAME}.part",
                delete=False,
                dir=str(target_dir),
            ) as temp_file:
                temp_path = Path(temp_file.name)

            try:
                hasher = hashlib.sha256()
                request = urllib.request.Request(
                    OFFICIAL_EU_PARAKEET_URL,
                    headers={"User-Agent": "stream-sub-translator/1.0"},
                )
                attempt_suffix = f" (attempt {attempt}/{max_attempts})" if max_attempts > 1 else ""
                start_message = (
                    f"[asr-model] Downloading official model {OFFICIAL_EU_PARAKEET_REPO} "
                    f"to {target_file}{attempt_suffix}"
                )
                print(start_message)
                if progress_callback is not None:
                    progress_callback(start_message)
                with urllib.request.urlopen(request, timeout=120) as response, temp_path.open("wb") as file_handle:
                    total_bytes = int(response.headers.get("Content-Length", "0") or 0)
                    downloaded = 0
                    chunk_size = 1024 * 1024
                    last_reported_percent = -1
                    last_reported_mb = -1
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        hasher.update(chunk)
                        file_handle.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes > 0:
                            percent = downloaded * 100.0 / total_bytes
                            progress_percent = int(percent)
                            if progress_callback is not None and progress_percent != last_reported_percent:
                                last_reported_percent = progress_percent
                                progress_callback(
                                    f"Downloading Parakeet model... {percent:5.1f}% ({downloaded / (1024 * 1024):.0f} MB / {total_bytes / (1024 * 1024):.0f} MB)"
                                )
                        else:
                            downloaded_mb = downloaded // (1024 * 1024)
                            if progress_callback is not None and downloaded_mb != last_reported_mb:
                                last_reported_mb = downloaded_mb
                                progress_callback(f"Downloading Parakeet model... {downloaded_mb} MB")
                if progress_callback is not None:
                    progress_callback("Finalizing local Parakeet model files...")
                shutil.move(str(temp_path), str(target_file))
                sha256 = hasher.hexdigest()
                try:
                    size_bytes = int(target_file.stat().st_size)
                except Exception:
                    size_bytes = 0
                manifest = {
                    "repo_id": OFFICIAL_EU_PARAKEET_REPO,
                    "filename": OFFICIAL_EU_PARAKEET_FILENAME,
                    "revision": "main",
                    "sha256": sha256,
                    "size_bytes": size_bytes,
                    "downloaded_at_utc": _utc_now_iso(),
                    "local_path": str(target_file),
                    "download_url": OFFICIAL_EU_PARAKEET_URL,
                }
                manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[asr-model] Installed official model to {target_file}")
                if progress_callback is not None:
                    progress_callback("Parakeet model download completed.")
                return target_file
            except Exception as exc:
                last_error = exc
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                is_retryable_http = isinstance(exc, urllib.error.HTTPError) and exc.code in {408, 429, 500, 502, 503, 504}
                is_retryable_non_http = not isinstance(exc, urllib.error.HTTPError)
                should_retry = attempt < max_attempts and (is_retryable_http or is_retryable_non_http)
                if progress_callback is not None:
                    progress_callback(
                        f"Parakeet model download failed on attempt {attempt}/{max_attempts}: {type(exc).__name__}: {exc}"
                    )
                if should_retry:
                    retry_delay_seconds = min(6, 2 * attempt)
                    retry_message = f"Retrying the Parakeet model download in {retry_delay_seconds} seconds..."
                    print(f"[asr-model] {retry_message}")
                    if progress_callback is not None:
                        progress_callback(retry_message)
                    time.sleep(retry_delay_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error

__all__ = [
    "OFFICIAL_EU_PARAKEET_FILENAME",
    "OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME",
    "OFFICIAL_EU_PARAKEET_REPO",
    "OFFICIAL_EU_PARAKEET_URL",
    "ProgressCallback",
    "official_eu_parakeet_integrity_state",
    "read_official_eu_parakeet_manifest",
    "ensure_official_eu_parakeet_model",
]
