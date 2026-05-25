from __future__ import annotations

import sys

from desktop.bootstrap_launcher import BootstrapLauncher, _parse_args, main as bootstrap_main


class WebOnlyBootstrapLauncher(BootstrapLauncher):
    def _launch_runtime(self, *extra_args: str) -> None:
        forwarded = tuple(extra_args)
        if "--web-speech-only" not in forwarded:
            forwarded = ("--web-speech-only", *forwarded)
        super()._launch_runtime(*forwarded)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return WebOnlyBootstrapLauncher().run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
