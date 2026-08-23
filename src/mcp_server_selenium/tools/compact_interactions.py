"""Retrying, postcondition-reporting interactions for the compact profile."""

import json
from pathlib import Path
import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

from ..server import get_workspace_root
from .compact_locator import LocatorReferenceError, resolved_element

_ACTIONS = {
    "click",
    "clear",
    "type",
    "set_value",
    "press_key",
    "select_option",
    "hover",
    "scroll_into_view",
    "upload_file",
}
_RETRIABLE = (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
)
_MAX_ATTEMPTS = 5
_SET_VALUE_SCRIPT = """
const element = arguments[0];
const value = arguments[1];
let prototype = Object.getPrototypeOf(element);
let descriptor = null;
while (prototype && !descriptor) {
  descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
  prototype = Object.getPrototypeOf(prototype);
}
if (descriptor && descriptor.set) descriptor.set.call(element, value);
else element.value = value;
element.dispatchEvent(new Event('input', {bubbles: true}));
element.dispatchEvent(new Event('change', {bubbles: true}));
return element.value;
"""
_DISPATCH_VALUE_EVENTS_SCRIPT = """
arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
return arguments[0].value;
"""


def _safe(callable_, default=None):
    try:
        return callable_()
    except Exception:
        return default


def _element_state(element) -> dict:
    return {
        "tag_name": _safe(lambda: element.tag_name, "unknown"),
        "id": _safe(lambda: element.get_attribute("id"), "") or "",
        "value": _safe(lambda: element.get_attribute("value"), None),
        "text": (_safe(lambda: element.text, "") or "")[:500],
        "visible": bool(_safe(element.is_displayed, False)),
        "enabled": bool(_safe(element.is_enabled, False)),
        "selected": bool(_safe(lambda: element.is_selected(), False)),
    }


def _resolve_upload_path(file_path: str) -> Path:
    if not file_path.strip():
        raise ValueError("file_path is required for upload_file")
    requested = Path(file_path).expanduser()
    if not requested.is_absolute():
        if ".." in requested.parts:
            raise ValueError("relative file_path cannot contain path traversal")
        requested = get_workspace_root() / requested
    resolved = requested.resolve()
    if not resolved.is_file():
        raise ValueError(f"Upload file does not exist or is not a file: {resolved}")
    return resolved


def _validate_action(
    action,
    element_ref,
    input_value,
    key,
    option_by,
    option_value,
    file_path,
    timeout,
):
    if action not in _ACTIONS:
        raise ValueError("Unsupported interaction action")
    if not element_ref.strip():
        raise ValueError("element_ref is required")
    if not 0 <= timeout <= 60:
        raise ValueError("timeout must be between 0 and 60 seconds")
    if action == "type" and input_value == "":
        raise ValueError("input_value is required for type")
    if action == "press_key" and not key:
        raise ValueError("key is required for press_key")
    if action == "select_option":
        if option_by not in {"value", "text", "index"}:
            raise ValueError("option_by must be value, text, or index")
        if option_value == "":
            raise ValueError("option_value is required for select_option")
        if option_by == "index":
            int(option_value)
    if action == "upload_file":
        return _resolve_upload_path(file_path)
    return None


def _perform(
    driver,
    element,
    action,
    input_value,
    key,
    option_by,
    option_value,
    upload_path,
):
    if action in {"click", "hover", "select_option", "upload_file"}:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
            element,
        )
    if action == "click":
        if not element.is_displayed() or not element.is_enabled():
            raise ElementNotInteractableException("Element is not visible and enabled")
        element.click()
        return {"mode": "browser_native", "events": ["click"]}
    if action == "clear":
        element.clear()
        return {"mode": "browser_native", "events": ["input", "change"]}
    if action == "type":
        element.send_keys(input_value)
        return {"mode": "browser_native", "events": ["keyboard", "input"]}
    if action == "set_value":
        element.clear()
        if input_value:
            element.send_keys(input_value)
        actual = element.get_attribute("value") or ""
        if actual != input_value:
            actual = driver.execute_script(
                _SET_VALUE_SCRIPT, element, input_value
            )
        else:
            actual = driver.execute_script(_DISPATCH_VALUE_EVENTS_SCRIPT, element)
        if actual != input_value:
            raise ElementNotInteractableException(
                f"Expected value {input_value!r}, observed {actual!r}"
            )
        return {"mode": "explicit", "events": ["input", "change"]}
    if action == "press_key":
        normalized = key.strip().upper().replace(" ", "_").replace("-", "_")
        element.send_keys(getattr(Keys, normalized, key))
        return {"mode": "browser_native", "events": ["keyboard"]}
    if action == "select_option":
        select = Select(element)
        if option_by == "value":
            select.select_by_value(option_value)
        elif option_by == "text":
            select.select_by_visible_text(option_value)
        else:
            select.select_by_index(int(option_value))
        return {
            "mode": "browser_native",
            "events": ["input", "change"],
            "selected": [option.text for option in select.all_selected_options][
                :20
            ],
        }
    if action == "hover":
        ActionChains(driver).move_to_element(element).perform()
        return {"mode": "browser_native", "events": ["mouseover", "mouseenter"]}
    if action == "scroll_into_view":
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
            element,
        )
        return {"mode": "script", "events": []}
    element.send_keys(str(upload_path))
    return {
        "mode": "browser_native",
        "events": ["input", "change"],
        "uploaded_file": str(upload_path),
        "sensitive_data_warning": "Uploaded files leave the local workspace boundary.",
    }


def interact_result(
    driver,
    action: str,
    element_ref: str,
    input_value: str = "",
    key: str = "",
    option_by: str = "value",
    option_value: str = "",
    file_path: str = "",
    timeout: float = 10,
) -> dict:
    started = time.monotonic()
    before_url = _safe(lambda: driver.current_url, "")
    try:
        upload_path = _validate_action(
            action,
            element_ref,
            input_value,
            key,
            option_by,
            option_value,
            file_path,
            timeout,
        )
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "action": action,
            "error": {"code": "invalid_interaction", "message": str(exc)},
        }

    deadline = started + timeout
    attempts = 0
    while attempts < _MAX_ATTEMPTS:
        attempts += 1
        try:
            with resolved_element(driver, element_ref) as element:
                event_result = _perform(
                    driver,
                    element,
                    action,
                    input_value,
                    key,
                    option_by,
                    option_value,
                    upload_path,
                )
                state = _element_state(element)
            after_url = _safe(lambda: driver.current_url, "")
            return {
                "ok": True,
                "action": action,
                "attempts": attempts,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "url": {
                    "before": before_url,
                    "after": after_url,
                    "changed": before_url != after_url,
                },
                "element": state,
                "event_dispatch": event_result,
            }
        except LocatorReferenceError as exc:
            if exc.code != "element_ref_not_resolved":
                return {
                    "ok": False,
                    "action": action,
                    "attempts": attempts,
                    "error": {"code": exc.code, "message": str(exc)},
                }
            last_error = str(exc)
        except _RETRIABLE as exc:
            last_error = str(exc)
        except Exception as exc:
            return {
                "ok": False,
                "action": action,
                "attempts": attempts,
                "error": {"code": "interaction_failed", "message": str(exc)},
            }

        now = time.monotonic()
        if attempts >= _MAX_ATTEMPTS or now >= deadline:
            return {
                "ok": False,
                "action": action,
                "attempts": attempts,
                "timed_out": now >= deadline,
                "error": {
                    "code": "interaction_retry_exhausted",
                    "message": last_error,
                },
            }
        time.sleep(min(0.1, deadline - now))


def interact_json(driver, *args, **kwargs) -> str:
    return json.dumps(interact_result(driver, *args, **kwargs), ensure_ascii=False)
