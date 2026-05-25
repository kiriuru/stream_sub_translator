from __future__ import annotations

import unittest

from backend.core.http_api_trace_middleware import _should_log_http_path


class HttpApiTraceMiddlewareTests(unittest.TestCase):
    def test_logs_api_and_dashboard_paths(self) -> None:
        self.assertTrue(_should_log_http_path("/api/health"))
        self.assertTrue(_should_log_http_path("/"))
        self.assertTrue(_should_log_http_path("/overlay"))

    def test_skips_static_assets_by_default(self) -> None:
        self.assertFalse(_should_log_http_path("/static/js/main.js"))


if __name__ == "__main__":
    unittest.main()
