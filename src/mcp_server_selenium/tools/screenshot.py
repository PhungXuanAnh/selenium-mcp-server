import logging
from pathlib import Path
import re

from ..server import (
    auto_recover_stale_window,
    ensure_driver_initialized,
    get_workspace_root,
    mcp,
)

logger = logging.getLogger(__name__)

DEFAULT_SCREENSHOT_DIRECTORY = "tmp/selenium-screenshot"
_SAFE_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _normalize_file_name(file_name: str) -> str:
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("file_name must be a non-empty descriptive PNG filename")

    normalized = file_name.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise ValueError("file_name must be a basename and cannot contain path traversal")

    suffix = Path(normalized).suffix
    if suffix and suffix.lower() != ".png":
        raise ValueError("file_name must use the .png extension")
    if suffix:
        normalized = f"{normalized[:-len(suffix)]}.png"
    else:
        normalized = f"{normalized}.png"

    if not _SAFE_FILE_NAME.fullmatch(normalized):
        raise ValueError(
            "file_name must start with a letter or number and contain only "
            "letters, numbers, dots, hyphens, and underscores"
        )
    return normalized


def _resolve_screenshot_directory(directory: str) -> Path:
    if not isinstance(directory, str) or not directory.strip():
        raise ValueError("directory must be a non-empty path")
    if "\\" in directory:
        raise ValueError("directory must use POSIX path separators")

    requested_directory = Path(directory.strip()).expanduser()
    if requested_directory.is_absolute():
        return requested_directory.resolve()
    if ".." in requested_directory.parts:
        raise ValueError("relative directory cannot contain path traversal")

    workspace_root = get_workspace_root()
    return (workspace_root / requested_directory).resolve()


def _next_available_path(directory: Path, file_name: str) -> Path:
    candidate = directory / file_name
    counter = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = directory / f"{Path(file_name).stem}-{counter}.png"
        counter += 1
    return candidate


def prepare_screenshot_path(file_name: str, directory: str) -> Path:
    """Validate artifact inputs and reserve the next non-colliding PNG path."""
    normalized_file_name = _normalize_file_name(file_name)
    screenshot_directory = _resolve_screenshot_directory(directory)
    screenshot_directory.mkdir(parents=True, exist_ok=True)
    return _next_available_path(screenshot_directory, normalized_file_name)


@mcp.tool(description="Save the active tab as a uniquely named PNG. Choose a semantic file_name. Prefer an absolute directory inside your current workspace; otherwise omit directory for the configured default.")
@auto_recover_stale_window
def take_screenshot(
    file_name: str,
    directory: str = DEFAULT_SCREENSHOT_DIRECTORY,
) -> str:
    """Take a screenshot of the current browser window.

    Always choose a short, descriptive file_name for the page or state being captured,
    such as ``checkout-error``. Prefer an absolute directory inside your current
    workspace when you know its path; this avoids ambiguity about the MCP server's
    working directory. Otherwise omit directory to use the configured workspace default.
    Existing artifacts are preserved by adding a numeric suffix.

    Args:
        file_name: Required safe basename chosen by the caller. ``.png`` is added when
            omitted. Paths, traversal, and non-PNG extensions are rejected.
        directory: Optional output directory. Prefer an absolute path inside the current
            workspace when known. If omitted, defaults to the workspace-relative
            ``tmp/selenium-screenshot``. Traversal in relative paths is rejected.

    Returns:
        The path to the saved screenshot file.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    screenshot_path = prepare_screenshot_path(file_name, directory)
    driver.save_screenshot(str(screenshot_path))

    return f"Screenshot saved to {screenshot_path}"
