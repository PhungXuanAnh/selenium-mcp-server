"""Truthful navigation policies for the experimental compact profile."""

import json
import time

from .compact_waits import page_snapshot, wait_for_result

_WAIT_POLICIES = {"initiated", "interactive", "complete", "network_idle"}


def normalize_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    normalized = url.strip()
    if not normalized.startswith(("http://", "https://")):
        normalized = "https://" + normalized
    return normalized


def navigate_result(
    driver,
    url: str,
    wait_until: str = "complete",
    timeout: float = 60,
    quiet_ms: int = 500,
) -> dict:
    started = time.monotonic()
    try:
        requested_url = normalize_url(url)
        if wait_until not in _WAIT_POLICIES:
            raise ValueError(
                "wait_until must be initiated, interactive, complete, or network_idle"
            )
        if not 0 <= timeout <= 120:
            raise ValueError("timeout must be between 0 and 120 seconds")
        if not 0 <= quiet_ms <= 10000:
            raise ValueError("quiet_ms must be between 0 and 10000")
    except ValueError as exc:
        snapshot = page_snapshot(driver)
        return {
            "ok": False,
            "timed_out": False,
            "wait_until": wait_until,
            "error": {"code": "invalid_navigation", "message": str(exc)},
            "final_url": snapshot.pop("url"),
            **snapshot,
        }

    try:
        cdp_result = driver.execute_cdp_cmd("Page.navigate", {"url": requested_url})
    except Exception as exc:
        snapshot = page_snapshot(driver)
        return {
            "ok": False,
            "timed_out": False,
            "requested_url": requested_url,
            "final_url": snapshot.pop("url"),
            "wait_until": wait_until,
            "error": {"code": "navigation_failed", "message": str(exc)},
            **snapshot,
        }

    if cdp_result.get("errorText"):
        snapshot = page_snapshot(driver)
        return {
            "ok": False,
            "timed_out": False,
            "requested_url": requested_url,
            "final_url": snapshot.pop("url"),
            "wait_until": wait_until,
            "error": {
                "code": "navigation_rejected",
                "message": cdp_result["errorText"],
            },
            **snapshot,
        }

    if wait_until == "initiated":
        snapshot = page_snapshot(driver)
        return {
            "ok": True,
            "timed_out": False,
            "navigation_pending": True,
            "requested_url": requested_url,
            "final_url": snapshot.pop("url") or None,
            "wait_until": wait_until,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "navigation": cdp_result,
            **snapshot,
        }

    remaining = max(0, timeout - (time.monotonic() - started))
    first_condition = "ready"
    first_state = "interactive" if wait_until == "network_idle" else wait_until
    readiness = wait_for_result(
        driver,
        first_condition,
        state=first_state,
        timeout=remaining,
    )
    phases = {"ready": readiness}
    final_wait = readiness
    if readiness["ok"] and wait_until == "network_idle":
        remaining = max(0, timeout - (time.monotonic() - started))
        final_wait = wait_for_result(
            driver,
            "network_idle",
            timeout=remaining,
            quiet_ms=quiet_ms,
        )
        phases["network_idle"] = final_wait

    snapshot = page_snapshot(driver)
    result = {
        "ok": bool(final_wait["ok"]),
        "timed_out": bool(final_wait.get("timed_out")),
        "navigation_pending": False,
        "requested_url": requested_url,
        "final_url": snapshot.pop("url"),
        "wait_until": wait_until,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "navigation": cdp_result,
        "phases": phases,
        **snapshot,
    }
    if "error" in final_wait:
        result["error"] = final_wait["error"]
    return result


def navigate_json(driver, *args, **kwargs) -> str:
    return json.dumps(navigate_result(driver, *args, **kwargs), ensure_ascii=False)
