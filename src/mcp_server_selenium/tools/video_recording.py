"""Stateful, tab-bound Chrome video recording support."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Optional
import urllib.request

from .screenshot import _resolve_screenshot_directory

logger = logging.getLogger(__name__)

DEFAULT_VIDEO_DIRECTORY = "tmp/selenium-video"
DEFAULT_MAX_DURATION_SECONDS = 600.0
MIN_MAX_DURATION_SECONDS = 0.1
MAX_MAX_DURATION_SECONDS = 86400.0
MAX_FLOW_TABS = 4
_SAFE_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_READ_CHUNK_SIZE = 1024 * 1024


class DevToolsCommandError(RuntimeError):
    """A structured Chrome DevTools command failure."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class UnsupportedRecordingError(RuntimeError):
    """Neither the native nor compatibility recording transport can start."""


def _normalize_video_file_name(file_name: str) -> str:
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("file_name must be a non-empty descriptive MP4 filename")

    normalized = file_name.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise ValueError("file_name must be a basename and cannot contain path traversal")

    suffix = Path(normalized).suffix
    if suffix and suffix.lower() != ".mp4":
        raise ValueError("file_name must use the .mp4 extension")
    if suffix:
        normalized = f"{normalized[:-len(suffix)]}.mp4"
    else:
        normalized = f"{normalized}.mp4"

    if not _SAFE_FILE_NAME.fullmatch(normalized):
        raise ValueError(
            "file_name must start with a letter or number and contain only "
            "letters, numbers, dots, hyphens, and underscores"
        )
    return normalized


def _partial_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.part")


def prepare_video_path(file_name: str, directory: str) -> Path:
    """Validate inputs and select a non-colliding MP4 destination."""
    normalized = _normalize_video_file_name(file_name)
    video_directory = _resolve_screenshot_directory(directory)
    video_directory.mkdir(parents=True, exist_ok=True)

    candidate = video_directory / normalized
    counter = 2
    while (
        candidate.exists()
        or candidate.is_symlink()
        or _partial_path(candidate).exists()
        or _partial_path(candidate).is_symlink()
    ):
        candidate = video_directory / f"{Path(normalized).stem}-{counter}.mp4"
        counter += 1
    return candidate


def _normalize_max_duration(max_duration_seconds: float) -> float:
    if isinstance(max_duration_seconds, bool):
        raise ValueError("max_duration_seconds must be a finite number")
    try:
        value = float(max_duration_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_duration_seconds must be a finite number") from exc
    if not math.isfinite(value):
        raise ValueError("max_duration_seconds must be a finite number")
    if not MIN_MAX_DURATION_SECONDS <= value <= MAX_MAX_DURATION_SECONDS:
        raise ValueError(
            "max_duration_seconds must be between 0.1 and 86400 seconds"
        )
    return value


class _DevToolsConnection:
    """One browser-level WebSocket with flattened target sessions."""

    def __init__(
        self,
        debugger_address: str,
        event_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        from websocket import (
            WebSocketConnectionClosedException,
            WebSocketTimeoutException,
            create_connection,
        )

        with urllib.request.urlopen(
            f"http://{debugger_address}/json/version", timeout=5
        ) as response:
            version = json.loads(response.read())
        websocket_url = version.get("webSocketDebuggerUrl")
        if not websocket_url:
            raise RuntimeError("Chrome did not expose a browser DevTools WebSocket")

        self._timeout_error = WebSocketTimeoutException
        self._closed_error = WebSocketConnectionClosedException
        self._event_callback = event_callback
        self._condition = threading.Condition()
        self._send_lock = threading.Lock()
        self._responses: dict[int, dict[str, Any]] = {}
        self._ignored_ids: set[int] = set()
        self._next_id = 1
        self._reader_error: Optional[BaseException] = None
        self._closed = threading.Event()
        self._ws = create_connection(
            websocket_url,
            timeout=5,
            origin=f"http://{debugger_address}",
        )
        self._ws.settimeout(0.5)
        self._reader = threading.Thread(
            target=self._read_loop,
            name="selenium-video-devtools",
            daemon=True,
        )
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._closed.is_set():
            try:
                raw_message = self._ws.recv()
            except self._timeout_error:
                continue
            except self._closed_error as exc:
                if not self._closed.is_set():
                    self._set_reader_error(exc)
                return
            except BaseException as exc:  # reader failures must wake command waiters
                if not self._closed.is_set():
                    self._set_reader_error(exc)
                return

            if not raw_message:
                continue
            try:
                message = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                logger.warning("Ignoring malformed DevTools WebSocket message")
                continue

            command_id = message.get("id")
            if isinstance(command_id, int):
                with self._condition:
                    if command_id in self._ignored_ids:
                        self._ignored_ids.remove(command_id)
                        continue
                    self._responses[command_id] = message
                    self._condition.notify_all()
                continue
            try:
                self._event_callback(message)
            except Exception:
                logger.exception("Video recorder event callback failed")

    def _set_reader_error(self, error: BaseException) -> None:
        with self._condition:
            self._reader_error = error
            self._condition.notify_all()

    def command(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        session_id: str = "",
        timeout: float = 30,
    ) -> dict[str, Any]:
        with self._condition:
            command_id = self._next_id
            self._next_id += 1

        payload: dict[str, Any] = {
            "id": command_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            payload["sessionId"] = session_id

        with self._send_lock:
            self._ws.send(json.dumps(payload, separators=(",", ":")))

        deadline = time.monotonic() + timeout
        with self._condition:
            while command_id not in self._responses:
                if self._reader_error is not None:
                    raise RuntimeError(
                        f"DevTools connection closed: {self._reader_error}"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Timed out waiting for {method}")
                self._condition.wait(remaining)
            response = self._responses.pop(command_id)

        error = response.get("error")
        if error:
            raise DevToolsCommandError(
                int(error.get("code", 0)), str(error.get("message", "DevTools error"))
            )
        return dict(response.get("result") or {})

    def send_no_wait(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        session_id: str = "",
    ) -> None:
        """Send a command from the reader callback without blocking that reader."""
        with self._condition:
            command_id = self._next_id
            self._next_id += 1
            self._ignored_ids.add(command_id)
        payload: dict[str, Any] = {
            "id": command_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            payload["sessionId"] = session_id
        with self._send_lock:
            self._ws.send(json.dumps(payload, separators=(",", ":")))

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._ws.close()
        finally:
            if threading.current_thread() is not self._reader:
                self._reader.join(timeout=2)


@dataclass
class _ActiveRecording:
    connection: Any
    session_id: str
    start_stream: str
    handle: str
    start_url: str
    browser_version: str
    include_address: bool
    final_path: Path
    partial_path: Path
    started_at: str
    started_monotonic: float
    main_frame_id: str = ""
    timeline: list[tuple[float, str]] = field(default_factory=list)
    timeline_lock: threading.Lock = field(default_factory=threading.Lock)
    target_closed: threading.Event = field(default_factory=threading.Event)
    transport: str = "native"
    encoder_state: Optional[dict[str, Any]] = None
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS
    deadline_at: str = ""
    timer: Any = None


@dataclass
class _ActiveFlowRecording:
    connection: Any
    sessions: dict[str, str]
    handles: list[str]
    urls: dict[str, str]
    main_frame_ids: dict[str, str]
    final_path: Path
    partial_path: Path
    started_at: str
    started_monotonic: float
    include_address: bool
    browser_version: str
    max_duration_seconds: float
    deadline_at: str
    process: Any
    frame_state: dict[str, Any]
    active_handle: str
    active_handle_box: dict[str, str]
    latest_frames: dict[str, bytes]
    frame_lock: threading.Lock
    timeline: list[tuple[float, str]]
    timeline_lock: threading.Lock
    handle_timeline: list[tuple[float, str]]
    stop_event: threading.Event
    target_closed: set[str]
    writer_thread: Optional[threading.Thread] = None
    timer: Any = None
    warning: str = ""


def _error_result(code: str, message: str, *, state: str = "idle") -> dict[str, Any]:
    return {
        "ok": False,
        "state": state,
        "error": {"code": code, "message": message},
    }


def _validate_mp4(path: Path) -> int:
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(64)
    if size <= 64 or b"ftyp" not in header:
        raise RuntimeError("Chrome returned an empty or invalid MP4 stream")
    return size


def _publish_mp4(partial_path: Path, final_path: Path) -> None:
    """Publish without overwriting a destination created while recording."""
    try:
        os.link(partial_path, final_path)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Video destination became occupied while recording: {final_path}"
        ) from exc
    partial_path.unlink()


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, hundredths = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{hundredths:02d}"


def _ass_text(url: str) -> str:
    cleaned = " ".join(str(url).replace("\x00", "").splitlines()).strip()
    cleaned = cleaned[:2048]
    return cleaned.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _ffmpeg_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _write_address_ass(
    path: Path,
    timeline: list[tuple[float, str]],
    duration: float,
) -> None:
    points: list[tuple[float, str]] = []
    for offset, url in sorted(timeline, key=lambda item: item[0]):
        offset = min(max(0.0, offset), duration)
        if points and points[-1][1] == url:
            continue
        points.append((offset, url))
    if not points:
        points = [(0.0, "about:blank")]
    if points[0][0] > 0:
        points.insert(0, (0.0, points[0][1]))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1144",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: URL,DejaVu Sans,24,&H00202020,&H00202020,&H00F1F3F4,&H00F1F3F4,0,0,0,0,100,100,0,0,1,0,0,7,24,24,12,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for index, (start, url) in enumerate(points):
        end = points[index + 1][0] if index + 1 < len(points) else duration
        if end <= start:
            continue
        lines.append(
            "Dialogue: 0,"
            f"{_ass_time(start)},{_ass_time(end)},URL,,0,0,0,,"
            f"{{\\an7\\pos(24,20)}}{_ass_text(url)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _overlay_address_recording(
    active: Any,
    duration: float,
    ffmpeg_finder: Callable[[str], Optional[str]],
    process_runner: Callable[..., Any],
) -> None:
    ffmpeg_path = ffmpeg_finder("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg disappeared before address compositing")

    ass_path = active.final_path.with_name(f".{active.final_path.name}.address.ass")
    overlay_path = active.final_path.with_name(
        f".{active.final_path.name}.overlay.part"
    )
    with active.timeline_lock:
        timeline = list(active.timeline)
    try:
        _write_address_ass(ass_path, timeline, max(duration, 0.01))
        filter_path = _ffmpeg_filter_path(ass_path)
        process = process_runner(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(active.partial_path),
                "-vf",
                "pad=iw:ih+64:0:64:color=0xF1F3F4,"
                f"subtitles=filename='{filter_path}':charenc=UTF-8",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(overlay_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "ffmpeg failed").strip()
            raise RuntimeError(detail[-1000:])
        _validate_mp4(overlay_path)
        os.replace(overlay_path, active.partial_path)
    finally:
        ass_path.unlink(missing_ok=True)
        overlay_path.unlink(missing_ok=True)


class RecordingManager:
    """Own at most one tab recording for the server process."""

    def __init__(
        self,
        *,
        connection_factory: Callable[..., Any] = _DevToolsConnection,
        ffmpeg_finder: Callable[[str], Optional[str]] = shutil.which,
        process_runner: Callable[..., Any] = subprocess.run,
        process_factory: Callable[..., Any] = subprocess.Popen,
        timer_factory: Callable[..., Any] = threading.Timer,
    ) -> None:
        self._connection_factory = connection_factory
        self._ffmpeg_finder = ffmpeg_finder
        self._process_runner = process_runner
        self._process_factory = process_factory
        self._timer_factory = timer_factory
        self._lock = threading.RLock()
        self._state = "idle"
        self._active: Optional[_ActiveRecording] = None
        self._last_result: Optional[dict[str, Any]] = None

    def start(
        self,
        driver: Any,
        file_name: str,
        directory: str = DEFAULT_VIDEO_DIRECTORY,
        include_address: bool = False,
        window_handle: str = "",
        max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    ) -> dict[str, Any]:
        with self._lock:
            if self._active is not None or self._state != "idle":
                return _error_result(
                    "recording_already_active",
                    "Stop the current recording before starting another one",
                    state=self._state,
                )

            try:
                normalized_max_duration = _normalize_max_duration(
                    max_duration_seconds
                )
            except ValueError as exc:
                return _error_result("invalid_duration", str(exc))
            try:
                final_path = prepare_video_path(file_name, directory)
            except (OSError, ValueError) as exc:
                return _error_result("invalid_path", str(exc))

            ffmpeg_path = self._ffmpeg_finder("ffmpeg") if include_address else None
            if include_address and not ffmpeg_path:
                return _error_result(
                    "ffmpeg_unavailable",
                    "include_address=true requires ffmpeg on PATH",
                )

            try:
                requested_handle = str(window_handle or "").strip()
                if requested_handle:
                    open_handles = {str(item) for item in driver.window_handles}
                    if requested_handle not in open_handles:
                        return _error_result(
                            "tab_not_found",
                            f"window_handle is not an open tab: {requested_handle}",
                        )
                    handle = requested_handle
                    start_url = ""
                else:
                    handle = str(driver.current_window_handle)
                    start_url = str(driver.current_url)
                capabilities = dict(driver.capabilities or {})
                debugger_address = str(
                    (capabilities.get("goog:chromeOptions") or {}).get(
                        "debuggerAddress", ""
                    )
                )
                browser_version = str(capabilities.get("browserVersion", ""))
            except Exception as exc:
                return _error_result("browser_state_error", str(exc))
            if not debugger_address:
                return _error_result(
                    "unsupported_driver",
                    "The active Chrome driver does not expose debuggerAddress",
                )

            partial_path = _partial_path(final_path)
            try:
                partial_path.touch(exist_ok=False)
            except OSError as exc:
                return _error_result("invalid_path", str(exc))

            started_monotonic = time.monotonic()
            started_wall = datetime.now(timezone.utc)
            deadline_at = (
                started_wall + timedelta(seconds=normalized_max_duration)
            ).isoformat()
            timeline: list[tuple[float, str]] = [(0.0, start_url)]
            timeline_lock = threading.Lock()
            target_closed = threading.Event()
            session_box = {"id": "", "main_frame_id": ""}
            connection_box: dict[str, Any] = {"connection": None}
            encoder_lock = threading.Lock()
            encoder_state: dict[str, Any] = {
                "process": None,
                "frames": 0,
                "error": "",
                "accepting": False,
            }

            def on_event(message: dict[str, Any]) -> None:
                method = message.get("method")
                params = message.get("params") or {}
                session_id = session_box["id"]
                if method == "Target.detachedFromTarget" and (
                    params.get("sessionId") == session_id
                ):
                    target_closed.set()
                    return
                if message.get("sessionId") != session_id:
                    return
                if method == "Page.screencastFrame":
                    try:
                        with encoder_lock:
                            process = encoder_state["process"]
                            if process is not None and encoder_state["accepting"]:
                                process.stdin.write(base64.b64decode(params.get("data", "")))
                                encoder_state["frames"] += 1
                    except Exception as exc:
                        encoder_state["error"] = str(exc)
                    finally:
                        connection = connection_box["connection"]
                        if connection is not None:
                            connection.send_no_wait(
                                "Page.screencastFrameAck",
                                {"sessionId": params.get("sessionId")},
                                session_id=session_id,
                            )
                    return
                url = ""
                if method == "Page.frameNavigated":
                    frame = params.get("frame") or {}
                    if not frame.get("parentId"):
                        session_box["main_frame_id"] = str(frame.get("id", ""))
                        url = str(frame.get("url", ""))
                elif method == "Page.navigatedWithinDocument" and (
                    not session_box["main_frame_id"]
                    or params.get("frameId") == session_box["main_frame_id"]
                ):
                    url = str(params.get("url", ""))
                if url:
                    with timeline_lock:
                        if timeline[-1][1] != url:
                            timeline.append((time.monotonic() - started_monotonic, url))

            connection = None
            session_id = ""
            transport = "native"
            start_stream = ""
            try:
                connection = self._connection_factory(debugger_address, on_event)
                connection_box["connection"] = connection
                targets = connection.command("Target.getTargets").get("targetInfos", [])
                target_info = next(
                    (
                        target
                        for target in targets
                        if target.get("targetId") == handle
                        and target.get("type") == "page"
                    ),
                    None,
                )
                if target_info is None:
                    raise RuntimeError(f"Selected tab target is unavailable: {handle}")
                if not start_url:
                    start_url = str(target_info.get("url") or "about:blank")
                    with timeline_lock:
                        timeline[0] = (0.0, start_url)
                session_id = str(
                    connection.command(
                        "Target.attachToTarget",
                        {"targetId": handle, "flatten": True},
                    ).get("sessionId", "")
                )
                if not session_id:
                    raise RuntimeError("Chrome did not create a DevTools target session")
                session_box["id"] = session_id
                connection.command("Page.enable", session_id=session_id)
                frame_tree = connection.command(
                    "Page.getFrameTree", session_id=session_id
                ).get("frameTree", {})
                session_box["main_frame_id"] = str(
                    (frame_tree.get("frame") or {}).get("id", "")
                )
                try:
                    start_result = connection.command(
                        "Page.startScreenRecording",
                        {
                            "audio": False,
                            "maxWidth": 1920,
                            "maxHeight": 1080,
                            "frameRate": 30,
                        },
                        session_id=session_id,
                    )
                    start_stream = str(start_result.get("stream", ""))
                    if not start_stream:
                        raise RuntimeError("Chrome did not return a recording stream")
                except DevToolsCommandError as exc:
                    if exc.code != -32601:
                        raise
                    fallback_ffmpeg = self._ffmpeg_finder("ffmpeg")
                    if not fallback_ffmpeg:
                        raise UnsupportedRecordingError(
                            "Chrome lacks native recording and ffmpeg is unavailable for the fallback"
                        ) from exc
                    transport = "screencast"
                    encoder_state["process"] = self._start_screencast_encoder(
                        fallback_ffmpeg,
                        partial_path,
                    )
                    encoder_state["accepting"] = True
                    connection.command(
                        "Page.startScreencast",
                        {
                            "format": "jpeg",
                            "quality": 90,
                            "maxWidth": 1920,
                            "maxHeight": 1080,
                            "everyNthFrame": 1,
                            "maxFramesInFlight": 3,
                        },
                        session_id=session_id,
                    )
            except UnsupportedRecordingError as exc:
                self._abort_screencast_encoder(encoder_state)
                if connection is not None:
                    connection.close()
                partial_path.unlink(missing_ok=True)
                return _error_result(
                    "unsupported_browser",
                    f"{exc} (Chrome {browser_version or 'unknown'})",
                )
            except DevToolsCommandError as exc:
                self._abort_screencast_encoder(encoder_state)
                if connection is not None:
                    connection.close()
                partial_path.unlink(missing_ok=True)
                code = "unsupported_browser" if exc.code == -32601 else "recording_failed"
                return _error_result(
                    code,
                    f"{exc} (Chrome {browser_version or 'unknown'})",
                )
            except Exception as exc:
                self._abort_screencast_encoder(encoder_state)
                if connection is not None:
                    connection.close()
                partial_path.unlink(missing_ok=True)
                return _error_result("recording_failed", str(exc))

            active = _ActiveRecording(
                connection=connection,
                session_id=session_id,
                start_stream=start_stream,
                handle=handle,
                start_url=start_url,
                browser_version=browser_version,
                include_address=bool(include_address),
                final_path=final_path,
                partial_path=partial_path,
                started_at=started_wall.isoformat(),
                started_monotonic=started_monotonic,
                main_frame_id=session_box["main_frame_id"],
                timeline=timeline,
                timeline_lock=timeline_lock,
                target_closed=target_closed,
                transport=transport,
                encoder_state=encoder_state if transport == "screencast" else None,
                max_duration_seconds=normalized_max_duration,
                deadline_at=deadline_at,
            )
            self._active = active
            self._state = "recording"
            timer = self._timer_factory(
                normalized_max_duration,
                self._auto_stop,
                args=(active,),
            )
            timer.daemon = True
            active.timer = timer
            timer.start()
            result = {
                "ok": True,
                "state": "recording",
                "handle": handle,
                "start_url": start_url,
                "path": str(final_path),
                "started_at": active.started_at,
                "include_address": bool(include_address),
                "transport": transport,
                "max_duration_seconds": normalized_max_duration,
                "deadline_at": deadline_at,
                "cleanup_required": True,
                "next_action": (
                    "Call record_video(action='stop') immediately after the final "
                    "browser action; the deadline is only a fallback"
                ),
            }
            self._last_result = result
            return result

    def _auto_stop(self, expected_active: _ActiveRecording) -> None:
        with self._lock:
            if self._active is not expected_active:
                return
        result = self.stop(reason="max_duration_reached")
        if not result.get("ok"):
            logger.error("Unable to auto-finalize video recording: %s", result)

    def _start_screencast_encoder(self, ffmpeg_path: str, output_path: Path) -> Any:
        return self._process_factory(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "image2pipe",
                "-framerate",
                "30",
                "-vcodec",
                "mjpeg",
                "-i",
                "pipe:0",
                "-an",
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(output_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _abort_screencast_encoder(self, state: Optional[dict[str, Any]]) -> None:
        if not state:
            return
        state["accepting"] = False
        process = state.get("process")
        if process is None or process.poll() is not None:
            return
        try:
            process.stdin.close()
        except Exception:
            pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _finish_screencast_encoder(self, active: _ActiveRecording) -> None:
        state = active.encoder_state or {}
        state["accepting"] = False
        process = state.get("process")
        if process is None:
            raise RuntimeError("The screencast encoder was not started")
        process.stdin.close()
        try:
            return_code = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise RuntimeError("The screencast encoder timed out")
        stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
        if state.get("error"):
            raise RuntimeError(f"Unable to write screencast frame: {state['error']}")
        if not state.get("frames"):
            raise RuntimeError("Chrome returned no screencast frames")
        if return_code != 0:
            raise RuntimeError(stderr[-1000:] or "ffmpeg screencast encoding failed")

    def _drain_stream(self, active: _ActiveRecording, stream: str) -> None:
        with active.partial_path.open("wb") as output:
            while True:
                response = active.connection.command(
                    "IO.read",
                    {"handle": stream, "size": _READ_CHUNK_SIZE},
                    session_id=active.session_id,
                )
                data = response.get("data", "")
                if data:
                    if response.get("base64Encoded"):
                        output.write(base64.b64decode(data))
                    else:
                        try:
                            output.write(str(data).encode("latin-1"))
                        except UnicodeEncodeError:
                            output.write(str(data).encode("utf-8"))
                if response.get("eof"):
                    break
        try:
            active.connection.command(
                "IO.close",
                {"handle": stream},
                session_id=active.session_id,
                timeout=5,
            )
        except Exception:
            logger.debug("Unable to close recording IO stream", exc_info=True)

    def _overlay_address(self, active: _ActiveRecording, duration: float) -> None:
        _overlay_address_recording(
            active,
            duration,
            self._ffmpeg_finder,
            self._process_runner,
        )

    def stop(self, reason: str = "manual_stop") -> dict[str, Any]:
        with self._lock:
            active = self._active
            if active is None:
                return _error_result(
                    "no_active_recording", "There is no active recording"
                )
            if self._state == "finalizing":
                return _error_result(
                    "recording_finalizing",
                    "The active recording is already finalizing",
                    state="finalizing",
                )
            self._state = "finalizing"

        if active.timer is not None:
            active.timer.cancel()

        duration = max(0.0, time.monotonic() - active.started_monotonic)
        overlay_started = False
        try:
            if active.target_closed.is_set():
                raise RuntimeError("The recorded tab closed before finalization")
            if active.transport == "native":
                stop_result = active.connection.command(
                    "Page.stopScreenRecording",
                    session_id=active.session_id,
                    timeout=60,
                )
                stream = str(stop_result.get("stream") or active.start_stream)
                if not stream:
                    raise RuntimeError("Chrome did not return the finalized stream")
                self._drain_stream(active, stream)
            else:
                active.connection.command(
                    "Page.stopScreencast",
                    session_id=active.session_id,
                    timeout=30,
                )
                self._finish_screencast_encoder(active)
            _validate_mp4(active.partial_path)
            if active.include_address:
                overlay_started = True
                self._overlay_address(active, duration)
            byte_count = _validate_mp4(active.partial_path)
            _publish_mp4(active.partial_path, active.final_path)
            result = {
                "ok": True,
                "state": "idle",
                "path": str(active.final_path),
                "bytes": byte_count,
                "duration_seconds": round(duration, 3),
                "handle": active.handle,
                "include_address": active.include_address,
                "transport": active.transport,
                "stop_reason": reason,
                "cleanup_required": False,
                "warning": "Video and visible URLs may contain sensitive data",
            }
        except DevToolsCommandError as exc:
            code = "target_closed" if active.target_closed.is_set() else "recording_failed"
            result = _error_result(code, str(exc))
        except subprocess.TimeoutExpired:
            result = _error_result(
                "address_overlay_failed", "ffmpeg address compositing timed out"
            )
        except Exception as exc:
            code = "address_overlay_failed" if overlay_started else "recording_failed"
            result = _error_result(code, str(exc))
        finally:
            try:
                if active.session_id:
                    active.connection.command(
                        "Target.detachFromTarget",
                        {"sessionId": active.session_id},
                        timeout=5,
                    )
            except Exception:
                logger.debug("Unable to detach video target session", exc_info=True)
            self._abort_screencast_encoder(active.encoder_state)
            active.connection.close()
            if not result.get("ok"):
                active.partial_path.unlink(missing_ok=True)
                result["stop_reason"] = reason
                result["cleanup_required"] = False
            with self._lock:
                self._active = None
                self._state = "idle"
                self._last_result = result
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = self._active
            result: dict[str, Any] = {
                "ok": True,
                "state": self._state,
                "cleanup_required": active is not None,
            }
            if active is not None:
                elapsed = max(0.0, time.monotonic() - active.started_monotonic)
                result["recording"] = {
                    "handle": active.handle,
                    "start_url": active.start_url,
                    "path": str(active.final_path),
                    "started_at": active.started_at,
                    "include_address": active.include_address,
                    "transport": active.transport,
                    "max_duration_seconds": active.max_duration_seconds,
                    "deadline_at": active.deadline_at,
                    "elapsed_seconds": round(elapsed, 3),
                    "remaining_seconds": round(
                        max(0.0, active.max_duration_seconds - elapsed), 3
                    ),
                    "cleanup_required": True,
                }
            if self._last_result is not None:
                result["last_result"] = self._last_result
            return result

    def is_recording_handle(self, handle: str) -> bool:
        with self._lock:
            return self._active is not None and self._active.handle == handle

    def shutdown(self) -> Optional[dict[str, Any]]:
        with self._lock:
            active = self._active
        if active is None:
            return None
        result = self.stop(reason="server_shutdown")
        if not result.get("ok"):
            logger.error("Unable to finalize active video recording: %s", result)
        return result


class FollowActiveRecordingManager:
    """Record selected tab targets into one stream that follows the active handle."""

    def __init__(
        self,
        *,
        connection_factory: Callable[..., Any] = _DevToolsConnection,
        ffmpeg_finder: Callable[[str], Optional[str]] = shutil.which,
        process_runner: Callable[..., Any] = subprocess.run,
        process_factory: Callable[..., Any] = subprocess.Popen,
        timer_factory: Callable[..., Any] = threading.Timer,
        frame_rate: int = 10,
    ) -> None:
        self._connection_factory = connection_factory
        self._ffmpeg_finder = ffmpeg_finder
        self._process_runner = process_runner
        self._process_factory = process_factory
        self._timer_factory = timer_factory
        self._frame_rate = frame_rate
        self._lock = threading.RLock()
        self._state = "idle"
        self._active: Optional[_ActiveFlowRecording] = None
        self._last_result: Optional[dict[str, Any]] = None

    def _start_encoder(self, ffmpeg_path: str, output_path: Path) -> Any:
        return self._process_factory(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "image2pipe",
                "-framerate",
                str(self._frame_rate),
                "-vcodec",
                "mjpeg",
                "-i",
                "pipe:0",
                "-an",
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(output_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    @staticmethod
    def _abort_encoder(process: Any) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            process.stdin.close()
        except Exception:
            pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _write_active_frames(self, active: _ActiveFlowRecording) -> None:
        interval = 1.0 / self._frame_rate
        next_tick = time.monotonic()
        while not active.stop_event.is_set():
            with active.frame_lock:
                frame = active.latest_frames.get(active.active_handle)
            if frame:
                try:
                    active.process.stdin.write(frame)
                    active.frame_state["frames"] += 1
                except Exception as exc:
                    active.frame_state["error"] = str(exc)
                    active.stop_event.set()
                    return
            next_tick = max(next_tick + interval, time.monotonic())
            active.stop_event.wait(max(0.0, next_tick - time.monotonic()))

    def start(
        self,
        driver: Any,
        file_name: str,
        directory: str,
        include_address: bool,
        handles: list[str],
        max_duration_seconds: float,
    ) -> dict[str, Any]:
        with self._lock:
            if self._active is not None or self._state != "idle":
                return _error_result(
                    "recording_already_active",
                    "Stop the current recording before starting another one",
                    state=self._state,
                )
            try:
                duration = _normalize_max_duration(max_duration_seconds)
                final_path = prepare_video_path(file_name, directory)
            except ValueError as exc:
                code = "invalid_duration" if "max_duration" in str(exc) else "invalid_path"
                return _error_result(code, str(exc))
            except OSError as exc:
                return _error_result("invalid_path", str(exc))

            ffmpeg_path = self._ffmpeg_finder("ffmpeg")
            if not ffmpeg_path:
                return _error_result(
                    "ffmpeg_unavailable",
                    "Multi-tab follow-active recording requires ffmpeg on PATH",
                )
            try:
                active_handle = str(driver.current_window_handle)
                capabilities = dict(driver.capabilities or {})
                debugger_address = str(
                    (capabilities.get("goog:chromeOptions") or {}).get(
                        "debuggerAddress", ""
                    )
                )
                browser_version = str(capabilities.get("browserVersion", ""))
            except Exception as exc:
                return _error_result("browser_state_error", str(exc))
            if active_handle not in handles:
                return _error_result(
                    "active_tab_not_selected",
                    "The active tab must be included in window_handles when recording starts",
                )
            if not debugger_address:
                return _error_result(
                    "unsupported_driver",
                    "The active Chrome driver does not expose debuggerAddress",
                )

            partial_path = _partial_path(final_path)
            try:
                partial_path.touch(exist_ok=False)
            except OSError as exc:
                return _error_result("invalid_path", str(exc))

            sessions: dict[str, str] = {}
            session_to_handle: dict[str, str] = {}
            urls: dict[str, str] = {}
            main_frame_ids: dict[str, str] = {}
            latest_frames: dict[str, bytes] = {}
            frame_lock = threading.Lock()
            timeline: list[tuple[float, str]] = []
            timeline_lock = threading.Lock()
            target_closed: set[str] = set()
            connection_box: dict[str, Any] = {"connection": None}
            active_handle_box = {"handle": active_handle}
            started_box: dict[str, Optional[float]] = {"monotonic": None}

            def on_event(message: dict[str, Any]) -> None:
                method = message.get("method")
                params = message.get("params") or {}
                if method == "Target.detachedFromTarget":
                    closed_handle = session_to_handle.get(str(params.get("sessionId", "")))
                    if closed_handle:
                        target_closed.add(closed_handle)
                    return
                session_id = str(message.get("sessionId", ""))
                handle = session_to_handle.get(session_id)
                if not handle:
                    return
                if method == "Page.screencastFrame":
                    try:
                        frame = base64.b64decode(params.get("data", ""))
                        if frame:
                            with frame_lock:
                                latest_frames[handle] = frame
                    finally:
                        connection = connection_box["connection"]
                        if connection is not None:
                            connection.send_no_wait(
                                "Page.screencastFrameAck",
                                {"sessionId": params.get("sessionId")},
                                session_id=session_id,
                            )
                    return
                url = ""
                if method == "Page.frameNavigated":
                    frame = params.get("frame") or {}
                    if not frame.get("parentId"):
                        main_frame_ids[handle] = str(frame.get("id", ""))
                        url = str(frame.get("url", ""))
                elif method == "Page.navigatedWithinDocument" and (
                    not main_frame_ids.get(handle)
                    or params.get("frameId") == main_frame_ids.get(handle)
                ):
                    url = str(params.get("url", ""))
                if url:
                    urls[handle] = url
                    started = started_box["monotonic"]
                    with frame_lock:
                        is_active = active_handle_box["handle"] == handle
                    if started is not None and is_active:
                        with timeline_lock:
                            if not timeline or timeline[-1][1] != url:
                                timeline.append((time.monotonic() - started, url))

            connection = None
            process = None
            try:
                process = self._start_encoder(ffmpeg_path, partial_path)
                connection = self._connection_factory(debugger_address, on_event)
                connection_box["connection"] = connection
                target_infos = connection.command("Target.getTargets").get(
                    "targetInfos", []
                )
                targets = {
                    str(target.get("targetId")): target
                    for target in target_infos
                    if target.get("type") == "page"
                }
                for handle in handles:
                    target = targets.get(handle)
                    if target is None:
                        raise RuntimeError(f"Selected tab target is unavailable: {handle}")
                    urls[handle] = str(target.get("url") or "about:blank")
                    session_id = str(
                        connection.command(
                            "Target.attachToTarget",
                            {"targetId": handle, "flatten": True},
                        ).get("sessionId", "")
                    )
                    if not session_id:
                        raise RuntimeError(
                            f"Chrome did not create a target session for {handle}"
                        )
                    sessions[handle] = session_id
                    session_to_handle[session_id] = handle
                    connection.command("Page.enable", session_id=session_id)
                    frame_tree = connection.command(
                        "Page.getFrameTree", session_id=session_id
                    ).get("frameTree", {})
                    main_frame_ids[handle] = str(
                        (frame_tree.get("frame") or {}).get("id", "")
                    )
                    connection.command(
                        "Page.startScreencast",
                        {
                            "format": "jpeg",
                            "quality": 90,
                            "maxWidth": 1920,
                            "maxHeight": 1080,
                            "everyNthFrame": 1,
                            "maxFramesInFlight": 3,
                        },
                        session_id=session_id,
                    )
            except Exception as exc:
                if connection is not None:
                    for session_id in sessions.values():
                        try:
                            connection.command(
                                "Page.stopScreencast", session_id=session_id, timeout=5
                            )
                            connection.command(
                                "Target.detachFromTarget",
                                {"sessionId": session_id},
                                timeout=5,
                            )
                        except Exception:
                            pass
                    connection.close()
                self._abort_encoder(process)
                partial_path.unlink(missing_ok=True)
                return _error_result("recording_failed", str(exc))

            started_monotonic = time.monotonic()
            started_wall = datetime.now(timezone.utc)
            deadline_at = (started_wall + timedelta(seconds=duration)).isoformat()
            started_box["monotonic"] = started_monotonic
            timeline.append((0.0, urls[active_handle]))
            frame_state = {"frames": 0, "error": ""}
            active = _ActiveFlowRecording(
                connection=connection,
                sessions=sessions,
                handles=list(handles),
                urls=urls,
                main_frame_ids=main_frame_ids,
                final_path=final_path,
                partial_path=partial_path,
                started_at=started_wall.isoformat(),
                started_monotonic=started_monotonic,
                include_address=bool(include_address),
                browser_version=browser_version,
                max_duration_seconds=duration,
                deadline_at=deadline_at,
                process=process,
                frame_state=frame_state,
                active_handle=active_handle,
                active_handle_box=active_handle_box,
                latest_frames=latest_frames,
                frame_lock=frame_lock,
                timeline=timeline,
                timeline_lock=timeline_lock,
                handle_timeline=[(0.0, active_handle)],
                stop_event=threading.Event(),
                target_closed=target_closed,
            )
            writer = threading.Thread(
                target=self._write_active_frames,
                args=(active,),
                name="selenium-video-follow-active",
                daemon=True,
            )
            active.writer_thread = writer
            self._active = active
            self._state = "recording"
            with active.frame_lock:
                initial_frame = active.latest_frames.get(active.active_handle)
            if initial_frame:
                try:
                    active.process.stdin.write(initial_frame)
                    active.frame_state["frames"] += 1
                except Exception as exc:
                    active.frame_state["error"] = str(exc)
            writer.start()
            timer = self._timer_factory(duration, self._auto_stop, args=(active,))
            timer.daemon = True
            active.timer = timer
            timer.start()
            result = {
                "ok": True,
                "state": "recording",
                "mode": "follow_active",
                "handles": list(handles),
                "active_handle": active_handle,
                "path": str(final_path),
                "started_at": active.started_at,
                "include_address": bool(include_address),
                "transport": "screencast-follow-active",
                "max_duration_seconds": duration,
                "deadline_at": deadline_at,
                "cleanup_required": True,
                "next_action": (
                    "Switch only with tabs/switch_tab, then call record_video(action='stop') "
                    "immediately after the final browser action"
                ),
            }
            self._last_result = result
            return result

    def _auto_stop(self, expected_active: _ActiveFlowRecording) -> None:
        with self._lock:
            if self._active is not expected_active:
                return
        result = self.stop(reason="max_duration_reached")
        if not result.get("ok"):
            logger.error("Unable to auto-finalize follow-active recording: %s", result)

    def notify_active_handle(self, handle: str) -> bool:
        with self._lock:
            active = self._active
            if active is None or self._state != "recording":
                return False
            if handle not in active.handles:
                active.warning = (
                    f"Active tab {handle} is outside window_handles; video remains on "
                    f"{active.active_handle}"
                )
                return False
            with active.frame_lock:
                if active.active_handle == handle:
                    return True
                active.active_handle = handle
                active.active_handle_box["handle"] = handle
            offset = max(0.0, time.monotonic() - active.started_monotonic)
            active.handle_timeline.append((offset, handle))
            with active.timeline_lock:
                url = active.urls.get(handle, "about:blank")
                if not active.timeline or active.timeline[-1][1] != url:
                    active.timeline.append((offset, url))
            active.warning = ""
            return True

    def stop(self, reason: str = "manual_stop") -> dict[str, Any]:
        with self._lock:
            active = self._active
            if active is None:
                return _error_result(
                    "no_active_recording", "There is no active recording"
                )
            if self._state == "finalizing":
                return _error_result(
                    "recording_finalizing",
                    "The active recording is already finalizing",
                    state="finalizing",
                )
            self._state = "finalizing"
        if active.timer is not None:
            active.timer.cancel()
        duration = max(0.0, time.monotonic() - active.started_monotonic)
        overlay_started = False
        result: dict[str, Any]
        try:
            active.stop_event.set()
            if active.writer_thread is not None:
                active.writer_thread.join(timeout=5)
                if active.writer_thread.is_alive():
                    raise RuntimeError("The active-frame writer did not stop")
            for session_id in active.sessions.values():
                active.connection.command(
                    "Page.stopScreencast", session_id=session_id, timeout=30
                )
            if active.target_closed:
                raise RuntimeError(
                    f"A recorded tab closed before finalization: {sorted(active.target_closed)[0]}"
                )
            active.process.stdin.close()
            try:
                return_code = active.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                active.process.kill()
                active.process.wait(timeout=5)
                raise RuntimeError("The follow-active encoder timed out")
            stderr = active.process.stderr.read().decode(
                "utf-8", errors="replace"
            ).strip()
            if active.frame_state.get("error"):
                raise RuntimeError(
                    f"Unable to write active-tab frame: {active.frame_state['error']}"
                )
            if not active.frame_state.get("frames"):
                raise RuntimeError("Chrome returned no frames for the active tab flow")
            if return_code != 0:
                raise RuntimeError(
                    stderr[-1000:] or "ffmpeg follow-active encoding failed"
                )
            _validate_mp4(active.partial_path)
            if active.include_address:
                overlay_started = True
                _overlay_address_recording(
                    active,
                    duration,
                    self._ffmpeg_finder,
                    self._process_runner,
                )
            byte_count = _validate_mp4(active.partial_path)
            _publish_mp4(active.partial_path, active.final_path)
            result = {
                "ok": True,
                "state": "idle",
                "mode": "follow_active",
                "path": str(active.final_path),
                "bytes": byte_count,
                "duration_seconds": round(duration, 3),
                "handles": list(active.handles),
                "active_handle": active.active_handle,
                "switch_count": max(0, len(active.handle_timeline) - 1),
                "include_address": active.include_address,
                "transport": "screencast-follow-active",
                "stop_reason": reason,
                "cleanup_required": False,
                "warning": "Video and visible URLs may contain sensitive data",
            }
        except subprocess.TimeoutExpired:
            result = _error_result(
                "address_overlay_failed", "ffmpeg address compositing timed out"
            )
        except Exception as exc:
            code = "address_overlay_failed" if overlay_started else "recording_failed"
            result = _error_result(code, str(exc))
        finally:
            active.stop_event.set()
            self._abort_encoder(active.process)
            for session_id in active.sessions.values():
                try:
                    active.connection.command(
                        "Target.detachFromTarget",
                        {"sessionId": session_id},
                        timeout=5,
                    )
                except Exception:
                    logger.debug("Unable to detach flow target session", exc_info=True)
            active.connection.close()
            if not result.get("ok"):
                active.partial_path.unlink(missing_ok=True)
                result["stop_reason"] = reason
                result["cleanup_required"] = False
            with self._lock:
                self._active = None
                self._state = "idle"
                self._last_result = result
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = self._active
            result: dict[str, Any] = {
                "ok": True,
                "state": self._state,
                "cleanup_required": active is not None,
            }
            if active is not None:
                elapsed = max(0.0, time.monotonic() - active.started_monotonic)
                result["recording"] = {
                    "mode": "follow_active",
                    "handles": list(active.handles),
                    "active_handle": active.active_handle,
                    "path": str(active.final_path),
                    "started_at": active.started_at,
                    "include_address": active.include_address,
                    "transport": "screencast-follow-active",
                    "max_duration_seconds": active.max_duration_seconds,
                    "deadline_at": active.deadline_at,
                    "elapsed_seconds": round(elapsed, 3),
                    "remaining_seconds": round(
                        max(0.0, active.max_duration_seconds - elapsed), 3
                    ),
                    "switch_count": max(0, len(active.handle_timeline) - 1),
                    "cleanup_required": True,
                }
                if active.warning:
                    result["recording"]["warning"] = active.warning
            if self._last_result is not None:
                result["last_result"] = self._last_result
            return result

    def is_recording_handle(self, handle: str) -> bool:
        with self._lock:
            return self._active is not None and handle in self._active.handles

    def shutdown(self) -> Optional[dict[str, Any]]:
        with self._lock:
            active = self._active
        if active is None:
            return None
        result = self.stop(reason="server_shutdown")
        if not result.get("ok"):
            logger.error("Unable to finalize follow-active recording: %s", result)
        return result


class RecordingCoordinator:
    """Select fixed-tab or single-artifact follow-active recording semantics."""

    def __init__(
        self,
        *,
        manager_factory: Callable[[], RecordingManager] = RecordingManager,
        flow_factory: Callable[[], FollowActiveRecordingManager] = (
            FollowActiveRecordingManager
        ),
    ) -> None:
        self._manager_factory = manager_factory
        self._flow_factory = flow_factory
        self._lock = threading.RLock()
        self._single: Optional[RecordingManager] = None
        self._flow: Optional[FollowActiveRecordingManager] = None
        self._last_result: Optional[dict[str, Any]] = None

    @staticmethod
    def _flow_handles(
        driver: Any,
        window_handle: str,
        window_handles: list[str],
    ) -> tuple[Optional[list[str]], Optional[dict[str, Any]]]:
        selected_handle = str(window_handle or "").strip()
        if window_handles is None:
            window_handles = []
        if not isinstance(window_handles, list):
            return None, _error_result(
                "invalid_window_handles", "window_handles must be a list of tab handles"
            )
        if selected_handle and window_handles:
            return None, _error_result(
                "conflicting_tab_selection",
                "window_handle and window_handles are mutually exclusive",
            )
        if not window_handles:
            return [], None
        if not 2 <= len(window_handles) <= MAX_FLOW_TABS:
            return None, _error_result(
                "invalid_window_handles",
                f"window_handles must contain 2-{MAX_FLOW_TABS} tab handles",
            )
        if any(not isinstance(item, str) or not item.strip() for item in window_handles):
            return None, _error_result(
                "invalid_window_handles", "Every window_handles item must be non-empty"
            )
        handles = [item.strip() for item in window_handles]
        if len(set(handles)) != len(handles):
            return None, _error_result(
                "invalid_window_handles", "window_handles must not contain duplicates"
            )
        try:
            open_handles = {str(item) for item in driver.window_handles}
        except Exception as exc:
            return None, _error_result("browser_state_error", str(exc))
        missing = [handle for handle in handles if handle not in open_handles]
        if missing:
            return None, _error_result(
                "tab_not_found", f"window_handles contains an open-tab mismatch: {missing[0]}"
            )
        return handles, None

    def _has_active(self) -> bool:
        target = self._flow or self._single
        return bool(target and target.status().get("cleanup_required"))

    def start(
        self,
        driver: Any,
        file_name: str,
        directory: str = DEFAULT_VIDEO_DIRECTORY,
        include_address: bool = False,
        window_handle: str = "",
        max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
        window_handles: list[str] = [],
    ) -> dict[str, Any]:
        with self._lock:
            if self._has_active():
                return _error_result(
                    "recording_already_active",
                    "Stop the current recording before starting another one",
                    state="recording",
                )
            self._single = None
            self._flow = None
            handles, selection_error = self._flow_handles(
                driver, window_handle, window_handles
            )
            if selection_error is not None:
                return selection_error
            assert handles is not None
            if handles:
                flow = self._flow_factory()
                result = flow.start(
                    driver,
                    file_name,
                    directory,
                    include_address,
                    handles,
                    max_duration_seconds,
                )
                if result.get("ok"):
                    self._flow = flow
            else:
                single = self._manager_factory()
                result = single.start(
                    driver,
                    file_name,
                    directory,
                    include_address,
                    window_handle,
                    max_duration_seconds,
                )
                if result.get("ok"):
                    self._single = single
            self._last_result = result
            return result

    def stop(self, reason: str = "manual_stop") -> dict[str, Any]:
        with self._lock:
            target = self._flow or self._single
            if target is None:
                return _error_result(
                    "no_active_recording", "There is no active recording"
                )
            result = target.stop(reason=reason)
            self._flow = None
            self._single = None
            self._last_result = result
            return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            target = self._flow or self._single
            if target is None:
                result: dict[str, Any] = {
                    "ok": True,
                    "state": "idle",
                    "cleanup_required": False,
                }
                if self._last_result is not None:
                    result["last_result"] = self._last_result
                return result
            result = target.status()
            if not result.get("cleanup_required"):
                self._last_result = result.get("last_result")
                self._flow = None
                self._single = None
            return result

    def notify_active_handle(self, handle: str) -> bool:
        with self._lock:
            return bool(self._flow and self._flow.notify_active_handle(handle))

    def is_recording_handle(self, handle: str) -> bool:
        with self._lock:
            target = self._flow or self._single
            return bool(target and target.is_recording_handle(handle))

    def shutdown(self) -> Optional[dict[str, Any]]:
        with self._lock:
            target = self._flow or self._single
            if target is None:
                return None
            result = target.shutdown()
            self._flow = None
            self._single = None
            if result is not None:
                self._last_result = result
            return result


recording_manager = RecordingCoordinator()


def record_video_json(
    driver: Any,
    action: str,
    file_name: str = "",
    directory: str = DEFAULT_VIDEO_DIRECTORY,
    include_address: bool = False,
    window_handle: str = "",
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    window_handles: list[str] = [],
) -> str:
    """Dispatch the public action contract and return structured JSON."""
    if action == "start":
        result = recording_manager.start(
            driver,
            file_name,
            directory,
            include_address,
            window_handle,
            max_duration_seconds,
            window_handles,
        )
    elif action == "stop":
        result = recording_manager.stop()
    elif action == "status":
        result = recording_manager.status()
    else:
        result = _error_result(
            "invalid_action", "action must be one of: start, stop, status"
        )
    return json.dumps(result, ensure_ascii=False)
