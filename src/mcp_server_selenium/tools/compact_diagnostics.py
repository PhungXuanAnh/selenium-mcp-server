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
_NETWORK_FILTER_KEYS = {"url_regex", "method", "resource_type", "request_id", "status"}


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
        self._request_metadata: dict[str, dict[str, Any]] = {}
        self._network_activity = deque(maxlen=network_limit * 2)
        self._network_epoch = time.monotonic()
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
        self._request_metadata = {}
        self._network_activity = deque(maxlen=self.network_limit * 2)
        self._network_epoch = time.monotonic()
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
            self._request_metadata[request_id] = {
                "request_id": request_id,
                "url": url,
                "method": str(request.get("method", "")).upper(),
                "resource_type": resource_type,
                "status": 0,
            }
            while len(self._request_metadata) > self.network_limit * 2:
                self._request_metadata.pop(next(iter(self._request_metadata)))
            if url.startswith(("http://", "https://")) and resource_type not in {
                "EventSource",
                "WebSocket",
            }:
                self._inflight[request_id] = (now, url)
        elif method == "Network.responseReceived" and request_id:
            response = params.get("response", {})
            metadata = self._request_metadata.setdefault(
                request_id,
                {"request_id": request_id, "method": "", "status": 0},
            )
            metadata.update(
                {
                    "url": str(response.get("url", metadata.get("url", ""))),
                    "resource_type": str(
                        params.get("type", metadata.get("resource_type", ""))
                    ),
                    "status": int(response.get("status", 0) or 0),
                }
            )
        elif method in {"Network.loadingFinished", "Network.loadingFailed"}:
            self._inflight.pop(request_id, None)
        metadata = self.event_metadata(event)
        self._network_activity.append((now, metadata.get("url", "")))
        self._last_network_activity = now

    def network_state(self, driver, ignore_url_regexes=None) -> dict:
        """Drain through the broker and report finite requests for network-idle waits."""
        patterns = ignore_url_regexes or []
        if not isinstance(patterns, list) or len(patterns) > 20:
            raise ValueError("ignore_url_regexes must be a list with at most 20 entries")
        compiled = []
        for pattern in patterns:
            if not isinstance(pattern, str) or len(pattern) > 500:
                raise ValueError("ignore_url_regexes entries must be strings up to 500 characters")
            compiled.append(re.compile(pattern))

        def ignored(url):
            return any(pattern.search(url) for pattern in compiled)

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
        inflight = [
            (request_id, url)
            for request_id, (_, url) in self._inflight.items()
            if not ignored(url)
        ]
        ignored_inflight = len(self._inflight) - len(inflight)
        if compiled:
            relevant_activity = [
                activity
                for activity, url in self._network_activity
                if not ignored(url)
            ]
            last_activity = max(relevant_activity, default=self._network_epoch)
        else:
            last_activity = self._last_network_activity
        return {
            "inflight": [
                {"request_id": request_id, "url": _redact_url(url)}
                for request_id, url in inflight
            ],
            "quiet_ms": int((now - last_activity) * 1000),
            "ignored_inflight": ignored_inflight,
            "ignored_url_patterns": len(compiled),
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
        filters: dict | None = None,
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
        normalized_filters = normalize_network_filters(filters or {})

        matching = []
        for event in buffer.events:
            if event.cursor <= cursor or event.timestamp < since_timestamp:
                continue
            if kind == "console" and normalized_level:
                if event.payload.get("level") != normalized_level:
                    continue
            if kind == "network":
                metadata = self.event_metadata(event.payload)
                event_prefix = _NETWORK_EVENT_PREFIXES[normalized_event_type]
                if event_prefix and not str(event.payload.get("method", "")).startswith(
                    event_prefix
                ):
                    continue
                if filter_url_by_text and filter_url_by_text not in _event_url(
                    event.payload, metadata
                ):
                    continue
                if not _matches_network_filters(metadata, normalized_filters):
                    continue
                if only_errors and not _is_network_error(event.payload, metadata):
                    continue
            matching.append(event)

        selected = matching[:limit]
        if mode == "consume":
            buffer.consume({event.cursor for event in selected})
        events = []
        for event in selected:
            payload = redact_diagnostic(event.payload) if redact else event.payload
            item = {"cursor": event.cursor, "timestamp": event.timestamp, **payload}
            if kind == "network":
                correlation = self.event_metadata(event.payload)
                item["correlation"] = (
                    redact_diagnostic(correlation) if redact else correlation
                )
            events.append(item)
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

    def event_metadata(self, event: dict) -> dict:
        params = event.get("params", {})
        request_id = str(params.get("requestId", ""))
        metadata = dict(self._request_metadata.get(request_id, {}))
        request = params.get("request", {})
        response = params.get("response", {})
        metadata.update(
            {
                "request_id": request_id,
                "url": str(
                    request.get("url", "")
                    or response.get("url", "")
                    or params.get("documentURL", "")
                    or metadata.get("url", "")
                ),
                "method": str(
                    request.get("method", "") or metadata.get("method", "")
                ).upper(),
                "resource_type": str(
                    params.get("type", "") or metadata.get("resource_type", "")
                ),
                "status": int(
                    response.get("status", 0)
                    or params.get("statusCode", 0)
                    or metadata.get("status", 0)
                    or 0
                ),
            }
        )
        return metadata

    def matching_network_events(self, driver, cursor: int, filters: dict) -> list[dict]:
        """Return unconsumed matching response events for route-aware waits."""
        self.drain_network(driver)
        normalized = normalize_network_filters(filters)
        matches = []
        for event in self._network.events:
            if event.cursor <= cursor:
                continue
            if event.payload.get("method") != "Network.responseReceived":
                continue
            metadata = self.event_metadata(event.payload)
            if _matches_network_filters(metadata, normalized):
                matches.append(
                    {
                        "cursor": event.cursor,
                        "timestamp": event.timestamp,
                        "event": event.payload,
                        "metadata": metadata,
                    }
                )
        return matches


def normalize_network_filters(filters: dict) -> dict:
    if not isinstance(filters, dict):
        raise ValueError("filters must be an object")
    unknown = sorted(set(filters) - _NETWORK_FILTER_KEYS)
    if unknown:
        raise ValueError("Unsupported network filters: " + ", ".join(unknown))
    normalized = dict(filters)
    url_regex = normalized.get("url_regex", "")
    if not isinstance(url_regex, str):
        raise ValueError("filters.url_regex must be a string")
    if url_regex:
        re.compile(url_regex)
    for key in ("method", "resource_type", "request_id"):
        if key in normalized and not isinstance(normalized[key], str):
            raise ValueError(f"filters.{key} must be a string")
    if "status" in normalized:
        status = normalized["status"]
        if not isinstance(status, int) or not 100 <= status <= 599:
            raise ValueError("filters.status must be an integer from 100 to 599")
    normalized["method"] = normalized.get("method", "").upper()
    normalized["resource_type"] = normalized.get("resource_type", "").lower()
    return normalized


def _matches_network_filters(metadata: dict, filters: dict) -> bool:
    if filters.get("url_regex") and not re.search(
        filters["url_regex"], metadata.get("url", "")
    ):
        return False
    if filters.get("method") and filters["method"] != metadata.get("method", ""):
        return False
    if filters.get("resource_type") and filters["resource_type"] != str(
        metadata.get("resource_type", "")
    ).lower():
        return False
    if filters.get("request_id") and filters["request_id"] != metadata.get(
        "request_id", ""
    ):
        return False
    if filters.get("status") and filters["status"] != metadata.get("status", 0):
        return False
    return True


def _event_url(event: dict, metadata: dict | None = None) -> str:
    params = event.get("params", {})
    return str(
        params.get("request", {}).get("url", "")
        or params.get("response", {}).get("url", "")
        or params.get("documentURL", "")
        or (metadata or {}).get("url", "")
    )


def _is_network_error(event: dict, metadata: dict | None = None) -> bool:
    if event.get("method") == "Network.loadingFailed":
        return True
    return (
        event.get("params", {}).get("response", {}).get("status", 0)
        or (metadata or {}).get("status", 0)
    ) >= 400


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
