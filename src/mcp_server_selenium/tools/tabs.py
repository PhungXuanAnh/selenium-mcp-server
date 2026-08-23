import json
from typing import Optional

from ..server import auto_recover_stale_window, ensure_driver_initialized, mcp


def _current_tab(driver) -> dict[str, object]:
    """Return serializable metadata for the driver's current tab."""
    return {
        "handle": driver.current_window_handle,
        "title": driver.title,
        "url": driver.current_url,
    }


@mcp.tool(description="List all tabs and the active handle without changing the final active tab. Serialize tab-sensitive calls in this server session.")
@auto_recover_stale_window
def list_tabs() -> str:
    """List all browser tabs and identify the currently active tab.

    This inspection preserves the active tab. Use a returned handle with ``switch_tab``
    before running browser tools against another tab. Do not overlap this call with
    other tab-sensitive browser tool calls in the same server session.

    Returns:
        A JSON object containing the active tab handle and metadata for every tab.
    """
    driver = ensure_driver_initialized()
    active_handle = driver.current_window_handle
    tabs = []

    try:
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            tab = _current_tab(driver)
            tab["active"] = handle == active_handle
            tabs.append(tab)
    finally:
        if active_handle in driver.window_handles:
            driver.switch_to.window(active_handle)

    return json.dumps({"active_handle": active_handle, "tabs": tabs}, indent=2)


@mcp.tool(description="Open and activate a new tab, optionally loading a URL. Serialize tab-sensitive calls in this server session.")
@auto_recover_stale_window
def open_tab(url: Optional[str] = None) -> str:
    """Open a new browser tab and optionally navigate it to a URL.

    The new tab becomes active, so later browser tools operate on it until another tab
    is selected. Do not overlap this call with other tab-sensitive browser tool calls
    in the same server session.

    Args:
        url: Optional URL to load in the new tab. If omitted, the tab remains blank.

    Returns:
        A JSON object describing the new active tab.
    """
    driver = ensure_driver_initialized()
    driver.switch_to.new_window("tab")

    if url:
        if not url.startswith(("http://", "https://", "about:", "data:", "file:", "chrome:")):
            url = "https://" + url
        driver.get(url)

    return json.dumps(_current_tab(driver), indent=2)


@mcp.tool(description="Activate a tab by a handle from list_tabs. Serialize the switch and dependent calls in this server session.")
@auto_recover_stale_window
def switch_tab(handle: str) -> str:
    """Switch to an existing browser tab by its window handle.

    Every later browser tool operates on the selected tab until another tab is opened,
    selected, or the active tab is closed. Serialize the switch and dependent tool
    calls; do not run tab-sensitive calls concurrently in the same server session.

    Args:
        handle: A window handle returned by ``list_tabs``.

    Returns:
        A JSON object describing the newly active tab.
    """
    driver = ensure_driver_initialized()
    if handle not in driver.window_handles:
        raise ValueError(f"Unknown tab handle: {handle}")

    driver.switch_to.window(handle)
    return json.dumps(_current_tab(driver), indent=2)


@mcp.tool(description="Close a chosen or active tab and activate a remaining tab. The final tab cannot be closed; serialize tab-sensitive calls.")
@auto_recover_stale_window
def close_tab(handle: Optional[str] = None) -> str:
    """Close a browser tab while keeping another tab active.

    The returned ``active_tab`` is the context used by later browser tools. Serialize
    this call with other tab-sensitive browser calls in the same server session.

    Args:
        handle: Optional handle of the tab to close. Defaults to the active tab.

    Returns:
        A JSON object containing the closed handle and the remaining active tab.

    Raises:
        ValueError: If the handle is unknown or it is the browser's final tab.
    """
    driver = ensure_driver_initialized()
    handles = list(driver.window_handles)
    if len(handles) <= 1:
        raise ValueError("Cannot close the final browser tab")

    active_handle = driver.current_window_handle
    target_handle = handle or active_handle
    if target_handle not in handles:
        raise ValueError(f"Unknown tab handle: {target_handle}")

    driver.switch_to.window(target_handle)
    driver.close()

    remaining_handles = list(driver.window_handles)
    if active_handle != target_handle and active_handle in remaining_handles:
        next_handle = active_handle
    else:
        next_handle = remaining_handles[-1]
    driver.switch_to.window(next_handle)

    return json.dumps(
        {
            "closed_handle": target_handle,
            "active_tab": _current_tab(driver),
            "remaining_handles": remaining_handles,
        },
        indent=2,
    )
