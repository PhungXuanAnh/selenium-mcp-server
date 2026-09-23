"""Runtime tab and browser metadata for the compact profile."""

import json
import logging

from ..server import get_download_directory
from .compact_waits import page_snapshot
from .tabs import page_targets
from .video_recording import _DevToolsConnection

logger = logging.getLogger(__name__)


def _background_ready_states(driver, handles: list[str]) -> dict[str, str]:
    """Read ``document.readyState`` of background tabs without activating them."""
    if not handles:
        return {}
    capabilities = getattr(driver, "capabilities", {}) or {}
    address = (capabilities.get("goog:chromeOptions") or {}).get("debuggerAddress", "")
    if not address:
        return {}
    states = {}
    try:
        connection = _DevToolsConnection(str(address), lambda message: None)
    except Exception:
        logger.debug("Could not open DevTools connection for tab states", exc_info=True)
        return {}
    try:
        for handle in handles:
            try:
                session = connection.command(
                    "Target.attachToTarget",
                    {"targetId": handle, "flatten": True},
                    timeout=5,
                )["sessionId"]
                evaluated = connection.command(
                    "Runtime.evaluate",
                    {"expression": "document.readyState", "returnByValue": True},
                    session_id=session,
                    timeout=5,
                )
                states[handle] = str(evaluated["result"]["value"])
                connection.command(
                    "Target.detachFromTarget", {"sessionId": session}, timeout=5
                )
            except Exception:
                logger.debug("Could not read readyState of tab %s", handle, exc_info=True)
    finally:
        connection.close()
    return states


def list_tabs_result(driver) -> dict:
    active_handle = driver.current_window_handle
    handles = list(driver.window_handles)
    targets = page_targets(driver)
    background_states = _background_ready_states(
        driver, [handle for handle in handles if handle != active_handle]
    )
    tabs = []
    for handle in handles:
        if handle == active_handle:
            snapshot = page_snapshot(driver)
            title, url, ready_state = driver.title, snapshot["url"], snapshot["ready_state"]
        else:
            target = targets.get(handle, {})
            title, url = target.get("title", ""), target.get("url", "")
            ready_state = background_states.get(handle, "unknown")
        tabs.append(
            {
                "handle": handle,
                "active": handle == active_handle,
                "title": title,
                "url": url,
                "ready_state": ready_state,
            }
        )

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
