"""Bounded, document-scoped element locators for the compact profile."""

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import json
import secrets
import time
from typing import Iterator

from pydantic import TypeAdapter, ValidationError
from selenium.webdriver.common.by import By

from .compact_models import (
    CssSelector,
    FieldsSelector,
    RefSelector,
    Selector,
    XPathSelector,
)

_SELECTOR_ADAPTER = TypeAdapter(Selector)
_ALLOWED_FIELD_NAMES = {"text", "class_name", "id", "element_type"}
_ABSOLUTE_XPATH_SCRIPT = """
const element = arguments[0];
if (!element || element.nodeType !== Node.ELEMENT_NODE) return null;
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
"""


class LocatorReferenceError(ValueError):
    """A stable reference is absent, expired, or belongs to another document."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _DocumentScope:
    session: str
    window: str
    document: str


@dataclass(frozen=True)
class _LocatorRecord:
    selector: dict
    scope: _DocumentScope
    created_at: float


class LocatorRegistry:
    """Store locator specifications only; never retain Selenium WebElements."""

    def __init__(self, max_entries: int = 256, ttl_seconds: float = 1800):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._records: OrderedDict[str, _LocatorRecord] = OrderedDict()

    def clear(self) -> None:
        self._records.clear()

    def current_scope(self, driver) -> _DocumentScope:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        session = str(getattr(driver, "session_id", id(driver)))
        try:
            window = str(driver.current_window_handle)
        except Exception:
            window = "unknown-window"
        try:
            origin = driver.execute_script(
                "return String(window.performance && performance.timeOrigin || '')"
            )
            document = str(origin or driver.current_url)
        except Exception:
            document = str(getattr(driver, "current_url", "unknown-document"))
        return _DocumentScope(session, window, document)

    def add(self, selector: Selector, scope: _DocumentScope) -> str:
        self._purge_expired()
        token = f"el_{secrets.token_urlsafe(12)}"
        self._records[token] = _LocatorRecord(
            selector=selector.model_dump(exclude_none=True),
            scope=scope,
            created_at=time.monotonic(),
        )
        while len(self._records) > self.max_entries:
            self._records.popitem(last=False)
        return token

    def resolve(self, driver, token: str) -> Selector:
        self._purge_expired()
        record = self._records.get(token)
        if record is None:
            raise LocatorReferenceError(
                "unknown_element_ref",
                "The element_ref is unknown or expired; query the element again.",
            )
        if record.scope != self.current_scope(driver):
            self._records.pop(token, None)
            raise LocatorReferenceError(
                "stale_element_ref",
                "The element_ref belongs to another tab or document; query it again.",
            )
        self._records.move_to_end(token)
        return _SELECTOR_ADAPTER.validate_python(record.selector)

    def _purge_expired(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        expired = [
            token
            for token, record in self._records.items()
            if record.created_at < cutoff
        ]
        for token in expired:
            self._records.pop(token, None)


locator_registry = LocatorRegistry()


def validate_selector(value) -> Selector:
    """Validate direct Python calls as strictly as MCP/Pydantic calls."""
    try:
        selector = _SELECTOR_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError(f"Invalid selector: {exc.errors(include_url=False)}") from exc
    if isinstance(selector, (XPathSelector, CssSelector)) and not selector.value.strip():
        raise ValueError("selector.value must not be empty")
    if isinstance(selector, RefSelector) and not selector.value.strip():
        raise ValueError("selector.value must contain an element_ref")
    if isinstance(selector, FieldsSelector):
        if not selector.value:
            raise ValueError("fields selector.value must contain at least one field")
        invalid = [
            key
            for key in selector.value
            if key not in _ALLOWED_FIELD_NAMES and not key.startswith("attribute:")
        ]
        if invalid:
            raise ValueError(
                "Unsupported fields selector keys: " + ", ".join(sorted(invalid))
            )
    return selector


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    joined = ", \"'\", ".join(f"'{part}'" for part in parts)
    return f"concat({joined})"


def _fields_xpath(values: dict[str, str]) -> str:
    element_type = values.get("element_type", "*").strip() or "*"
    valid_tag = (
        element_type == "*"
        or (
            element_type[0].isalpha()
            and all(character.isalnum() or character == "-" for character in element_type)
        )
    )
    if not valid_tag:
        raise ValueError("fields element_type must be an HTML tag name")
    conditions = []
    if "id" in values:
        conditions.append(f"@id={_xpath_literal(values['id'])}")
    if "text" in values:
        conditions.append(f"contains(., {_xpath_literal(values['text'])})")
    for class_name in values.get("class_name", "").split():
        class_literal = _xpath_literal(f" {class_name} ")
        conditions.append(
            f"contains(concat(' ', normalize-space(@class), ' '), {class_literal})"
        )
    for key, value in values.items():
        if key.startswith("attribute:"):
            attribute = key.partition(":")[2]
            if not attribute or not all(
                character.isalnum() or character in "_:-" for character in attribute
            ):
                raise ValueError(f"Invalid attribute selector name: {attribute!r}")
            conditions.append(f"@{attribute}={_xpath_literal(value)}")
    predicate = f"[{' and '.join(conditions)}]" if conditions else ""
    return f"//{element_type}{predicate}"


def _frame_value(selector: Selector) -> str:
    return getattr(selector, "frame", None) or ""


@contextmanager
def _selector_context(driver, selector: Selector) -> Iterator[None]:
    driver.switch_to.default_content()
    frame = _frame_value(selector)
    if frame:
        try:
            iframe = driver.find_element(By.ID, frame)
            driver.switch_to.frame(iframe)
        except Exception:
            driver.switch_to.frame(frame)
    try:
        yield
    finally:
        driver.switch_to.default_content()


def _find_elements(driver, selector: Selector):
    if isinstance(selector, XPathSelector):
        return driver.find_elements(By.XPATH, selector.value)
    if isinstance(selector, CssSelector):
        return driver.find_elements(By.CSS_SELECTOR, selector.value)
    if isinstance(selector, FieldsSelector):
        return driver.find_elements(By.XPATH, _fields_xpath(selector.value))
    raise TypeError("Reference selectors must be resolved before searching")


def resolve_selector(driver, selector: Selector) -> Selector:
    if isinstance(selector, RefSelector):
        return locator_registry.resolve(driver, selector.value)
    return selector


@contextmanager
def matching_elements(driver, selector_value):
    """Yield freshly matched elements while the selector's frame is active."""
    selector = resolve_selector(driver, validate_selector(selector_value))
    with _selector_context(driver, selector):
        yield selector, _find_elements(driver, selector)


@contextmanager
def resolved_element(driver, element_ref: str):
    """Yield one freshly resolved WebElement in its frame context."""
    selector = locator_registry.resolve(driver, element_ref)
    with _selector_context(driver, selector):
        elements = _find_elements(driver, selector)
        if len(elements) != 1:
            raise LocatorReferenceError(
                "element_ref_not_resolved",
                f"The element_ref now matches {len(elements)} elements; query it again.",
            )
        yield elements[0]


def _exact_selector(driver, element, frame: str) -> XPathSelector:
    xpath = driver.execute_script(_ABSOLUTE_XPATH_SCRIPT, element)
    if not xpath:
        raise RuntimeError("Unable to create a stable XPath for the matched element")
    return XPathSelector(type="xpath", value=xpath, frame=frame or None)


def _element_payload(driver, element, frame: str, scope: _DocumentScope, return_html: bool):
    exact_selector = _exact_selector(driver, element, frame)
    payload = {
        "element_ref": locator_registry.add(exact_selector, scope),
        "tag_name": element.tag_name,
        "id": element.get_attribute("id") or "",
        "class": element.get_attribute("class") or "",
        "text": (element.text or "")[:500],
        "xpath": exact_selector.value,
        "visible": bool(element.is_displayed()),
        "enabled": bool(element.is_enabled()),
    }
    if return_html:
        payload["innerHTML"] = (element.get_attribute("innerHTML") or "")[:20000]
        payload["outerHTML"] = (element.get_attribute("outerHTML") or "")[:20000]
    return payload


def query(driver, action: str, selector_value, page: int, page_size, return_html: bool):
    """Execute one compact element query and return its structured result."""
    selector = resolve_selector(driver, validate_selector(selector_value))
    if page < 1:
        raise ValueError("page must be at least 1")
    default_size = 5 if action == "children" else 3
    size = default_size if page_size is None else page_size
    if not isinstance(size, int) or not 1 <= size <= 50:
        raise ValueError("page_size must be between 1 and 50")

    scope = locator_registry.current_scope(driver)
    frame = _frame_value(selector)
    with _selector_context(driver, selector):
        matches = _find_elements(driver, selector)
        if action == "one":
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one element; found {len(matches)}")
            selected = matches
        elif action == "children":
            if len(matches) != 1:
                raise ValueError(
                    f"Expected exactly one parent element; found {len(matches)}"
                )
            matches = matches[0].find_elements(By.XPATH, "./*")
            start = (page - 1) * size
            selected = matches[start : start + size]
        else:
            start = (page - 1) * size
            selected = matches[start : start + size]
        elements = [
            _element_payload(driver, element, frame, scope, return_html)
            for element in selected
        ]

    return {
        "ok": True,
        "action": action,
        "matched": len(matches),
        "page": page,
        "page_size": size,
        "returned": len(elements),
        "has_more": page * size < len(matches),
        "elements": elements,
    }


def query_json(driver, action: str, selector, page: int, page_size, return_html: bool):
    try:
        return json.dumps(
            query(driver, action, selector, page, page_size, return_html),
            ensure_ascii=False,
        )
    except LocatorReferenceError as exc:
        return json.dumps(
            {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps(
            {"ok": False, "error": {"code": "invalid_query", "message": str(exc)}}
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": {"code": "query_failed", "message": str(exc)}}
        )
