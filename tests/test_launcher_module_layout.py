from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"


class LauncherModuleLayoutTests(unittest.TestCase):
    def test_split_modules_exist(self) -> None:
        for name in (
            "launcher_context.py",
            "launcher_api.py",
            "launcher_bootstrap.py",
            "launcher_window.py",
            "launcher_backend.py",
            "browser_worker_launcher.py",
            "launcher.py",
        ):
            self.assertTrue((DESKTOP_ROOT / name).exists(), msg=name)

    def test_launcher_py_is_thin_facade(self) -> None:
        source = (DESKTOP_ROOT / "launcher.py").read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 40)
        self.assertIn("launcher_bootstrap", source)
        self.assertNotIn("class DesktopLauncher", source)
        self.assertIn('if __name__ == "__main__":', source)
        self.assertIn("main()", source)

    def test_launcher_re_exports_context_helpers(self) -> None:
        import desktop.launcher as launcher_module

        self.assertTrue(hasattr(launcher_module, "_load_worker_launch_browser_preference"))
        self.assertTrue(hasattr(launcher_module, "_is_port_in_use"))
        self.assertTrue(hasattr(launcher_module, "DesktopApi"))
        self.assertTrue(hasattr(launcher_module, "DesktopLauncher"))

    def test_desktop_launcher_uses_window_and_backend_mixins(self) -> None:
        from desktop.launcher_bootstrap import DesktopLauncher
        from desktop.launcher_backend import LauncherBackendMixin
        from desktop.launcher_window import LauncherWindowMixin

        self.assertTrue(issubclass(DesktopLauncher, LauncherWindowMixin))
        self.assertTrue(issubclass(DesktopLauncher, LauncherBackendMixin))

    def test_splash_ru_i18n_is_valid_utf8_cyrillic(self) -> None:
        from desktop.launcher_context import _SPLASH_I18N

        ru = _SPLASH_I18N["ru"]
        self.assertIn("Запуск desktop", ru["launcher.eyebrow"])
        for key, value in ru.items():
            self.assertNotIn("╨", value, msg=f"mojibake in ru string {key!r}")
            self.assertNotIn("тАФ", value, msg=f"broken dash encoding in ru string {key!r}")


if __name__ == "__main__":
    unittest.main()
