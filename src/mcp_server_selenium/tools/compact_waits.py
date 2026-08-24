"""Deterministic condition waits for the experimental compact profile."""

import json
import base64
import re
import time

from selenium.webdriver.common.by import By

from .compact_diagnostics import (
    diagnostics_broker,
    normalize_network_filters,
    redact_diagnostic,
    response_body,
)
from .compact_locator import (
    LocatorReferenceError,
    matching_elements,
    validate_selector,
)

_CONDITIONS = {
    "ready",
    "url",
    "element",
    "text",
    "network_idle",
    "network_response",
    "all",
    "any",
}
_ELEMENT_STATES = {"present", "visible", "enabled", "hidden"}
_TEXT_STATES = {"present", "absent"}
_MATCH_MODES = {"contains", "equals", "regex"}
_MAX_WAIT_RESPONSE_BYTES = 1_000_000
_MISSING = object()


def page_snapshot(driver) -> dict:
    try:
        ready_state = str(driver.execute_script("return document.readyState"))
    except Exception:
        ready_state = "unknown"
    try:
        url = str(driver.current_url)
    except Exception:
        url = ""
    return {"url": url, "ready_state": ready_state}


def _matches(observed: str, expected: str, mode: str) -> bool:
    if mode == "contains":
        return expected in observed
    if mode == "equals":
        return expected == observed
    return re.search(expected, observed) is not None


def _validate(
    condition: str,
    state: str,
    value: str,
    selector,
    match: str,
    timeout: float,
    poll_interval: float,
    quiet_ms: int,
    options: dict,
    depth: int = 0,
):
    if condition not in _CONDITIONS:
        raise ValueError(
            "condition must be ready, url, element, text, network_idle, network_response, all, or any"
        )
    if not 0 <= timeout <= 120:
        raise ValueError("timeout must be between 0 and 120 seconds")
    if not 0.05 <= poll_interval <= 2:
        raise ValueError("poll_interval must be between 0.05 and 2 seconds")
    if not 0 <= quiet_ms <= 10000:
        raise ValueError("quiet_ms must be between 0 and 10000")
    if match not in _MATCH_MODES:
        raise ValueError("match must be contains, equals, or regex")
    if match == "regex" and value:
        re.compile(value)
    if not isinstance(options, dict):
        raise ValueError("options must be an object")

    if condition == "ready":
        state = state or "complete"
        if state not in {"interactive", "complete"}:
            raise ValueError("ready state must be interactive or complete")
    elif condition == "url" and not value:
        raise ValueError("value is required for a URL wait")
    elif condition == "element":
        state = state or "visible"
        if state not in _ELEMENT_STATES:
            raise ValueError(
                "element state must be present, visible, enabled, or hidden"
            )
        if selector is None:
            raise ValueError("selector is required for an element wait")
        selector = validate_selector(selector)
    elif condition == "text":
        state = state or "present"
        if state not in _TEXT_STATES:
            raise ValueError("text state must be present or absent")
        if not value:
            raise ValueError("value is required for a text wait")
        if selector is not None:
            selector = validate_selector(selector)
    elif condition == "network_response":
        unknown = sorted(set(options) - {"cursor", "filters", "json_predicate"})
        if unknown:
            raise ValueError(
                "Unsupported network_response options: " + ", ".join(unknown)
            )
        cursor = options.get("cursor", 0)
        if not isinstance(cursor, int) or cursor < 0:
            raise ValueError("options.cursor must be an integer zero or greater")
        options = dict(options)
        options["filters"] = normalize_network_filters(options.get("filters", {}))
        predicate = options.get("json_predicate", {})
        if not isinstance(predicate, dict) or len(predicate) > 20:
            raise ValueError("options.json_predicate must be an object with at most 20 paths")
        for path in predicate:
            if not isinstance(path, str) or not path or len(path) > 200:
                raise ValueError("JSON predicate paths must be non-empty strings up to 200 characters")
        if len(json.dumps(predicate, ensure_ascii=False).encode()) > 4096:
            raise ValueError("options.json_predicate must be at most 4096 bytes")
    elif condition == "network_idle":
        unknown = sorted(set(options) - {"ignore_url_regexes"})
        if unknown:
            raise ValueError(
                "Unsupported network_idle options: " + ", ".join(unknown)
            )
        patterns = options.get("ignore_url_regexes", [])
        if not isinstance(patterns, list) or len(patterns) > 20:
            raise ValueError(
                "options.ignore_url_regexes must be a list with at most 20 entries"
            )
        for pattern in patterns:
            if not isinstance(pattern, str) or len(pattern) > 500:
                raise ValueError(
                    "ignore_url_regexes entries must be strings up to 500 characters"
                )
            re.compile(pattern)
    elif condition in {"all", "any"}:
        if depth >= 3:
            raise ValueError("composed wait depth must not exceed 3")
        unknown = sorted(set(options) - {"conditions"})
        if unknown:
            raise ValueError(
                f"Unsupported {condition} options: " + ", ".join(unknown)
            )
        clauses = options.get("conditions")
        if not isinstance(clauses, list) or not 1 <= len(clauses) <= 10:
            raise ValueError("options.conditions must contain 1 to 10 wait clauses")
        options = dict(options)
        options["conditions"] = [
            _validate_clause(clause, depth + 1) for clause in clauses
        ]
    elif options:
        raise ValueError(f"options are not supported for condition={condition}")
    return state, selector, options


def _validate_clause(clause: dict, depth: int) -> dict:
    if not isinstance(clause, dict):
        raise ValueError("Each composed wait clause must be an object")
    allowed = {"condition", "state", "value", "selector", "match", "quiet_ms", "options"}
    unknown = sorted(set(clause) - allowed)
    if unknown:
        raise ValueError("Unsupported composed wait fields: " + ", ".join(unknown))
    condition = clause.get("condition", "")
    state, selector, options = _validate(
        condition,
        clause.get("state", ""),
        clause.get("value", ""),
        clause.get("selector"),
        clause.get("match", "contains"),
        0,
        0.1,
        clause.get("quiet_ms", 500),
        clause.get("options", {}),
        depth,
    )
    return {
        "condition": condition,
        "state": state,
        "value": clause.get("value", ""),
        "selector": selector,
        "match": clause.get("match", "contains"),
        "quiet_ms": clause.get("quiet_ms", 500),
        "options": options,
    }


def _json_path(value, path: str):
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def _bounded_value(value):
    encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded) <= 500:
        return value
    return encoded[:500] + "…"


def _redacted_predicate_value(path: str, value):
    key = path.rsplit(".", 1)[-1]
    return redact_diagnostic({key: _bounded_value(value)})[key]


def _observe_network_response(driver, options: dict):
    cursor = options.get("cursor", 0)
    filters = options.get("filters", {})
    predicate = options.get("json_predicate", {})
    matches = diagnostics_broker.matching_network_events(driver, cursor, filters)
    last_observation = {
        "cursor": cursor,
        "matched_responses": len(matches),
        "filter_keys": sorted(key for key, item in filters.items() if item),
    }
    for match_event in matches:
        metadata = match_event["metadata"]
        observation = {
            "cursor": match_event["cursor"],
            "response": redact_diagnostic(metadata),
            "json_predicate": {},
        }
        if not predicate:
            return True, observation
        body_result = response_body(driver, metadata.get("request_id", ""))
        if not body_result.get("ok"):
            observation["body_state"] = body_result.get("error", {})
            last_observation = observation
            continue
        body = body_result.get("body", "")
        if body_result.get("base64Encoded"):
            try:
                body = base64.b64decode(body).decode("utf-8")
            except Exception:
                observation["body_state"] = {"code": "response_body_decode_failed"}
                last_observation = observation
                continue
        if len(body.encode()) > _MAX_WAIT_RESPONSE_BYTES:
            observation["body_state"] = {
                "code": "response_body_too_large",
                "limit_bytes": _MAX_WAIT_RESPONSE_BYTES,
            }
            last_observation = observation
            continue
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            observation["body_state"] = {"code": "response_body_not_json"}
            last_observation = observation
            continue
        passed = True
        for path, expected in predicate.items():
            observed = _json_path(parsed, path)
            matched = observed is not _MISSING and observed == expected
            passed = passed and matched
            observation["json_predicate"][path] = {
                "matched": matched,
                "expected": _redacted_predicate_value(path, expected),
                "observed": (
                    "[MISSING]"
                    if observed is _MISSING
                    else _redacted_predicate_value(path, observed)
                ),
            }
        observation["body_state"] = {"code": "json_evaluated"}
        if passed:
            return True, observation
        last_observation = observation
    return False, last_observation


def _observe(driver, condition, state, value, selector, match, quiet_ms, options):
    if condition in {"all", "any"}:
        observations = []
        satisfied_values = []
        for clause in options["conditions"]:
            satisfied, observation = _observe(
                driver,
                clause["condition"],
                clause["state"],
                clause["value"],
                clause["selector"],
                clause["match"],
                clause["quiet_ms"],
                clause["options"],
            )
            satisfied_values.append(satisfied)
            observations.append(
                {
                    "condition": clause["condition"],
                    "satisfied": satisfied,
                    "observation": observation,
                }
            )
        combined = all(satisfied_values) if condition == "all" else any(satisfied_values)
        return combined, {"operator": condition, "conditions": observations}

    if condition == "ready":
        ready_state = page_snapshot(driver)["ready_state"]
        satisfied = ready_state == "complete" or (
            state == "interactive" and ready_state == "interactive"
        )
        return satisfied, {"ready_state": ready_state, "expected": state}

    if condition == "url":
        observed = page_snapshot(driver)["url"]
        return _matches(observed, value, match), {
            "url": observed,
            "expected": value,
            "match": match,
        }

    if condition == "element":
        with matching_elements(driver, selector) as (_, elements):
            visible = sum(element.is_displayed() for element in elements)
            enabled = sum(
                element.is_displayed() and element.is_enabled() for element in elements
            )
        observation = {
            "matched": len(elements),
            "visible": visible,
            "enabled": enabled,
            "expected": state,
        }
        if state == "present":
            return bool(elements), observation
        if state == "visible":
            return visible > 0, observation
        if state == "enabled":
            return enabled > 0, observation
        return visible == 0, observation

    if condition == "text":
        if selector is None:
            try:
                observed = str(
                    driver.execute_script(
                        "return document.body ? document.body.innerText : ''"
                    )
                )
            except Exception:
                observed = driver.find_element(By.TAG_NAME, "body").text
        else:
            with matching_elements(driver, selector) as (_, elements):
                observed = "\n".join(element.text or "" for element in elements)
        found = _matches(observed, value, match)
        return (found if state == "present" else not found), {
            "matched": found,
            "expected": value,
            "state": state,
            "sample": observed[:500],
        }

    if condition == "network_response":
        return _observe_network_response(driver, options)

    observation = diagnostics_broker.network_state(
        driver, options.get("ignore_url_regexes", [])
    )
    satisfied = not observation["inflight"] and observation["quiet_ms"] >= quiet_ms
    observation["expected_quiet_ms"] = quiet_ms
    return satisfied, observation


def wait_for_result(
    driver,
    condition: str,
    state: str = "",
    value: str = "",
    selector=None,
    match: str = "contains",
    timeout: float = 30,
    poll_interval: float = 0.1,
    quiet_ms: int = 500,
    options: dict = {},
) -> dict:
    started = time.monotonic()
    try:
        state, selector, options = _validate(
            condition,
            state,
            value,
            selector,
            match,
            timeout,
            poll_interval,
            quiet_ms,
            options,
        )
    except (ValueError, re.error) as exc:
        return {
            "ok": False,
            "timed_out": False,
            "condition": condition,
            "error": {"code": "invalid_wait", "message": str(exc)},
            **page_snapshot(driver),
        }

    deadline = started + timeout
    last_observation = {}
    last_error = ""
    while True:
        try:
            satisfied, last_observation = _observe(
                driver, condition, state, value, selector, match, quiet_ms, options
            )
            last_error = ""
            if satisfied:
                return {
                    "ok": True,
                    "timed_out": False,
                    "condition": condition,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "observation": last_observation,
                    **page_snapshot(driver),
                }
        except LocatorReferenceError as exc:
            return {
                "ok": False,
                "timed_out": False,
                "condition": condition,
                "error": {"code": exc.code, "message": str(exc)},
                **page_snapshot(driver),
            }
        except Exception as exc:
            last_error = str(exc)

        now = time.monotonic()
        if now >= deadline:
            result = {
                "ok": False,
                "timed_out": True,
                "condition": condition,
                "elapsed_ms": int((now - started) * 1000),
                "observation": last_observation,
                **page_snapshot(driver),
            }
            if last_error:
                result["last_error"] = last_error
            return result
        time.sleep(min(poll_interval, deadline - now))


def wait_for_json(driver, *args, **kwargs) -> str:
    return json.dumps(
        wait_for_result(driver, *args, **kwargs), ensure_ascii=False
    )
