"""Retrying, postcondition-reporting interactions for the compact profile."""

import json
from pathlib import Path
import secrets
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
from .compact_actionability import geometry_signature, inspect_actionability
from .compact_locator import (
    LocatorReferenceError,
    matching_elements,
    resolved_element,
    validate_selector,
)

_ACTIONS = {
    "inspect",
    "scroll",
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
_MAX_ATTEMPTS = 50
_CLICK_MODES = {"native", "actions", "javascript"}
_CLICK_OPTION_KEYS = {"click_mode", "offset", "stability_ms", "observe_ms"}
_INPUT_MODES = {"auto", "keyboard", "dom"}
_TARGET_KINDS = {"auto", "form_control", "contenteditable"}
_INPUT_TYPES = {"insertText", "insertFromPaste"}
_INPUT_OPTION_KEYS = {
    "target_kind",
    "input_mode",
    "input_type",
    "clear_existing",
    "verify_after_input",
    "expected_value",
    "observe_ms",
}
_SCROLL_OPTION_KEYS = {
    "direction",
    "amount",
    "to",
    "until_visible",
    "max_steps",
    "step_delay_ms",
    "include_nested_scroll_containers",
}
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
_TARGET_KIND_SCRIPT = """
const element = arguments[0];
if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
  return 'form_control';
}
if (element.isContentEditable || element.getAttribute('contenteditable') === 'true') {
  return 'contenteditable';
}
return 'unsupported';
"""
_CONTENTEDITABLE_INPUT_SCRIPT = """
const element = arguments[0];
const value = arguments[1];
const clearExisting = arguments[2];
const inputType = arguments[3];
element.focus();
if (clearExisting) element.replaceChildren();
const selection = element.ownerDocument.getSelection();
const range = element.ownerDocument.createRange();
range.selectNodeContents(element);
range.collapse(false);
selection.removeAllRanges();
selection.addRange(range);
const beforeInput = new InputEvent('beforeinput', {
  bubbles: true,
  cancelable: true,
  data: value,
  inputType
});
const accepted = element.dispatchEvent(beforeInput);
if (!accepted) {
  return {accepted: false, text: element.innerText || element.textContent || ''};
}
let inserted = false;
try { inserted = document.execCommand('insertText', false, value); }
catch (_) { inserted = false; }
if (!inserted) {
  const activeSelection = element.ownerDocument.getSelection();
  const activeRange = activeSelection && activeSelection.rangeCount
    ? activeSelection.getRangeAt(0)
    : range;
  activeRange.deleteContents();
  const textNode = element.ownerDocument.createTextNode(value);
  activeRange.insertNode(textNode);
  activeRange.setStartAfter(textNode);
  activeRange.collapse(true);
  activeSelection.removeAllRanges();
  activeSelection.addRange(activeRange);
}
element.dispatchEvent(new InputEvent('input', {
  bubbles: true,
  data: value,
  inputType
}));
element.dispatchEvent(new Event('change', {bubbles: true}));
return {accepted: true, text: element.innerText || element.textContent || ''};
"""
_CLEAR_CONTENTEDITABLE_SCRIPT = """
const element = arguments[0];
element.focus();
element.replaceChildren();
element.dispatchEvent(new InputEvent('input', {
  bubbles: true,
  data: null,
  inputType: 'deleteContentBackward'
}));
element.dispatchEvent(new Event('change', {bubbles: true}));
return element.innerText || element.textContent || '';
"""
_SCROLL_SCRIPT = """
const requestedContainer = arguments[0];
const direction = arguments[1];
const amount = arguments[2];
const destination = arguments[3];
const includeNested = arguments[4];
const candidates = [];
const seen = new Set();
function add(node) {
  if (!node || seen.has(node) || candidates.length >= 50) return;
  seen.add(node);
  candidates.push(node);
}
if (requestedContainer) {
  add(requestedContainer);
} else {
  add(document.scrollingElement);
  if (includeNested) {
    const nodes = document.querySelectorAll('*');
    const limit = Math.min(nodes.length, 2000);
    for (let index = 0; index < limit; index += 1) {
      const node = nodes[index];
      const style = getComputedStyle(node);
      const vertical = /(auto|scroll|overlay)/.test(style.overflowY) && node.scrollHeight > node.clientHeight;
      const horizontal = /(auto|scroll|overlay)/.test(style.overflowX) && node.scrollWidth > node.clientWidth;
      if (vertical || horizontal) add(node);
    }
  }
}
const states = [];
for (const node of candidates) {
  const beforeLeft = node.scrollLeft;
  const beforeTop = node.scrollTop;
  if (destination === 'start') {
    if (direction === 'left' || direction === 'right') node.scrollLeft = 0;
    else node.scrollTop = 0;
  } else if (destination === 'end') {
    if (direction === 'left' || direction === 'right') node.scrollLeft = node.scrollWidth;
    else node.scrollTop = node.scrollHeight;
  } else if (direction === 'up') {
    node.scrollTop -= amount;
  } else if (direction === 'down') {
    node.scrollTop += amount;
  } else if (direction === 'left') {
    node.scrollLeft -= amount;
  } else {
    node.scrollLeft += amount;
  }
  states.push({
    tag_name: node === document.scrollingElement ? 'document' : String(node.tagName || '').toLowerCase(),
    id: node.id || '',
    before: {left: Math.round(beforeLeft), top: Math.round(beforeTop)},
    after: {left: Math.round(node.scrollLeft), top: Math.round(node.scrollTop)},
    maximum: {
      left: Math.max(0, Math.round(node.scrollWidth - node.clientWidth)),
      top: Math.max(0, Math.round(node.scrollHeight - node.clientHeight))
    }
  });
}
return {
  scanned_nodes: includeNested && !requestedContainer ? Math.min(document.querySelectorAll('*').length, 2000) : 0,
  scan_truncated: Boolean(includeNested && !requestedContainer && document.querySelectorAll('*').length > 2000),
  containers: states,
  changed: states.filter(state => state.before.left !== state.after.left || state.before.top !== state.after.top).length
};
"""
_START_OBSERVATION_SCRIPT = """
const key = arguments[0];
function focusState() {
  const active = document.activeElement;
  return {
    tag_name: active && active.tagName ? active.tagName.toLowerCase() : '',
    id: active && active.id || '',
    role: active && active.getAttribute && active.getAttribute('role') || ''
  };
}
const record = {mutations: 0, focus_before: focusState()};
record.selection_length_before = String(window.getSelection && window.getSelection() || '').length;
record.observer = new MutationObserver(entries => {
  record.mutations = Math.min(1000000, record.mutations + entries.length);
});
record.observer.observe(document, {
  subtree: true,
  childList: true,
  attributes: true,
  characterData: true
});
window[key] = record;
return {focus_before: record.focus_before, selection_length_before: record.selection_length_before};
"""
_FINISH_OBSERVATION_SCRIPT = """
const key = arguments[0];
const record = window[key];
if (!record) return {available: false};
record.observer.disconnect();
const active = document.activeElement;
const result = {
  available: true,
  mutation_count: record.mutations,
  focus_before: record.focus_before,
  focus_after: {
    tag_name: active && active.tagName ? active.tagName.toLowerCase() : '',
    id: active && active.id || '',
    role: active && active.getAttribute && active.getAttribute('role') || ''
  },
  selection_length_before: record.selection_length_before,
  selection_length_after: String(window.getSelection && window.getSelection() || '').length
};
delete window[key];
return result;
"""


class InputPostconditionError(ValueError):
    def __init__(self, expected: str, observed: str):
        super().__init__(f"Expected input state {expected!r}, observed {observed!r}")
        self.expected = expected
        self.observed = observed


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


def _start_observation(driver):
    token = "__selenium_mcp_observe_" + secrets.token_hex(8)
    try:
        before = driver.execute_script(_START_OBSERVATION_SCRIPT, token)
    except Exception:
        return "", {"available": False}
    return token, {"available": True, **(before or {})}


def _finish_observation(driver, token: str):
    if not token:
        return {"available": False}
    try:
        return driver.execute_script(_FINISH_OBSERVATION_SCRIPT, token)
    except Exception:
        return {"available": False}


def _target_changes(before: dict, after: dict) -> dict:
    changes = {}
    for key in ("value", "text", "visible", "enabled", "selected"):
        if before.get(key) != after.get(key):
            changes[key] = {"before": before.get(key), "after": after.get(key)}
    return changes


def _observed_result(
    before_url: str,
    after_url: str,
    before_element: dict,
    after_element: dict,
    browser_observation: dict,
) -> dict:
    changes = _target_changes(before_element, after_element)
    focus_changed = (
        browser_observation.get("focus_before")
        != browser_observation.get("focus_after")
        if browser_observation.get("available")
        else False
    )
    selection_changed = (
        browser_observation.get("selection_length_before")
        != browser_observation.get("selection_length_after")
        if browser_observation.get("available")
        else False
    )
    mutation_count = int(browser_observation.get("mutation_count", 0) or 0)
    return {
        "effect_observed": bool(
            before_url != after_url
            or changes
            or focus_changed
            or selection_changed
            or mutation_count
        ),
        "application_outcome": "not_asserted",
        "url": {
            "before": before_url,
            "after": after_url,
            "changed": before_url != after_url,
        },
        "target": {
            "before": before_element,
            "after": after_element,
            "changes": changes,
        },
        "dom": {
            "observation_available": bool(browser_observation.get("available")),
            "mutation_count": mutation_count,
        },
        "focus": {
            "before": browser_observation.get("focus_before"),
            "after": browser_observation.get("focus_after"),
            "changed": focus_changed,
        },
        "selection": {
            "length_before": browser_observation.get("selection_length_before"),
            "length_after": browser_observation.get("selection_length_after"),
            "changed": selection_changed,
        },
    }


def _target_kind(driver, element, requested: str) -> str:
    detected = str(driver.execute_script(_TARGET_KIND_SCRIPT, element))
    if requested != "auto" and requested != detected:
        raise ElementNotInteractableException(
            f"Requested target_kind={requested}, detected {detected}"
        )
    if detected not in {"form_control", "contenteditable"}:
        raise ElementNotInteractableException(
            "Target is neither an input/textarea nor a contenteditable element"
        )
    return detected


def _target_text(driver, element, target_kind: str) -> str:
    if target_kind == "form_control":
        return element.get_attribute("value") or ""
    return str(
        driver.execute_script(
            "return arguments[0].innerText || arguments[0].textContent || '';",
            element,
        )
    )


def _perform_input(driver, element, action: str, input_value: str, options: dict) -> dict:
    requested_kind = options.get("target_kind", "auto")
    target_kind = _target_kind(driver, element, requested_kind)
    input_mode = options.get("input_mode", "auto")
    clear_existing = options.get("clear_existing", action == "set_value")
    verify = options.get("verify_after_input", True)
    input_type = options.get("input_type", "insertText")
    before = _target_text(driver, element, target_kind)
    expected = options.get(
        "expected_value",
        input_value if clear_existing else before + input_value,
    )
    events = ["keyboard", "input"]

    if target_kind == "form_control":
        selected_mode = "keyboard" if input_mode == "auto" else input_mode
        if clear_existing:
            element.clear()
        if selected_mode == "keyboard":
            if input_value:
                element.send_keys(input_value)
            observed = _target_text(driver, element, target_kind)
            if observed != expected and input_mode == "auto":
                observed = str(driver.execute_script(_SET_VALUE_SCRIPT, element, expected))
                selected_mode = "keyboard_then_dom"
                events = ["input", "change"]
            else:
                driver.execute_script(_DISPATCH_VALUE_EVENTS_SCRIPT, element)
                events = ["keyboard", "input", "change"]
        else:
            observed = str(driver.execute_script(_SET_VALUE_SCRIPT, element, expected))
            events = ["input", "change"]
    else:
        selected_mode = "dom" if input_mode == "auto" else input_mode
        if selected_mode == "keyboard":
            if clear_existing:
                element.send_keys(Keys.CONTROL, "a")
                element.send_keys(Keys.BACKSPACE)
            if input_value:
                element.send_keys(input_value)
            observed = _target_text(driver, element, target_kind)
            events = ["keyboard", "beforeinput", "input"]
        else:
            dom_result = driver.execute_script(
                _CONTENTEDITABLE_INPUT_SCRIPT,
                element,
                input_value,
                clear_existing,
                input_type,
            )
            if not dom_result.get("accepted"):
                raise ElementNotInteractableException(
                    "The contenteditable beforeinput event was canceled"
                )
            observed = str(dom_result.get("text", ""))
            events = ["beforeinput", "input", "change"]

    if verify and observed != expected:
        raise InputPostconditionError(expected, observed)
    return {
        "mode": selected_mode,
        "events": events,
        "target_kind": target_kind,
        "input_type": input_type,
        "clear_existing": clear_existing,
        "verification": {
            "enabled": verify,
            "passed": observed == expected if verify else None,
            "expected": expected,
            "observed": observed,
        },
    }


def _normalize_scroll_options(options: dict) -> dict:
    direction = options.get("direction", "down")
    if direction not in {"up", "down", "left", "right", "both"}:
        raise ValueError("options.direction must be up, down, left, right, or both")
    amount = options.get("amount", 400)
    if not isinstance(amount, int) or not 1 <= amount <= 100000:
        raise ValueError("options.amount must be an integer from 1 to 100000")
    destination = options.get("to", "")
    if destination not in {"", "start", "end"}:
        raise ValueError("options.to must be start or end")
    if direction == "both" and destination:
        raise ValueError("options.to is not supported with direction=both")
    max_steps = options.get("max_steps", 20)
    if not isinstance(max_steps, int) or not 1 <= max_steps <= 100:
        raise ValueError("options.max_steps must be an integer from 1 to 100")
    delay = options.get("step_delay_ms", 50)
    if not isinstance(delay, int) or not 0 <= delay <= 1000:
        raise ValueError("options.step_delay_ms must be an integer from 0 to 1000")
    include_nested = options.get("include_nested_scroll_containers", False)
    if not isinstance(include_nested, bool):
        raise ValueError(
            "options.include_nested_scroll_containers must be true or false"
        )
    until_visible = options.get("until_visible")
    if until_visible is not None:
        until_visible = validate_selector(until_visible)
    return {
        "direction": direction,
        "amount": amount,
        "to": destination,
        "max_steps": max_steps,
        "step_delay_ms": delay,
        "include_nested_scroll_containers": include_nested,
        "until_visible": until_visible,
    }


def _visible_target(driver, selector):
    if selector is None:
        return False, {"matched": 0, "visible": 0}
    with matching_elements(driver, selector) as (_, elements):
        diagnostics = [inspect_actionability(driver, element) for element in elements[:20]]
        visible = sum(
            bool(item.get("webdriver", {}).get("displayed"))
            and bool(item.get("geometry", {}).get("intersects_viewport"))
            and bool(item.get("hit_test", {}).get("target_hit"))
            for item in diagnostics
        )
    return visible > 0, {
        "matched": len(elements),
        "visible": visible,
        "sampled": len(diagnostics),
        "sample_reasons": [item.get("reasons", []) for item in diagnostics[:3]],
    }


def _scroll_result(driver, element_ref: str, timeout: float, options: dict, started: float):
    normalized = _normalize_scroll_options(options)
    deadline = started + timeout
    observations = []
    target_visible, target = _visible_target(driver, normalized["until_visible"])
    if target_visible:
        return {
            "ok": True,
            "action": "scroll",
            "attempts": 0,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "target": target,
            "scroll": {"already_visible": True, "steps": observations},
            "execution": {"strategy": "script", "attempted": False, "completed": True},
            "observed": {
                "effect_observed": False,
                "application_outcome": "not_asserted",
                "target_visible": True,
            },
        }
    sweep_direction = "down" if normalized["direction"] == "both" else normalized["direction"]
    sweep_reversed = False
    for step in range(1, normalized["max_steps"] + 1):
        try:
            if element_ref:
                with resolved_element(driver, element_ref) as container:
                    observation = driver.execute_script(
                        _SCROLL_SCRIPT,
                        container,
                        sweep_direction,
                        normalized["amount"],
                        normalized["to"],
                        False,
                    )
            else:
                observation = driver.execute_script(
                    _SCROLL_SCRIPT,
                    None,
                    sweep_direction,
                    normalized["amount"],
                    normalized["to"],
                    normalized["include_nested_scroll_containers"],
                )
        except LocatorReferenceError as exc:
            return {
                "ok": False,
                "action": "scroll",
                "error": {"code": exc.code, "message": str(exc)},
            }
        observations.append({"step": step, "direction": sweep_direction, **observation})
        target_visible, target = _visible_target(driver, normalized["until_visible"])
        if normalized["until_visible"] is None or target_visible:
            return {
                "ok": True,
                "action": "scroll",
                "attempts": step,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "target": target,
                "scroll": {"already_visible": False, "steps": observations},
                "execution": {"strategy": "script", "attempted": True, "completed": True},
                "observed": {
                    "effect_observed": bool(observation.get("changed", 0)),
                    "application_outcome": "not_asserted",
                    "target_visible": target_visible,
                },
            }
        now = time.monotonic()
        if now >= deadline:
            break
        if observation.get("changed", 0) == 0:
            if normalized["direction"] == "both" and not sweep_reversed:
                sweep_direction = "up"
                sweep_reversed = True
                continue
            break
        delay = normalized["step_delay_ms"] / 1000
        if delay:
            time.sleep(min(delay, max(0, deadline - now)))
    return {
        "ok": False,
        "action": "scroll",
        "attempts": len(observations),
        "timed_out": time.monotonic() >= deadline,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "target": target,
        "scroll": {"already_visible": False, "steps": observations},
        "error": {
            "code": "scroll_target_not_visible",
            "message": "The until_visible selector did not become visible within the bounded scroll sweep.",
        },
        "execution": {
            "strategy": "script",
            "attempted": bool(observations),
            "completed": False,
        },
        "observed": {
            "effect_observed": any(
                step.get("changed", 0) for step in observations
            ),
            "application_outcome": "not_asserted",
            "target_visible": False,
        },
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
    options,
):
    if action not in _ACTIONS:
        raise ValueError("Unsupported interaction action")
    if action != "scroll" and not element_ref.strip():
        raise ValueError("element_ref is required")
    if not isinstance(options, dict):
        raise ValueError("options must be an object")
    if action == "click":
        allowed_options = _CLICK_OPTION_KEYS
    elif action in {"type", "set_value"}:
        allowed_options = _INPUT_OPTION_KEYS
    elif action == "scroll":
        allowed_options = _SCROLL_OPTION_KEYS
    else:
        allowed_options = set()
    unknown_options = sorted(set(options) - allowed_options)
    if unknown_options:
        raise ValueError(
            f"Unsupported {action} options: {', '.join(unknown_options)}"
        )
    if action == "click":
        click_mode = options.get("click_mode", "native")
        if click_mode not in _CLICK_MODES:
            raise ValueError("options.click_mode must be native, actions, or javascript")
        stability_ms = options.get("stability_ms", 100)
        observe_ms = options.get("observe_ms", 100)
        if not isinstance(stability_ms, int) or not 0 <= stability_ms <= 2000:
            raise ValueError("options.stability_ms must be an integer from 0 to 2000")
        if not isinstance(observe_ms, int) or not 0 <= observe_ms <= 2000:
            raise ValueError("options.observe_ms must be an integer from 0 to 2000")
        offset = options.get("offset")
        if offset is not None:
            if not isinstance(offset, dict) or set(offset) - {"x", "y"}:
                raise ValueError("options.offset must contain only integer x and y")
            if not all(
                isinstance(offset.get(axis, 0), int)
                and -10000 <= offset.get(axis, 0) <= 10000
                for axis in ("x", "y")
            ):
                raise ValueError("options.offset x and y must be integers from -10000 to 10000")
    if action in {"type", "set_value"}:
        if options.get("target_kind", "auto") not in _TARGET_KINDS:
            raise ValueError(
                "options.target_kind must be auto, form_control, or contenteditable"
            )
        if options.get("input_mode", "auto") not in _INPUT_MODES:
            raise ValueError("options.input_mode must be auto, keyboard, or dom")
        if options.get("input_type", "insertText") not in _INPUT_TYPES:
            raise ValueError(
                "options.input_type must be insertText or insertFromPaste"
            )
        for key in ("clear_existing", "verify_after_input"):
            if key in options and not isinstance(options[key], bool):
                raise ValueError(f"options.{key} must be true or false")
        if "expected_value" in options and not isinstance(
            options["expected_value"], str
        ):
            raise ValueError("options.expected_value must be a string")
        observe_ms = options.get("observe_ms", 100)
        if not isinstance(observe_ms, int) or not 0 <= observe_ms <= 2000:
            raise ValueError("options.observe_ms must be an integer from 0 to 2000")
    if action == "scroll":
        _normalize_scroll_options(options)
    if not 0 <= timeout <= 60:
        raise ValueError("timeout must be between 0 and 60 seconds")
    if action == "type" and input_value == "" and not options.get("clear_existing"):
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
    options,
):
    if action in {"click", "hover", "select_option", "upload_file"}:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
            element,
        )
    if action == "click":
        click_mode = options.get("click_mode", "native")
        offset = options.get("offset") or {}
        if click_mode == "native":
            element.click()
        elif click_mode == "actions":
            chain = ActionChains(driver)
            if offset:
                chain.move_to_element_with_offset(
                    element, offset.get("x", 0), offset.get("y", 0)
                )
            else:
                chain.move_to_element(element)
            chain.click().perform()
        else:
            driver.execute_script("arguments[0].click();", element)
        return {
            "mode": click_mode,
            "events": ["click"],
            "offset": offset or None,
        }
    if action == "clear":
        target_kind = str(driver.execute_script(_TARGET_KIND_SCRIPT, element))
        if target_kind == "contenteditable":
            driver.execute_script(_CLEAR_CONTENTEDITABLE_SCRIPT, element)
            return {
                "mode": "dom",
                "events": ["input", "change"],
                "target_kind": target_kind,
            }
        element.clear()
        return {
            "mode": "browser_native",
            "events": ["input", "change"],
            "target_kind": "form_control",
        }
    if action in {"type", "set_value"}:
        return _perform_input(driver, element, action, input_value, options)
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
    options: dict = {},
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
            options,
        )
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "action": action,
            "error": {"code": "invalid_interaction", "message": str(exc)},
        }

    if action == "scroll":
        return _scroll_result(driver, element_ref, timeout, options, started)

    deadline = started + timeout
    attempts = 0
    last_actionability = {}
    last_execution = {}
    before_element_state = {}
    browser_observation = {"available": False}
    stable_signature = None
    stable_since = started
    while attempts < _MAX_ATTEMPTS:
        attempts += 1
        try:
            with resolved_element(driver, element_ref) as element:
                if action == "inspect":
                    return {
                        "ok": True,
                        "action": action,
                        "attempts": attempts,
                        "elapsed_ms": int((time.monotonic() - started) * 1000),
                        "element": _element_state(element),
                        "actionability": inspect_actionability(driver, element),
                        "execution": {
                            "strategy": "diagnostic",
                            "attempted": False,
                            "completed": True,
                        },
                    }
                if action == "click":
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
                        element,
                    )
                    last_actionability = inspect_actionability(driver, element)
                    click_mode = options.get("click_mode", "native")
                    last_execution = {
                        "strategy": click_mode,
                        "attempted": False,
                    }
                    if click_mode != "javascript":
                        current_signature = geometry_signature(last_actionability)
                        now = time.monotonic()
                        if current_signature != stable_signature:
                            stable_signature = current_signature
                            stable_since = now
                        stability_ms = options.get("stability_ms", 100)
                        stable_for_ms = int((now - stable_since) * 1000)
                        last_actionability["stable_for_ms"] = stable_for_ms
                        blocking_reasons = list(last_actionability.get("reasons", []))
                        if stable_for_ms < stability_ms and "animating" not in blocking_reasons:
                            blocking_reasons.append("layout_not_stable")
                        last_actionability["blocking_reasons"] = blocking_reasons
                        if blocking_reasons:
                            last_error = "Element is not actionable: " + ", ".join(
                                blocking_reasons
                            )
                            raise ElementNotInteractableException(last_error)
                    last_execution["attempted"] = True
                before_element_state = _element_state(element)
                observation_token, _ = _start_observation(driver)
                try:
                    event_result = _perform(
                        driver,
                        element,
                        action,
                        input_value,
                        key,
                        option_by,
                        option_value,
                        upload_path,
                        options,
                    )
                except _RETRIABLE:
                    _finish_observation(driver, observation_token)
                    if action == "click":
                        last_actionability = inspect_actionability(driver, element)
                    raise
                except Exception:
                    _finish_observation(driver, observation_token)
                    raise
                observe_ms = options.get("observe_ms", 100)
                if observe_ms:
                    time.sleep(
                        min(
                            observe_ms / 1000,
                            max(0, deadline - time.monotonic()),
                        )
                    )
                browser_observation = _finish_observation(driver, observation_token)
                state = _element_state(element)
            after_url = _safe(lambda: driver.current_url, "")
            observed = _observed_result(
                before_url,
                after_url,
                before_element_state,
                state,
                browser_observation,
            )
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
                "execution": {
                    "strategy": event_result.get("mode", "browser_native"),
                    "attempted": True,
                    "completed": True,
                    "reported_events": event_result.get("events", []),
                    "observe_ms": options.get("observe_ms", 100),
                },
                "observed": observed,
                **(
                    {"actionability": last_actionability}
                    if action == "click"
                    else {}
                ),
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
        except InputPostconditionError as exc:
            return {
                "ok": False,
                "action": action,
                "attempts": attempts,
                "error": {
                    "code": "input_postcondition_failed",
                    "message": str(exc),
                },
                "verification": {
                    "enabled": True,
                    "passed": False,
                    "expected": exc.expected,
                    "observed": exc.observed,
                },
            }
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
                **(
                    {"actionability": last_actionability}
                    if last_actionability
                    else {}
                ),
                **({"execution": last_execution} if last_execution else {}),
            }
        time.sleep(min(0.1, deadline - now))


def interact_json(driver, *args, **kwargs) -> str:
    return json.dumps(interact_result(driver, *args, **kwargs), ensure_ascii=False)
