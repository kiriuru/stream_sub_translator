from backend.core.paths import APP_PATHS, AppPaths, DESKTOP_USER_DATA_DIRNAME, detect_app_paths, ensure_app_layout

RuntimePaths = AppPaths
detect_runtime_paths = detect_app_paths
RUNTIME_PATHS = APP_PATHS


def ensure_runtime_layout(paths: RuntimePaths | None = None) -> RuntimePaths:
    return ensure_app_layout(paths)
