"""Runtime tab and browser metadata for the compact profile."""

import json

from ..server import get_download_directory
from .compact_waits import page_snapshot


def _tab_snapshot(driver, handle: str, active_handle: str) -> dict:
    snapshot = page_snapshot(driver)
    return {
        "handle": handle,
        "active": handle == active_handle,
        "title": driver.title,
        "url": snapshot["url"],
        "ready_state": snapshot["ready_state"],
    }


def list_tabs_result(driver) -> dict:
    active_handle = driver.current_window_handle
    tabs = []
    try:
        for handle in list(driver.window_handles):
            driver.switch_to.window(handle)
            tabs.append(_tab_snapshot(driver, handle, active_handle))
    finally:
        if active_handle in driver.window_handles:
            driver.switch_to.window(active_handle)

    capabilities = getattr(driver, "capabilities", {}) or {}
    chrome = capabilities.get("chrome", {}) or {}
    return {
        "ok": True,
        "active_handle": active_handle,
        "tabs": tabs,
        "browser": {
            "name": capabilities.get("browserName", "chrome"),
            "version": capabilities.get("browserVersion", "unknown"),
            "driver_version": str(chrome.get("chromedriverVersion", "unknown")).split()[0],
            "platform": capabilities.get("platformName", "unknown"),
        },
        "download_directory": str(get_download_directory()),
    }


def list_tabs_json(driver) -> str:
    return json.dumps(list_tabs_result(driver), ensure_ascii=False)
