"""Bounded diagnostic buffers for the experimental compact profile."""

from collections import deque
from dataclasses import dataclass, field
import json
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .logs import CONSOLE_LOG_DELIVERY_WAIT_SECONDS, read_driver_logs

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
}
_SENSITIVE_QUERY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "code",
    "key",
    "password",
    "secret",
    "session",
    "token",
)
_SENSITIVE_VALUE_FIELDS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "passwd",
    "refresh_token",
    "secret",
    "session_token",
    "token",
}
_BODY_KEYS = {"postdata", "requestheaderstext", "responseheaderstext"}
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
_NETWORK_EVENT_PREFIXES = {
    "all": "",
    "request": "Network.requestWillBeSent",
    "response": "Network.responseReceived",
    "finished": "Network.loadingFinished",
    "failed": "Network.loadingFailed",
}
_MAX_RESPONSE_ERROR_CHARS = 500


@dataclass(frozen=True)
class DiagnosticEvent:
    cursor: int
    timestamp: int
    payload: dict[str, Any]


@dataclass
class _EventBuffer:
    max_entries: int
    events: deque[DiagnosticEvent] = field(default_factory=deque)
    dropped_events: int = 0

    def append(self, event: DiagnosticEvent) -> None:
        if len(self.events) >= self.max_entries:
            self.events.popleft()
            self.dropped_events += 1
        self.events.append(event)

    def consume(self, cursors: set[int]) -> None:
        self.events = deque(
            (event for event in self.events if event.cursor not in cursors)
        )


def _is_sensitive_query_name(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_QUERY_PARTS)


def _is_sensitive_value_field(name: str) -> bool:
    return name.lower().replace("-", "_") in _SENSITIVE_VALUE_FIELDS


def _redact_url(value: str) -> str:
    try:
        split = urlsplit(value)
        if split.scheme not in {"http", "https"} or not split.netloc:
            return value
        query = [
            (key, "[REDACTED]" if _is_sensitive_query_name(key) else item_value)
            for key, item_value in parse_qsl(split.query, keep_blank_values=True)
        ]
        return urlunsplit(
            (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
        )
    except (TypeError, ValueError):
        return value


def _redact_string(value: str) -> str:
    return _URL_PATTERN.sub(lambda match: _redact_url(match.group(0)), value)


def redact_diagnostic(value, parent_key: str = ""):
    """Redact common credentials without mutating the broker's retained event."""
    normalized_parent = parent_key.lower().replace("_", "")
    if normalized_parent in _BODY_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        result = {}
        headers = normalized_parent.endswith("headers")
        for key, item in value.items():
            if headers and str(key).lower() in _SENSITIVE_HEADERS:
                result[key] = "[REDACTED]"
            elif _is_sensitive_value_field(str(key)) and not isinstance(
                item, (dict, list)
            ):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_diagnostic(item, str(key))
        return result
    if isinstance(value, list):
        return [redact_diagnostic(item, parent_key) for item in value]
    if isinstance(value, str):
        if parent_key.lower() in {"url", "documenturl"}:
            return _redact_url(value)
        return _redact_string(value)
    return value


class DiagnosticsBroker:
    """Own destructive WebDriver reads and retain a bounded per-session copy."""

    def __init__(
        self,
        console_limit: int = 500,
        network_limit: int = 1000,
        max_inflight_age_seconds: float = 15,
    ):
        self.console_limit = console_limit
        self.network_limit = network_limit
        self.max_inflight_age_seconds = max_inflight_age_seconds
        self._session = ""
        self._cursor = 0
        self._console = _EventBuffer(console_limit)
        self._network = _EventBuffer(network_limit)
        self._inflight: dict[str, tuple[float, str]] = {}
        self._last_network_activity = time.monotonic()
        self._ignored_long_running = 0

    def clear(self) -> None:
        self._session = ""
        self._reset_buffers()

    def _reset_buffers(self) -> None:
        self._cursor = 0
        self._console = _EventBuffer(self.console_limit)
        self._network = _EventBuffer(self.network_limit)
        self._inflight = {}
        self._last_network_activity = time.monotonic()
        self._ignored_long_running = 0

    def _activate(self, driver) -> None:
        session = str(getattr(driver, "session_id", id(driver)))
        if session != self._session:
            self._session = session
            self._reset_buffers()

    def latest_cursor(self, driver) -> int:
        self._activate(driver)
        return self._cursor

    def _append(self, buffer: _EventBuffer, payload: dict, timestamp: int) -> None:
        self._cursor += 1
        buffer.append(DiagnosticEvent(self._cursor, timestamp, payload))

    def drain_console(self, driver, wait_seconds=None) -> int:
        self._activate(driver)
        if wait_seconds is None:
            wait_seconds = CONSOLE_LOG_DELIVERY_WAIT_SECONDS
        entries = read_driver_logs(driver, "browser", wait_seconds=wait_seconds)
        for entry in entries:
            timestamp = int(entry.get("timestamp") or time.time() * 1000)
            self._append(
                self._console,
                {
                    "level": str(entry.get("level", "INFO")).upper(),
                    "source": entry.get("source", ""),
                    "message": entry.get("message", ""),
                },
                timestamp,
            )
        return len(entries)

    def drain_network(self, driver) -> int:
        self._activate(driver)
        entries = read_driver_logs(driver, "performance")
        appended = 0
        for entry in entries:
            try:
                event = json.loads(entry["message"])["message"]
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            method = str(event.get("method", ""))
            if not method.startswith("Network."):
                continue
            timestamp = int(entry.get("timestamp") or time.time() * 1000)
            self._append(self._network, event, timestamp)
            self._track_request(event)
            appended += 1
        return appended

    def _track_request(self, event: dict) -> None:
        method = event.get("method", "")
        params = event.get("params", {})
        request_id = str(params.get("requestId", ""))
        now = time.monotonic()
        if method == "Network.requestWillBeSent" and request_id:
            request = params.get("request", {})
            url = str(request.get("url", ""))
            resource_type = str(params.get("type", ""))
            if url.startswith(("http://", "https://")) and resource_type not in {
                "EventSource",
                "WebSocket",
            }:
                self._inflight[request_id] = (now, url)
        elif method in {"Network.loadingFinished", "Network.loadingFailed"}:
            self._inflight.pop(request_id, None)
        self._last_network_activity = now

    def network_state(self, driver) -> dict:
        """Drain through the broker and report finite requests for network-idle waits."""
        self.drain_network(driver)
        now = time.monotonic()
        expired = [
            request_id
            for request_id, (started, _) in self._inflight.items()
            if now - started > self.max_inflight_age_seconds
        ]
        for request_id in expired:
            self._inflight.pop(request_id, None)
            self._ignored_long_running += 1
        return {
            "inflight": [
                {"request_id": request_id, "url": _redact_url(url)}
                for request_id, (_, url) in self._inflight.items()
            ],
            "quiet_ms": int((now - self._last_network_activity) * 1000),
            "ignored_long_running": self._ignored_long_running,
        }

    def read(
        self,
        kind: str,
        mode: str,
        cursor: int,
        limit: int,
        since_timestamp: int,
        redact: bool,
        log_level: str = "",
        filter_url_by_text: str = "",
        only_errors: bool = False,
        event_type: str = "all",
    ) -> dict:
        if mode not in {"peek", "consume"}:
            raise ValueError("mode must be 'peek' or 'consume'")
        if cursor < 0:
            raise ValueError("cursor must be zero or greater")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        buffer = self._console if kind == "console" else self._network
        normalized_level = log_level.strip().upper()
        if normalized_level == "ALL":
            normalized_level = ""
        if normalized_level == "ERROR":
            normalized_level = "SEVERE"
        if normalized_level not in {"", "DEBUG", "INFO", "WARNING", "SEVERE"}:
            raise ValueError(
                "log_level must be blank/ALL, DEBUG, INFO, WARNING, ERROR, or SEVERE"
            )
        normalized_event_type = event_type.strip().lower()
        if normalized_event_type not in _NETWORK_EVENT_PREFIXES:
            raise ValueError(
                "event_type must be all, request, response, finished, or failed"
            )

        matching = []
        for event in buffer.events:
            if event.cursor <= cursor or event.timestamp < since_timestamp:
                continue
            if kind == "console" and normalized_level:
                if event.payload.get("level") != normalized_level:
                    continue
            if kind == "network":
                event_prefix = _NETWORK_EVENT_PREFIXES[normalized_event_type]
                if event_prefix and not str(event.payload.get("method", "")).startswith(
                    event_prefix
                ):
                    continue
                if filter_url_by_text and filter_url_by_text not in _event_url(
                    event.payload
                ):
                    continue
                if only_errors and not _is_network_error(event.payload):
                    continue
            matching.append(event)

        selected = matching[:limit]
        if mode == "consume":
            buffer.consume({event.cursor for event in selected})
        events = []
        for event in selected:
            payload = redact_diagnostic(event.payload) if redact else event.payload
            events.append(
                {"cursor": event.cursor, "timestamp": event.timestamp, **payload}
            )
        return {
            "ok": True,
            "mode": mode,
            "events": events,
            "returned": len(events),
            "next_cursor": selected[-1].cursor if selected else cursor,
            "latest_cursor": self._cursor,
            "has_more": len(matching) > len(selected),
            "dropped_events": buffer.dropped_events,
        }


def _event_url(event: dict) -> str:
    params = event.get("params", {})
    return str(
        params.get("request", {}).get("url", "")
        or params.get("response", {}).get("url", "")
        or params.get("documentURL", "")
    )


def _is_network_error(event: dict) -> bool:
    if event.get("method") == "Network.loadingFailed":
        return True
    return event.get("params", {}).get("response", {}).get("status", 0) >= 400


diagnostics_broker = DiagnosticsBroker()


def response_body(driver, request_id: str) -> dict:
    try:
        response = driver.execute_cdp_cmd(
            "Network.getResponseBody", {"requestId": request_id}
        )
        return {
            "ok": True,
            "request_id": request_id,
            **response,
            "sensitive_data_warning": "Response bodies may contain sensitive data.",
        }
    except Exception as exc:
        raw_message = str(exc)
        lowered = raw_message.lower()
        if "evicted" in lowered:
            code = "response_body_evicted"
            message = "Chrome evicted this response body from its CDP buffer."
        elif "no resource" in lowered or "no data found" in lowered:
            code = "response_body_expired"
            message = "Chrome no longer has this response body in its CDP buffer."
        else:
            code = "response_body_unavailable"
            message = raw_message.split("Stacktrace:", 1)[0]
            message = re.split(r"\n\s*\(Session info:", message, maxsplit=1)[0]
            message = message.strip()[:_MAX_RESPONSE_ERROR_CHARS]
            if not message:
                message = "Chrome could not return this response body."
        return {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "hint": "Read network events promptly and retry the request if needed.",
            },
        }
