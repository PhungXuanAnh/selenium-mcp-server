"""Bounded browser-side actionability diagnostics for compact interactions."""


_ACTIONABILITY_SCRIPT = r"""
const element = arguments[0];
const webdriverDisplayed = Boolean(arguments[1]);
const webdriverEnabled = Boolean(arguments[2]);

function describe(node) {
  if (!node || node.nodeType !== Node.ELEMENT_NODE) return null;
  const text = String(node.innerText || node.textContent || '').trim().replace(/\s+/g, ' ');
  return {
    tag_name: String(node.tagName || '').toLowerCase(),
    id: node.id || '',
    class: String(node.className || '').slice(0, 300),
    role: node.getAttribute('role') || '',
    accessible_name: String(
      node.getAttribute('aria-label') || node.getAttribute('title') || text
    ).slice(0, 200)
  };
}

const style = getComputedStyle(element);
const rect = element.getBoundingClientRect();
const viewportWidth = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
const viewportHeight = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);
const intersectsViewport = rect.width > 0 && rect.height > 0 &&
  rect.right > 0 && rect.bottom > 0 && rect.left < viewportWidth && rect.top < viewportHeight;
const centerX = Math.min(Math.max(rect.left + rect.width / 2, 0), Math.max(viewportWidth - 1, 0));
const centerY = Math.min(Math.max(rect.top + rect.height / 2, 0), Math.max(viewportHeight - 1, 0));
const hitRoot = element.getRootNode && element.getRootNode();
const topmost = intersectsViewport
  ? (hitRoot && typeof hitRoot.elementFromPoint === 'function'
      ? hitRoot.elementFromPoint(centerX, centerY)
      : document.elementFromPoint(centerX, centerY))
  : null;
const hitTarget = Boolean(topmost && (topmost === element || element.contains(topmost)));
const inertAncestor = element.closest('[inert]');
const disabled = Boolean(
  !webdriverEnabled || element.disabled || element.getAttribute('aria-disabled') === 'true'
);
const animations = [];
for (const animation of element.getAnimations({subtree: false}).slice(0, 20)) {
  const effect = animation.effect || null;
  const timing = effect && typeof effect.getTiming === 'function' ? effect.getTiming() : {};
  animations.push({
    play_state: animation.playState || '',
    animation_name: String(animation.animationName || ''),
    transition_property: String(animation.transitionProperty || ''),
    duration_ms: Number(timing.duration) || 0,
    iterations: timing.iterations === Infinity ? 'infinite' : Number(timing.iterations) || 0
  });
}

const scrollAncestors = [];
let parent = element.parentElement;
while (parent && scrollAncestors.length < 20) {
  const parentStyle = getComputedStyle(parent);
  const overflowX = parentStyle.overflowX;
  const overflowY = parentStyle.overflowY;
  const scrollableX = /(auto|scroll|overlay)/.test(overflowX) && parent.scrollWidth > parent.clientWidth;
  const scrollableY = /(auto|scroll|overlay)/.test(overflowY) && parent.scrollHeight > parent.clientHeight;
  if (scrollableX || scrollableY) {
    scrollAncestors.push({
      element: describe(parent),
      overflow_x: overflowX,
      overflow_y: overflowY,
      scroll_left: Math.round(parent.scrollLeft),
      scroll_top: Math.round(parent.scrollTop),
      client_width: Math.round(parent.clientWidth),
      client_height: Math.round(parent.clientHeight),
      scroll_width: Math.round(parent.scrollWidth),
      scroll_height: Math.round(parent.scrollHeight)
    });
  }
  parent = parent.parentElement;
}
const scrollingElement = document.scrollingElement;
if (scrollingElement && scrollAncestors.length < 20) {
  scrollAncestors.push({
    element: {tag_name: 'document', id: '', class: '', role: '', accessible_name: ''},
    overflow_x: 'auto',
    overflow_y: 'auto',
    scroll_left: Math.round(scrollingElement.scrollLeft),
    scroll_top: Math.round(scrollingElement.scrollTop),
    client_width: Math.round(scrollingElement.clientWidth),
    client_height: Math.round(scrollingElement.clientHeight),
    scroll_width: Math.round(scrollingElement.scrollWidth),
    scroll_height: Math.round(scrollingElement.scrollHeight)
  });
}

const reasons = [];
if (!webdriverDisplayed) reasons.push('webdriver_hidden');
if (style.display === 'none') reasons.push('display_none');
if (style.visibility === 'hidden' || style.visibility === 'collapse') reasons.push('visibility_hidden');
if (Number.parseFloat(style.opacity || '1') <= 0) reasons.push('opacity_zero');
if (rect.width <= 0 || rect.height <= 0) reasons.push('zero_size');
if (!intersectsViewport) reasons.push('offscreen');
if (style.pointerEvents === 'none') reasons.push('pointer_events_none');
if (inertAncestor) reasons.push('inert_ancestor');
if (disabled) reasons.push('disabled');
if (intersectsViewport && !hitTarget) reasons.push('covered');
if (animations.some(item => item.play_state === 'running' || item.play_state === 'pending')) {
  reasons.push('animating');
}

return {
  actionable: reasons.length === 0,
  stable: !reasons.includes('animating'),
  reasons,
  webdriver: {displayed: webdriverDisplayed, enabled: webdriverEnabled},
  geometry: {
    x: Math.round(rect.x * 100) / 100,
    y: Math.round(rect.y * 100) / 100,
    top: Math.round(rect.top * 100) / 100,
    right: Math.round(rect.right * 100) / 100,
    bottom: Math.round(rect.bottom * 100) / 100,
    left: Math.round(rect.left * 100) / 100,
    width: Math.round(rect.width * 100) / 100,
    height: Math.round(rect.height * 100) / 100,
    center_x: Math.round(centerX * 100) / 100,
    center_y: Math.round(centerY * 100) / 100,
    intersects_viewport: intersectsViewport,
    viewport_width: viewportWidth,
    viewport_height: viewportHeight
  },
  css: {
    display: style.display,
    visibility: style.visibility,
    opacity: style.opacity,
    pointer_events: style.pointerEvents,
    overflow_x: style.overflowX,
    overflow_y: style.overflowY,
    z_index: style.zIndex
  },
  hit_test: {
    point: {x: Math.round(centerX * 100) / 100, y: Math.round(centerY * 100) / 100},
    target_hit: hitTarget,
    topmost: describe(topmost),
    covered_by: hitTarget ? null : describe(topmost)
  },
  inert_ancestor: describe(inertAncestor),
  animations,
  scroll_ancestors: scrollAncestors
};
"""


def inspect_actionability(driver, element) -> dict:
    """Return bounded evidence explaining whether an element is actionable now."""
    displayed = bool(element.is_displayed())
    enabled = bool(element.is_enabled())
    result = driver.execute_script(
        _ACTIONABILITY_SCRIPT,
        element,
        displayed,
        enabled,
    )
    if not isinstance(result, dict):
        raise RuntimeError("Browser returned an invalid actionability result")
    return result


def geometry_signature(actionability: dict) -> tuple:
    """Return the geometry fields used to determine short-term layout stability."""
    geometry = actionability.get("geometry", {})
    return tuple(
        geometry.get(key)
        for key in ("x", "y", "width", "height")
    )
