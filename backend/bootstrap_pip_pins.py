from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# omegaconf 2.3 (pulled by NeMo) requires antlr4-python3-runtime 4.9.*, but PyPI ships
# that line as sdist-only. Building the sdist on Windows is flaky (setuptools egg-info race,
# long paths, pip cache). Pre-install a vendored py3-none-any wheel before NeMo install.
ANTLR4_RUNTIME_VERSION = "4.9.3"
ANTLR4_RUNTIME_WHEEL_NAME = f"antlr4_python3_runtime-{ANTLR4_RUNTIME_VERSION}-py3-none-any.whl"
OFFLINE_PYTHON_WHEELS_DIR = Path("vendor") / "python-wheels"


def bundled_antlr4_wheel(bundle_root: Path) -> Path | None:
    wheel_path = bundle_root / OFFLINE_PYTHON_WHEELS_DIR / ANTLR4_RUNTIME_WHEEL_NAME
    if wheel_path.is_file():
        return wheel_path
    return None


def antlr4_runtime_satisfied(python_exe: Path) -> bool:
    if not python_exe.is_file():
        return False
    completed = subprocess.run(
        [
            str(python_exe),
            "-c",
            (
                "import importlib.metadata as m; "
                f"version = m.version('antlr4-python3-runtime'); "
                "major, minor, *_rest = version.split('.'); "
                "raise SystemExit(0 if major == '4' and minor == '9' else 1)"
            ),
        ],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.returncode == 0


def install_bundled_antlr4_runtime(
    *,
    python_exe: Path,
    bundle_root: Path,
    env: dict[str, str] | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    def emit(message: str) -> None:
        if log is not None:
            log(message)

    if antlr4_runtime_satisfied(python_exe):
        emit(f"[deps] antlr4-python3-runtime {ANTLR4_RUNTIME_VERSION} already available.")
        return

    wheel_path = bundled_antlr4_wheel(bundle_root)
    if wheel_path is None:
        raise RuntimeError(
            f"Missing bundled antlr4 wheel under {bundle_root / OFFLINE_PYTHON_WHEELS_DIR}. "
            "NeMo install on Windows requires the vendored wheel."
        )

    emit(f"[deps] Installing bundled antlr4-python3-runtime wheel: {wheel_path.name}")
    completed = subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--no-cache-dir",
            str(wheel_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        detail = (completed.stdout or completed.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit code {completed.returncode}"
        raise RuntimeError(f"Bundled antlr4-python3-runtime install failed. {tail}")
    if not antlr4_runtime_satisfied(python_exe):
        raise RuntimeError(
            f"Bundled antlr4-python3-runtime install finished, but {ANTLR4_RUNTIME_VERSION} is still missing."
        )
    emit(f"[deps] Bundled antlr4-python3-runtime {ANTLR4_RUNTIME_VERSION} installed.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install vendored bootstrap pip pins.")
    parser.add_argument(
        "--python",
        required=True,
        type=Path,
        help="Python executable to install into.",
    )
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Root containing vendor/python-wheels.",
    )
    parser.add_argument(
        "--refresh-wheel",
        action="store_true",
        help="Rebuild and copy the antlr4 wheel into vendor/python-wheels (maintainers only).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    bundle_root = args.bundle_root.resolve()
    if args.refresh_wheel:
        output_dir = bundle_root / ".tmp" / "wheel-build"
        output_dir.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                str(args.python),
                "-m",
                "pip",
                "wheel",
                f"antlr4-python3-runtime=={ANTLR4_RUNTIME_VERSION}",
                "--no-deps",
                "-w",
                str(output_dir),
            ],
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
        source = output_dir / ANTLR4_RUNTIME_WHEEL_NAME
        if not source.is_file():
            print(f"Wheel build did not produce {source}", file=sys.stderr)
            return 1
        destination_dir = bundle_root / OFFLINE_PYTHON_WHEELS_DIR
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / ANTLR4_RUNTIME_WHEEL_NAME
        destination.write_bytes(source.read_bytes())
        print(json.dumps({"wheel": str(destination), "bytes": destination.stat().st_size}))
        return 0

    install_bundled_antlr4_runtime(
        python_exe=args.python.resolve(),
        bundle_root=bundle_root,
        log=print,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
