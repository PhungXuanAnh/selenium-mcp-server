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

from .compact_models import CssSelector, FieldsSelector, RefSelector, Selector, XPathSelector

_SELECTOR_ADAPTER = TypeAdapter(Selector)
_ALLOWED_FIELD_NAMES = {
    "text", "class_name", "id", "element_type", "role", "accessible_name"
}
_SEMANTIC_SCAN_LIMIT = 5000
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
_EXACT_CSS_SCRIPT = """
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
  parts.unshift(`${node.tagName.toLowerCase()}:nth-of-type(${index})`);
  if (node.parentNode && node.parentNode.toString() === '[object ShadowRoot]') break;
  node = node.parentElement;
}
return parts.join(' > ');
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
class _ResolvedLocator:
    selector: Selector
    traversal: tuple[dict, ...]


@dataclass(frozen=True)
class _LocatorRecord:
    selector: dict
    traversal: tuple[dict, ...]
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

    def add(
        self,
        selector: Selector,
        scope: _DocumentScope,
        traversal: tuple[dict, ...] = (),
    ) -> str:
        self._purge_expired()
        token = f"el_{secrets.token_urlsafe(12)}"
        self._records[token] = _LocatorRecord(
            selector=selector.model_dump(exclude_none=True),
            traversal=tuple(dict(step) for step in traversal),
            scope=scope,
            created_at=time.monotonic(),
        )
        while len(self._records) > self.max_entries:
            self._records.popitem(last=False)
        return token

    def resolve_locator(self, driver, token: str) -> _ResolvedLocator:
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
        return _ResolvedLocator(
            _SELECTOR_ADAPTER.validate_python(record.selector), record.traversal
        )

    def resolve(self, driver, token: str) -> Selector:
        return self.resolve_locator(driver, token).selector

    def _purge_expired(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        for token in [
            token for token, record in self._records.items()
            if record.created_at < cutoff
        ]:
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
            key for key in selector.value
            if key not in _ALLOWED_FIELD_NAMES and not key.startswith("attribute:")
        ]
        if invalid:
            raise ValueError(
                "Unsupported fields selector keys: " + ", ".join(sorted(invalid))
            )
    return selector


def validate_query_options(options) -> tuple[dict, ...]:
    if not isinstance(options, dict):
        raise ValueError("options must be an object")
    unknown = sorted(set(options) - {"scope"})
    if unknown:
        raise ValueError("Unsupported query options: " + ", ".join(unknown))
    scope = options.get("scope", [])
    if not isinstance(scope, list) or len(scope) > 8:
        raise ValueError("options.scope must be a list with at most 8 steps")
    normalized = []
    for step in scope:
        if not isinstance(step, dict) or set(step) - {"type", "value", "by"}:
            raise ValueError("Each scope step accepts only type, value, and by")
        step_type = step.get("type")
        value = step.get("value")
        if step_type not in {"frame", "shadow"}:
            raise ValueError("scope step type must be frame or shadow")
        if not isinstance(value, str) or not value or len(value) > 1000:
            raise ValueError(
                "scope step value must be a non-empty string up to 1000 characters"
            )
        default_by = "id_or_name" if step_type == "frame" else "css"
        by = step.get("by", default_by)
        allowed_by = {"css", "id", "name", "id_or_name"}
        if by not in allowed_by or (step_type == "shadow" and by == "id_or_name"):
            raise ValueError(
                "scope step by must be css, id, name, or frame-only id_or_name"
            )
        normalized.append({"type": step_type, "value": value, "by": by})
    return tuple(normalized)


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
    valid_tag = element_type == "*" or (
        element_type[0].isalpha()
        and all(character.isalnum() or character == "-" for character in element_type)
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


def _direct_locator(selector: Selector, traversal: tuple[dict, ...]) -> _ResolvedLocator:
    frame = getattr(selector, "frame", None) or ""
    steps = list(traversal)
    if frame:
        steps.insert(0, {"type": "frame", "value": frame, "by": "id_or_name"})
        selector = selector.model_copy(update={"frame": None})
    return _ResolvedLocator(selector, tuple(steps))


def _locate_scope_node(root, step: dict):
    by = step["by"]
    value = step["value"]
    if by == "css":
        return root.find_element(By.CSS_SELECTOR, value)
    if by == "id":
        return root.find_element(By.ID, value)
    if by == "name":
        return root.find_element(By.NAME, value)
    try:
        return root.find_element(By.ID, value)
    except Exception:
        return root.find_element(By.NAME, value)


@contextmanager
def _locator_context(driver, locator: _ResolvedLocator) -> Iterator[object]:
    driver.switch_to.default_content()
    root = driver
    try:
        for step in locator.traversal:
            host = _locate_scope_node(root, step)
            if step["type"] == "frame":
                driver.switch_to.frame(host)
                root = driver
            else:
                root = host.shadow_root
        yield root
    finally:
        driver.switch_to.default_content()


def _semantic_match(element, values: dict[str, str]) -> bool:
    role = values.get("role")
    if role and (element.aria_role or "").lower() != role.lower():
        return False
    name = values.get("accessible_name")
    return not name or (element.accessible_name or "") == name


def _find_elements(root, selector: Selector, driver):
    if isinstance(selector, XPathSelector):
        if root is not driver:
            raise ValueError(
                "XPath is not supported inside shadow scope; use css or fields"
            )
        return root.find_elements(By.XPATH, selector.value)
    if isinstance(selector, CssSelector):
        return root.find_elements(By.CSS_SELECTOR, selector.value)
    if isinstance(selector, FieldsSelector):
        if root is driver:
            elements = root.find_elements(By.XPATH, _fields_xpath(selector.value))
        else:
            elements = root.find_elements(
                By.CSS_SELECTOR, selector.value.get("element_type", "*") or "*"
            )
        if len(elements) > _SEMANTIC_SCAN_LIMIT:
            raise ValueError(
                f"Fields selector matched more than {_SEMANTIC_SCAN_LIMIT} candidates; refine it"
            )
        values = selector.value
        classes = set(values.get("class_name", "").split())
        filtered = []
        for element in elements:
            if values.get("id") and (element.get_attribute("id") or "") != values["id"]:
                continue
            if values.get("text") and values["text"] not in (element.text or ""):
                continue
            if classes and not classes.issubset(
                set((element.get_attribute("class") or "").split())
            ):
                continue
            if any(
                (element.get_attribute(key.partition(":")[2]) or "") != value
                for key, value in values.items() if key.startswith("attribute:")
            ):
                continue
            if not _semantic_match(element, values):
                continue
            filtered.append(element)
        return filtered
    raise TypeError("Reference selectors must be resolved before searching")


def _resolve_locator(
    driver, selector: Selector, traversal: tuple[dict, ...]
) -> _ResolvedLocator:
    if isinstance(selector, RefSelector):
        if traversal:
            raise ValueError("options.scope cannot be combined with a ref selector")
        return locator_registry.resolve_locator(driver, selector.value)
    return _direct_locator(selector, traversal)


def resolve_selector(driver, selector: Selector) -> Selector:
    if isinstance(selector, RefSelector):
        return locator_registry.resolve(driver, selector.value)
    return selector


@contextmanager
def matching_elements(driver, selector_value, options=None):
    """Yield freshly matched elements while the recorded scope is active."""
    selector = validate_selector(selector_value)
    locator = _resolve_locator(
        driver, selector, validate_query_options(options or {})
    )
    with _locator_context(driver, locator) as root:
        yield locator.selector, _find_elements(root, locator.selector, driver)


@contextmanager
def resolved_element(driver, element_ref: str):
    """Yield one freshly resolved WebElement in its recorded scope context."""
    locator = locator_registry.resolve_locator(driver, element_ref)
    with _locator_context(driver, locator) as root:
        elements = _find_elements(root, locator.selector, driver)
        if len(elements) != 1:
            raise LocatorReferenceError(
                "element_ref_not_resolved",
                f"The element_ref now matches {len(elements)} elements; query it again.",
            )
        yield elements[0]


def _exact_selector(driver, element, traversal: tuple[dict, ...]) -> Selector:
    if any(step["type"] == "shadow" for step in traversal):
        css = driver.execute_script(_EXACT_CSS_SCRIPT, element)
        if not css:
            raise RuntimeError(
                "Unable to create a stable CSS selector for the matched element"
            )
        return CssSelector(type="css", value=css)
    xpath = driver.execute_script(_ABSOLUTE_XPATH_SCRIPT, element)
    if not xpath:
        raise RuntimeError("Unable to create a stable XPath for the matched element")
    return XPathSelector(type="xpath", value=xpath)


def _element_payload(
    driver, element, traversal: tuple[dict, ...], scope: _DocumentScope,
    return_html: bool,
):
    exact_selector = _exact_selector(driver, element, traversal)
    payload = {
        "element_ref": locator_registry.add(exact_selector, scope, traversal),
        "tag_name": element.tag_name,
        "id": element.get_attribute("id") or "",
        "class": element.get_attribute("class") or "",
        "text": (element.text or "")[:500],
        "selector": exact_selector.model_dump(exclude_none=True),
        "xpath": exact_selector.value if isinstance(exact_selector, XPathSelector) else "",
        "role": element.aria_role or "",
        "accessible_name": (element.accessible_name or "")[:500],
        "visible": bool(element.is_displayed()),
        "enabled": bool(element.is_enabled()),
        "scope": [dict(step) for step in traversal],
        "reference": {
            "ttl_seconds": locator_registry.ttl_seconds,
            "document_scoped": True,
            "re_resolves_dom": True,
        },
    }
    if return_html:
        payload["innerHTML"] = (element.get_attribute("innerHTML") or "")[:20000]
        payload["outerHTML"] = (element.get_attribute("outerHTML") or "")[:20000]
    return payload


def query(
    driver, action: str, selector_value, page: int, page_size,
    return_html: bool, options: dict | None = None,
):
    """Execute one compact element query and return its structured result."""
    selector = validate_selector(selector_value)
    locator = _resolve_locator(
        driver, selector, validate_query_options(options or {})
    )
    if page < 1:
        raise ValueError("page must be at least 1")
    default_size = 5 if action == "children" else 3
    size = default_size if page_size is None else page_size
    if not isinstance(size, int) or not 1 <= size <= 50:
        raise ValueError("page_size must be between 1 and 50")

    scope = locator_registry.current_scope(driver)
    with _locator_context(driver, locator) as root:
        matches = _find_elements(root, locator.selector, driver)
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
            _element_payload(driver, element, locator.traversal, scope, return_html)
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
        "scope": [dict(step) for step in locator.traversal],
        "query_semantics": {
            "includes_hidden_matches": True,
            "visibility_reported_per_element": True,
        },
        "reference_policy": {
            "ttl_seconds": locator_registry.ttl_seconds,
            "re_resolves_exact_locator": True,
            "same_document_rerender": "succeeds only while the exact locator resolves to one element",
            "invalidated_by": [
                "different_tab",
                "full_document_navigation",
                "ttl_expiry",
                "zero_or_multiple_current_matches",
            ],
        },
        "elements": elements,
    }


def query_json(
    driver, action: str, selector, page: int, page_size, return_html: bool,
    options: dict | None = None,
):
    try:
        return json.dumps(
            query(driver, action, selector, page, page_size, return_html, options),
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
