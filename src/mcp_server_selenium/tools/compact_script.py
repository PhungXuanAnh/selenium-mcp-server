"""Bounded asynchronous JavaScript execution for the compact profile."""

import json

from selenium.common.exceptions import TimeoutException

from .compact_diagnostics import diagnostics_broker

_WRAPPER_PREFIX = r"""
const done = arguments[arguments.length - 1];
const MAX_DEPTH = 5;
const MAX_ITEMS = 50;
const MAX_STRING = 10000;
function xpathFor(element) {
  const parts = [];
  let node = element;
  while (node && node.nodeType === Node.ELEMENT_NODE) {
    let index = 1;
    let sibling = node.previousElementSibling;
    while (sibling) {
      if (sibling.tagName === node.tagName) index += 1;
      sibling = sibling.previousElementSibling;
    }
    parts.unshift(`${node.tagName.toLowerCase()}[${index}]`);
    node = node.parentElement;
  }
  return `/${parts.join('/')}`;
}
function boundedString(value) {
  const text = String(value);
  return {value: text.slice(0, MAX_STRING), truncated: text.length > MAX_STRING};
}
function serialize(value, depth = 0, seen = new WeakSet()) {
  if (value === undefined) return {type: 'undefined'};
  if (value === null) return {type: 'null', value: null};
  const kind = typeof value;
  if (kind === 'string') return {type: 'string', ...boundedString(value)};
  if (kind === 'number') return {
    type: 'number', value: Number.isFinite(value) ? value : String(value)
  };
  if (kind === 'boolean') return {type: 'boolean', value};
  if (kind === 'bigint') return {type: 'bigint', value: String(value)};
  if (kind === 'symbol' || kind === 'function') {
    return {type: kind, ...boundedString(value)};
  }
  if (value instanceof Element) return {
    type: 'element',
    value: {
      tag_name: value.tagName.toLowerCase(),
      id: value.id || '',
      class: String(value.className || ''),
      text: (value.innerText || value.textContent || '').slice(0, 500),
      xpath: xpathFor(value)
    }
  };
  if (value instanceof Error) return {
    type: 'error',
    value: {
      name: value.name || 'Error',
      message: String(value.message || value).slice(0, MAX_STRING),
      stack: String(value.stack || '').slice(0, 4000)
    }
  };
  if (value instanceof Date) return {type: 'date', value: value.toISOString()};
  if (depth >= MAX_DEPTH) return {type: 'max_depth'};
  if (seen.has(value)) return {type: 'circular'};
  seen.add(value);
  if (Array.isArray(value)) {
    return {
      type: 'array',
      value: value.slice(0, MAX_ITEMS).map(item => serialize(item, depth + 1, seen)),
      truncated: value.length > MAX_ITEMS
    };
  }
  const keys = Object.keys(value);
  const output = {};
  for (const key of keys.slice(0, MAX_ITEMS)) {
    try { output[key] = serialize(value[key], depth + 1, seen); }
    catch (error) { output[key] = {type: 'getter_error', value: String(error)}; }
  }
  return {type: 'object', value: output, truncated: keys.length > MAX_ITEMS};
}
(async () => {
  try {
    const value = await (async function () {
"""
_WRAPPER_SUFFIX = r"""
    }).call(window);
    done({ok: true, result: serialize(value)});
  } catch (error) {
    done({
      ok: false,
      error: {
        code: 'javascript_exception',
        name: error && error.name || 'Error',
        message: String(error && error.message || error).slice(0, MAX_STRING),
        stack: String(error && error.stack || '').slice(0, 4000)
      }
    });
  }
})();
"""


def _execution_error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


def run_javascript_result(
    driver,
    javascript_code: str,
    capture_console: bool = False,
    timeout: float = 30,
) -> dict:
    if not isinstance(javascript_code, str) or not javascript_code.strip():
        return _execution_error(
            "invalid_javascript", "javascript_code must be a non-empty string"
        )
    if not 0.1 <= timeout <= 120:
        return _execution_error(
            "invalid_javascript", "timeout must be between 0.1 and 120 seconds"
        )

    capture_error = ""
    start_cursor = 0
    if capture_console:
        try:
            diagnostics_broker.drain_console(driver, wait_seconds=0)
            start_cursor = diagnostics_broker.latest_cursor(driver)
        except RuntimeError as exc:
            capture_error = str(exc)

    driver.set_script_timeout(timeout)
    wrapped_code = _WRAPPER_PREFIX + javascript_code + "\n" + _WRAPPER_SUFFIX
    try:
        result = driver.execute_async_script(wrapped_code)
    except TimeoutException as exc:
        result = _execution_error("javascript_timeout", str(exc))
    except Exception as exc:
        result = _execution_error("javascript_execution_failed", str(exc))
    if not isinstance(result, dict):
        result = _execution_error(
            "javascript_protocol_error",
            "The browser did not return the structured JavaScript envelope.",
        )

    if capture_console:
        try:
            diagnostics_broker.drain_console(driver)
            result["console"] = diagnostics_broker.read(
                "console", "consume", start_cursor, 100, 0, True
            )
        except RuntimeError as exc:
            capture_error = str(exc)
        if capture_error:
            result["console_error"] = capture_error
    return result


def run_javascript_json(driver, *args, **kwargs) -> str:
    return json.dumps(
        run_javascript_result(driver, *args, **kwargs), ensure_ascii=False
    )
