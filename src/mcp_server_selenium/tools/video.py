"""Legacy MCP wrapper for tab video recording."""

from typing import Literal

from ..server import ensure_driver_initialized, mcp
from .video_recording import (
    DEFAULT_MAX_DURATION_SECONDS,
    DEFAULT_VIDEO_DIRECTORY,
    record_video_json,
)


@mcp.tool(
    description="start requires file_name; window_handle records one fixed tab, while window_handles selects 2-4 tabs for one MP4 that follows tabs/switch_tab. max_duration_seconds auto-finalizes. Always stop after the final action. Paths match screenshot; address is synthetic. Sensitive."
)
def record_video(
    action: Literal["start", "stop", "status"],
    file_name: str = "",
    directory: str = DEFAULT_VIDEO_DIRECTORY,
    include_address: bool = False,
    window_handle: str = "",
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    window_handles: list[str] = [],
) -> str:
    """Start, stop, or inspect one fixed tab or one follow-active tab flow."""
    driver = ensure_driver_initialized() if action == "start" else None
    return record_video_json(
        driver,
        action,
        file_name,
        directory,
        include_address,
        window_handle,
        max_duration_seconds,
        window_handles,
    )
