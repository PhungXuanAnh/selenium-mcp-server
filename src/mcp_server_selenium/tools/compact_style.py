"""Reference-based bounded style inspection for the compact profile."""

import json

from .compact_locator import LocatorReferenceError, resolved_element

_APPLIED_STYLE_SCRIPT = """
const element = arguments[0];
const appliedRules = [];
let truncated = false;
for (const sheet of Array.from(document.styleSheets)) {
  let rules;
  try { rules = sheet.cssRules || sheet.rules || []; }
  catch (_) { continue; }
  for (const rule of Array.from(rules)) {
    if (!rule.selectorText) continue;
    try {
      if (element.matches(rule.selectorText)) {
        if (appliedRules.length >= 200) { truncated = true; break; }
        appliedRules.push({
          selector: rule.selectorText,
          cssText: String(rule.style && rule.style.cssText || '').slice(0, 5000),
          href: sheet.href || 'inline'
        });
      }
    } catch (_) {}
  }
  if (truncated) break;
}
return {
  inline: element.getAttribute('style') || '',
  applied_rules: appliedRules,
  truncated
};
"""
_COMPUTED_STYLE_SCRIPT = """
const style = getComputedStyle(arguments[0]);
const result = {};
const limit = Math.min(style.length, 500);
for (let index = 0; index < limit; index += 1) {
  const name = style[index];
  result[name] = style.getPropertyValue(name);
}
return {properties: result, truncated: style.length > limit};
"""


def style_result(
    driver,
    element_ref: str,
    return_html: bool = False,
    all_styles: bool = True,
    computed_style: bool = True,
) -> dict:
    if not element_ref:
        return {
            "ok": False,
            "error": {
                "code": "element_ref_required",
                "message": "element_ref from query_elements is required",
            },
        }
    try:
        with resolved_element(driver, element_ref) as element:
            info = {
                "tag_name": element.tag_name,
                "id": element.get_attribute("id") or "",
                "class": element.get_attribute("class") or "",
                "text": (element.text or "")[:500],
            }
            if return_html:
                return {
                    "ok": True,
                    "element": info,
                    "html": {
                        "innerHTML": (element.get_attribute("innerHTML") or "")[:20000],
                        "outerHTML": (element.get_attribute("outerHTML") or "")[:20000],
                    },
                }
            result = {"ok": True, "element": info}
            if all_styles:
                result["all_styles"] = driver.execute_script(
                    _APPLIED_STYLE_SCRIPT, element
                )
            if computed_style:
                result["computed_style"] = driver.execute_script(
                    _COMPUTED_STYLE_SCRIPT, element
                )
            return result
    except LocatorReferenceError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
        return {
            "ok": False,
            "error": {"code": "style_lookup_failed", "message": str(exc)},
        }


def style_json(driver, *args, **kwargs) -> str:
    return json.dumps(style_result(driver, *args, **kwargs), ensure_ascii=False)
