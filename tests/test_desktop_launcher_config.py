from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from desktop.launcher import (
    DESKTOP_PROFILE_LOCK_BROWSER_SPEECH,
    LAUNCH_OPTION_CPU,
    LAUNCH_OPTION_NVIDIA,
    STARTUP_MODE_BROWSER,
    STARTUP_MODE_LOCAL,
    DesktopLauncher,
    _load_worker_launch_browser_preference,
    _load_saved_asr_mode,
    _read_install_profile,
    _load_profile_name,
)
from desktop.runtime_bootstrap import detect_runtime_paths


def _build_launcher_with_fake_paths(tmp_root: Path) -> DesktopLauncher:
    real_paths = detect_runtime_paths()
    fake_project = tmp_root / "project"
    fake_data = fake_project / "user-data"
    fake_logs = fake_project / "logs"
    fake_runtime = tmp_root / "runtime"
    fake_paths = replace(
        real_paths,
        project_root=fake_project,
        data_dir=fake_data,
        logs_dir=fake_logs,
        runtime_root=fake_runtime,
        cache_root=fake_runtime / "cache",
        temp_root=fake_runtime / "tmp",
        fonts_dir=fake_project / "fonts",
        install_profile_file=fake_data / "install_profile.txt",
    )
    fake_data.mkdir(parents=True, exist_ok=True)
    fake_logs.mkdir(parents=True, exist_ok=True)
    fake_runtime.mkdir(parents=True, exist_ok=True)
    with patch("desktop.launcher.detect_runtime_paths", return_value=fake_paths):
        launcher = DesktopLauncher(debug_webview=False, web_speech_only=False)
    return launcher


class WorkerLaunchBrowserPreferenceTests(unittest.TestCase):
    def test_returns_default_when_config_missing(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            self.assertEqual(_load_worker_launch_browser_preference(cfg), "auto")

    def test_returns_default_on_invalid_json(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text("{ not json", encoding="utf-8")
            self.assertEqual(_load_worker_launch_browser_preference(cfg), "auto")

    def test_chromium_maps_to_auto(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text(json.dumps({"asr": {"browser": {"worker_launch_browser": "chromium"}}}), encoding="utf-8")
            self.assertEqual(_load_worker_launch_browser_preference(cfg), "auto")

    def test_microsoft_edge_maps_to_google_chrome(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text(json.dumps({"asr": {"browser": {"worker_launch_browser": "microsoft_edge"}}}), encoding="utf-8")
            self.assertEqual(_load_worker_launch_browser_preference(cfg), "google_chrome")

    def test_keeps_known_values(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text(json.dumps({"asr": {"browser": {"worker_launch_browser": "google_chrome"}}}), encoding="utf-8")
            self.assertEqual(_load_worker_launch_browser_preference(cfg), "google_chrome")


class SavedAsrModeAndProfileTests(unittest.TestCase):
    def test_defaults_when_missing(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            self.assertEqual(_load_saved_asr_mode(cfg), STARTUP_MODE_LOCAL)
            self.assertEqual(_load_profile_name(cfg), "default")
            self.assertEqual(_read_install_profile(Path(raw) / "install_profile.txt"), "auto")

    def test_reads_persisted_values(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text(
                json.dumps({"asr": {"mode": "browser_google"}, "profile": "streamA"}),
                encoding="utf-8",
            )
            self.assertEqual(_load_saved_asr_mode(cfg), STARTUP_MODE_BROWSER)
            self.assertEqual(_load_profile_name(cfg), "streamA")

    def test_ignores_unknown_asr_mode(self) -> None:
        with TemporaryDirectory() as raw:
            cfg = Path(raw) / "config.json"
            cfg.write_text(json.dumps({"asr": {"mode": "remote_only"}}), encoding="utf-8")
            self.assertEqual(_load_saved_asr_mode(cfg), STARTUP_MODE_LOCAL)


class ApplyStartupModeToConfigTests(unittest.TestCase):
    def test_browser_mode_sets_desktop_profile_lock(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(STARTUP_MODE_BROWSER, install_profile=None)
            cfg_path = launcher._paths.data_dir / "config.json"
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["asr"]["mode"], STARTUP_MODE_BROWSER)
            self.assertEqual(payload["asr"]["desktop_profile_lock"], DESKTOP_PROFILE_LOCK_BROWSER_SPEECH)
            self.assertEqual(payload["remote"]["role"], "disabled")
            self.assertFalse(payload["remote"]["enabled"])
            self.assertFalse(payload["remote"]["lan"]["bind_enabled"])

    def test_local_mode_builds_default_config_when_missing(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(STARTUP_MODE_LOCAL, install_profile=LAUNCH_OPTION_NVIDIA)
            payload = json.loads((launcher._paths.data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("asr"), dict)
            self.assertEqual(payload["asr"]["mode"], STARTUP_MODE_LOCAL)
            self.assertTrue(payload["asr"]["prefer_gpu"])

    def test_local_mode_clears_profile_lock_and_sets_gpu(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._paths.data_dir.mkdir(parents=True, exist_ok=True)
            cfg_path = launcher._paths.data_dir / "config.json"
            cfg_path.write_text(
                json.dumps({"asr": {"desktop_profile_lock": DESKTOP_PROFILE_LOCK_BROWSER_SPEECH}}),
                encoding="utf-8",
            )

            launcher._apply_startup_mode_to_config(STARTUP_MODE_LOCAL, install_profile=LAUNCH_OPTION_NVIDIA)
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["asr"]["mode"], STARTUP_MODE_LOCAL)
            self.assertNotIn("desktop_profile_lock", payload["asr"])
            self.assertTrue(payload["asr"]["prefer_gpu"])

    def test_cpu_profile_clears_prefer_gpu(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(STARTUP_MODE_LOCAL, install_profile=LAUNCH_OPTION_CPU)
            cfg_path = launcher._paths.data_dir / "config.json"
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["asr"]["prefer_gpu"])

    def test_remote_controller_enables_remote_without_lan_bind(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(
                STARTUP_MODE_LOCAL,
                install_profile=None,
                remote_role="controller",
                allow_lan=False,
            )
            payload = json.loads((launcher._paths.data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["remote"]["role"], "controller")
            self.assertTrue(payload["remote"]["enabled"])
            self.assertFalse(payload["remote"]["lan"]["bind_enabled"])

    def test_remote_worker_with_lan_bind(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(
                STARTUP_MODE_LOCAL,
                install_profile=LAUNCH_OPTION_CPU,
                remote_role="worker",
                allow_lan=True,
            )
            payload = json.loads((launcher._paths.data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["remote"]["role"], "worker")
            self.assertTrue(payload["remote"]["enabled"])
            self.assertTrue(payload["remote"]["lan"]["bind_enabled"])

    def test_invalid_remote_role_falls_back_to_disabled(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._apply_startup_mode_to_config(
                STARTUP_MODE_LOCAL,
                install_profile=None,
                remote_role="bogus-value",
                allow_lan=True,
            )
            payload = json.loads((launcher._paths.data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["remote"]["role"], "disabled")
            self.assertFalse(payload["remote"]["enabled"])
            self.assertTrue(payload["remote"]["lan"]["bind_enabled"])

    def test_web_speech_only_locks_to_browser_profile_in_local_mode(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            launcher._web_speech_only = True
            launcher._apply_startup_mode_to_config(STARTUP_MODE_LOCAL, install_profile=LAUNCH_OPTION_CPU)
            payload = json.loads((launcher._paths.data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["asr"]["desktop_profile_lock"], DESKTOP_PROFILE_LOCK_BROWSER_SPEECH)


class LogRotationTests(unittest.TestCase):
    def test_log_file_archives_previous_run(self) -> None:
        with TemporaryDirectory() as raw:
            log_path = Path(raw) / "desktop-launcher.log"
            log_path.write_text("prior run", encoding="utf-8")
            DesktopLauncher._rotate_log_file(log_path)
            archive = log_path.with_name("desktop-launcher.old.log")
            self.assertTrue(archive.exists())
            self.assertEqual(archive.read_text(encoding="utf-8"), "prior run")
            self.assertTrue(log_path.exists())
            self.assertEqual(log_path.read_text(encoding="utf-8"), "")

    def test_rotation_overwrites_existing_archive(self) -> None:
        with TemporaryDirectory() as raw:
            log_path = Path(raw) / "desktop-launcher.log"
            log_path.write_text("second run", encoding="utf-8")
            archive = log_path.with_name("desktop-launcher.old.log")
            archive.write_text("first archive", encoding="utf-8")
            DesktopLauncher._rotate_log_file(log_path)
            self.assertEqual(archive.read_text(encoding="utf-8"), "second run")
            self.assertEqual(log_path.read_text(encoding="utf-8"), "")

    def test_launcher_does_not_create_legacy_channel_log_files(self) -> None:
        with TemporaryDirectory() as raw:
            launcher = _build_launcher_with_fake_paths(Path(raw))
            logs_dir = launcher._paths.logs_dir
            self.assertTrue((logs_dir / "desktop-launcher.log").exists())
            for stem in DesktopLauncher._LEGACY_EMPTY_CHANNEL_LOG_STEMS:
                self.assertFalse((logs_dir / f"{stem}.log").exists(), stem)
                self.assertFalse((logs_dir / f"{stem}.old.log").exists(), stem)

    def test_launcher_removes_empty_legacy_channel_logs(self) -> None:
        with TemporaryDirectory() as raw:
            logs_dir = Path(raw) / "project" / "logs"
            logs_dir.mkdir(parents=True)
            stale = logs_dir / "overlay-events.log"
            stale.write_text("", encoding="utf-8")
            _build_launcher_with_fake_paths(Path(raw))
            self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
