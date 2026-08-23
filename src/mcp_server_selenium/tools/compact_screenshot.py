"""Viewport, full-page, and element captures for the compact profile."""

import base64
import json

from .compact_locator import LocatorReferenceError, resolved_element
from .screenshot import prepare_screenshot_path

_MODES = {"viewport", "full_page", "element"}
_MAX_FULL_PAGE_PIXELS = 100_000_000
_MAX_FULL_PAGE_DIMENSION = 32_767


def _capture_full_page(driver, path) -> None:
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
    width = float(size.get("width", 0))
    height = float(size.get("height", 0))
    if width <= 0 or height <= 0:
        raise RuntimeError("Chrome did not report a positive full-page content size")
    if (
        width > _MAX_FULL_PAGE_DIMENSION
        or height > _MAX_FULL_PAGE_DIMENSION
        or width * height > _MAX_FULL_PAGE_PIXELS
    ):
        raise ValueError(
            f"Full page is too large to capture safely ({int(width)}x{int(height)})"
        )
    result = driver.execute_cdp_cmd(
        "Page.captureScreenshot",
        {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
        },
    )
    data = result.get("data", "")
    if not data:
        raise RuntimeError("Chrome returned an empty full-page screenshot")
    path.write_bytes(base64.b64decode(data, validate=True))


def screenshot_result(
    driver,
    file_name: str,
    directory: str,
    mode: str = "viewport",
    element_ref: str = "",
) -> dict:
    if mode not in _MODES:
        return {
            "ok": False,
            "mode": mode,
            "error": {
                "code": "invalid_screenshot",
                "message": "mode must be viewport, full_page, or element",
            },
        }
    if mode == "element" and not element_ref:
        return {
            "ok": False,
            "mode": mode,
            "error": {
                "code": "element_ref_required",
                "message": "element_ref from query_elements is required for element mode",
            },
        }
    try:
        path = prepare_screenshot_path(file_name, directory)
        if mode == "viewport":
            if driver.save_screenshot(str(path)) is False:
                raise RuntimeError("WebDriver reported that viewport capture failed")
        elif mode == "full_page":
            _capture_full_page(driver, path)
        else:
            with resolved_element(driver, element_ref) as element:
                if element.screenshot(str(path)) is False:
                    raise RuntimeError("WebElement reported that element capture failed")
        return {
            "ok": True,
            "mode": mode,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sensitive_data_warning": "Screenshots may contain credentials, PHI, or other sensitive page data.",
        }
    except LocatorReferenceError as exc:
        return {
            "ok": False,
            "mode": mode,
            "error": {"code": exc.code, "message": str(exc)},
        }
    except Exception as exc:
        return {
            "ok": False,
            "mode": mode,
            "error": {"code": "screenshot_failed", "message": str(exc)},
        }


def screenshot_json(driver, *args, **kwargs) -> str:
    return json.dumps(screenshot_result(driver, *args, **kwargs), ensure_ascii=False)
