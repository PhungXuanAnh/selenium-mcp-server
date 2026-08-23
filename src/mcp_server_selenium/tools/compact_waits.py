"""Deterministic condition waits for the experimental compact profile."""

import json
import re
import time

from selenium.webdriver.common.by import By

from .compact_diagnostics import diagnostics_broker
from .compact_locator import (
    LocatorReferenceError,
    matching_elements,
    validate_selector,
)

_CONDITIONS = {"ready", "url", "element", "text", "network_idle"}
_ELEMENT_STATES = {"present", "visible", "enabled", "hidden"}
_TEXT_STATES = {"present", "absent"}
_MATCH_MODES = {"contains", "equals", "regex"}


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
):
    if condition not in _CONDITIONS:
        raise ValueError("condition must be ready, url, element, text, or network_idle")
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
    return state, selector


def _observe(driver, condition, state, value, selector, match, quiet_ms):
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

    observation = diagnostics_broker.network_state(driver)
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
) -> dict:
    started = time.monotonic()
    try:
        state, selector = _validate(
            condition,
            state,
            value,
            selector,
            match,
            timeout,
            poll_interval,
            quiet_ms,
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
                driver, condition, state, value, selector, match, quiet_ms
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
