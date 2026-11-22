/* @ds-bundle: {"format":3,"namespace":"HachiDesignSystem_46e488","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"StatusPill","sourcePath":"components/core/StatusPill.jsx"},{"name":"Switch","sourcePath":"components/core/Switch.jsx"},{"name":"LoyalLoop","sourcePath":"components/feedback/LoyalLoop.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"HachiMark","sourcePath":"components/hachi/HachiMark.jsx"},{"name":"LeashPrompt","sourcePath":"components/hachi/LeashPrompt.jsx"},{"name":"RunCard","sourcePath":"components/hachi/RunCard.jsx"},{"name":"Terminal","sourcePath":"components/hachi/Terminal.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"8edcb54d0233","components/core/Button.jsx":"0d38ad002290","components/core/Card.jsx":"ae976756fce6","components/core/Input.jsx":"bb4fd2e0dde0","components/core/StatusPill.jsx":"7c7de6fcf046","components/core/Switch.jsx":"5f429a7f242f","components/feedback/LoyalLoop.jsx":"1eb82b01ee18","components/feedback/Toast.jsx":"de20799080c2","components/hachi/HachiMark.jsx":"63c75e1f016b","components/hachi/LeashPrompt.jsx":"703ca7d21706","components/hachi/RunCard.jsx":"88bed3b42f43","components/hachi/Terminal.jsx":"4ba0f69e1004","ui_kits/cli/Cli.jsx":"0bce52359d87","ui_kits/tui/Tui.jsx":"0f434e8cf515","ui_kits/webapp/Sidebar.jsx":"f9ca54a2c28e","ui_kits/webapp/Workspace.jsx":"51ea28057fed","ui_kits/webapp/icons.jsx":"2d77dabd6a31"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.HachiDesignSystem_46e488 = window.HachiDesignSystem_46e488 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Badge — small count / meta chip. Subtle by default; `tone` for emphasis. */
function Badge({
  tone = "neutral",
  style = {},
  children,
  ...rest
}) {
  const tones = {
    neutral: {
      bg: "var(--hachi-cream)",
      fg: "var(--text-muted)"
    },
    brand: {
      bg: "var(--hachi-brand-tint)",
      fg: "var(--hachi-brand-hover)"
    },
    navy: {
      bg: "var(--hachi-trust-tint)",
      fg: "var(--hachi-trust)"
    }
  };
  const t = tones[tone] || tones.neutral;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      padding: "2px 8px",
      borderRadius: "var(--radius-sm)",
      background: t.bg,
      color: t.fg,
      fontFamily: "var(--font-body)",
      fontWeight: 500,
      fontSize: 12,
      lineHeight: 1.5,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Hachi Button — sentence case, radius 10, flat. Torii red used only for `primary`.
 */
function Button({
  variant = "primary",
  size = "md",
  icon = null,
  disabled = false,
  type = "button",
  onClick,
  children,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: {
      padding: "0 12px",
      height: 32,
      fontSize: 13
    },
    md: {
      padding: "0 16px",
      height: 40,
      fontSize: 14
    }
  };
  const variants = {
    primary: {
      background: "var(--hachi-brand)",
      color: "var(--text-on-brand)",
      border: "0.5px solid transparent"
    },
    secondary: {
      background: "transparent",
      color: "var(--hachi-trust)",
      border: "1px solid var(--hachi-trust)"
    },
    ghost: {
      background: "transparent",
      color: "var(--text-muted)",
      border: "0.5px solid transparent"
    },
    danger: {
      background: "var(--hachi-danger)",
      color: "#FBF7EF",
      border: "0.5px solid transparent"
    }
  };
  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    fontFamily: "var(--font-body)",
    fontWeight: 500,
    lineHeight: 1,
    borderRadius: "var(--radius-md)",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1,
    transition: "background var(--dur) var(--ease), color var(--dur) var(--ease), border-color var(--dur) var(--ease)",
    whiteSpace: "nowrap",
    ...sizes[size],
    ...variants[variant],
    ...style
  };
  const hoverBg = {
    primary: "var(--hachi-brand-hover)",
    secondary: "var(--hachi-trust-tint)",
    ghost: "var(--hachi-cream)",
    danger: "#A93226"
  }[variant];
  const onEnter = e => {
    if (!disabled) e.currentTarget.style.background = hoverBg;
  };
  const onLeave = e => {
    if (!disabled) e.currentTarget.style.background = variants[variant].background;
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    style: base,
    onMouseEnter: onEnter,
    onMouseLeave: onLeave
  }, rest), icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Card — surface on canvas, 0.5px hairline, radius 16, flat (no shadow). */
function Card({
  padding = 24,
  style = {},
  children,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-lg)",
      padding,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Input — cream-white surface, hairline border, red focus ring. Optional label. */
function Input({
  label,
  hint,
  mono = false,
  style = {},
  id,
  ...rest
}) {
  const inputId = id || (label ? `in-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const [focus, setFocus] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: inputId,
    style: {
      font: "var(--text-small)",
      color: "var(--text-default)",
      fontWeight: 500
    }
  }, label), /*#__PURE__*/React.createElement("input", _extends({
    id: inputId,
    onFocus: e => {
      setFocus(true);
      rest.onFocus?.(e);
    },
    onBlur: e => {
      setFocus(false);
      rest.onBlur?.(e);
    },
    style: {
      height: 40,
      padding: "0 12px",
      background: "var(--surface-card)",
      color: "var(--text-default)",
      fontFamily: mono ? "var(--font-mono)" : "var(--font-body)",
      fontSize: mono ? 13 : 14,
      border: focus ? "1px solid var(--hachi-brand)" : "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "0 0 0 3px var(--hachi-brand-tint)" : "none",
      outline: "none",
      transition: "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
      ...style
    }
  }, rest)), hint && /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)"
    }
  }, hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/StatusPill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * StatusPill — the four Hachi status states. Tinted bg + dark same-family text + dot.
 */
function StatusPill({
  status = "working",
  label,
  style = {},
  ...rest
}) {
  const map = {
    working: {
      bg: "var(--hachi-working-tint)",
      fg: "#A8651A",
      dot: "var(--hachi-working)",
      text: "working"
    },
    "on-watch": {
      bg: "var(--hachi-trust-tint)",
      fg: "var(--hachi-trust)",
      dot: "var(--hachi-trust)",
      text: "on watch"
    },
    done: {
      bg: "var(--hachi-success-tint)",
      fg: "#2C7A50",
      dot: "var(--hachi-success)",
      text: "done"
    },
    blocked: {
      bg: "var(--hachi-danger-tint)",
      fg: "#9E2D21",
      dot: "var(--hachi-danger)",
      text: "blocked"
    }
  };
  const s = map[status] || map.working;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      padding: "5px 12px",
      borderRadius: "var(--radius-pill)",
      background: s.bg,
      color: s.fg,
      fontFamily: "var(--font-body)",
      fontWeight: 500,
      fontSize: 13,
      lineHeight: 1,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: s.dot
    }
  }), label || s.text);
}
Object.assign(__ds_scope, { StatusPill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatusPill.jsx", error: String((e && e.message) || e) }); }

// components/core/Switch.jsx
try { (() => {
/** Switch — flat toggle. On = Torii red. The leash you can flip. */
function Switch({
  checked = false,
  onChange,
  disabled = false,
  label,
  style = {}
}) {
  const toggle = () => {
    if (!disabled) onChange?.(!checked);
  };
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    role: "switch",
    "aria-checked": checked,
    tabIndex: disabled ? -1 : 0,
    onClick: toggle,
    onKeyDown: e => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        toggle();
      }
    },
    style: {
      width: 40,
      height: 24,
      borderRadius: "var(--radius-pill)",
      background: checked ? "var(--hachi-brand)" : "var(--hachi-line)",
      border: "0.5px solid " + (checked ? "var(--hachi-brand)" : "var(--hachi-line)"),
      position: "relative",
      transition: "background var(--dur) var(--ease)",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      top: 2,
      left: checked ? 18 : 2,
      width: 18,
      height: 18,
      borderRadius: "50%",
      background: "var(--surface-card)",
      transition: "left var(--dur) var(--ease)"
    }
  })), label && /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-body)",
      color: "var(--text-default)"
    }
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Switch.jsx", error: String((e && e.message) || e) }); }

// components/feedback/LoyalLoop.jsx
try { (() => {
/**
 * LoyalLoop — the loading spinner. A figure-8 / infinity in Torii red.
 * 8 = ∞ = always on; "hachi" means eight.
 */
function LoyalLoop({
  size = 48,
  color = "var(--hachi-brand)",
  speed = 1.4,
  style = {}
}) {
  const w = size;
  const h = size * 0.6;
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 100 56",
    width: w,
    height: h,
    role: "img",
    "aria-label": "Loading",
    style: style
  }, /*#__PURE__*/React.createElement("path", {
    d: "M 39 28 C 39 16 23 16 23 28 C 23 40 39 40 49 28 C 59 16 75 16 75 28 C 75 40 59 40 49 28 Z",
    fill: "none",
    stroke: color,
    strokeWidth: "9",
    strokeLinecap: "round",
    strokeDasharray: "60 180",
    style: {
      animation: `hachi-loop-dash ${speed}s linear infinite`
    }
  }));
}
Object.assign(__ds_scope, { LoyalLoop });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/LoyalLoop.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
/**
 * Toast — a pill notification in Hachi's voice. Default tone "success" with a check.
 * e.g. "Task complete — Hachi is resting".
 */
function Toast({
  message = "Task complete — Hachi is resting",
  tone = "success",
  style = {}
}) {
  const tones = {
    success: {
      dot: "var(--hachi-success)",
      glyph: "✓"
    },
    working: {
      dot: "var(--hachi-working)",
      glyph: "•"
    },
    blocked: {
      dot: "var(--hachi-danger)",
      glyph: "!"
    }
  };
  const t = tones[tone] || tones.success;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-pill)",
      padding: "10px 18px 10px 12px",
      boxShadow: "0 4px 16px rgba(28,26,32,0.08)",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 22,
      height: 22,
      borderRadius: "50%",
      background: t.dot,
      color: "#FBF7EF",
      display: "grid",
      placeItems: "center",
      fontSize: 13,
      fontWeight: 500,
      flexShrink: 0
    }
  }, t.glyph), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-body)",
      fontSize: 14,
      color: "var(--text-default)"
    }
  }, message));
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/hachi/HachiMark.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * HachiMark — the two-tone mascot, inline so it never depends on an asset path.
 * Never recolour: the dog is always Torii red + cream + ink, in every screen.
 * `variant="knockout"` gives a one-colour silhouette in `currentColor` (16px-safe).
 */
function HachiMark({
  size = 40,
  variant = "two-tone",
  style = {},
  ...rest
}) {
  if (variant === "knockout") {
    return /*#__PURE__*/React.createElement("svg", _extends({
      viewBox: "0 0 100 100",
      width: size,
      height: size,
      role: "img",
      "aria-label": "Hachi",
      style: style
    }, rest), /*#__PURE__*/React.createElement("g", {
      transform: "translate(50,52)",
      fill: "currentColor",
      fillRule: "evenodd"
    }, /*#__PURE__*/React.createElement("path", {
      fillRule: "evenodd",
      d: "M -26 -14 C -30 4 -22 22 -9 28 C -3 32 3 32 9 28 C 22 22 30 4 26 -14 L 23 -44 L 8 -23 L -8 -23 L -23 -44 Z M -11 -7 C -8.9 -7 -7.2 -4.8 -7.2 -2 C -7.2 0.8 -8.9 3 -11 3 C -13.1 3 -14.8 0.8 -14.8 -2 C -14.8 -4.8 -13.1 -7 -11 -7 Z M 11 -7 C 13.1 -7 14.8 -4.8 14.8 -2 C 14.8 0.8 13.1 3 11 3 C 8.9 3 7.2 0.8 7.2 -2 C 7.2 -4.8 8.9 -7 11 -7 Z M -4 0 L 4 0 L 0 6 Z"
    })));
  }
  return /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 100 100",
    width: size,
    height: size,
    role: "img",
    "aria-label": "Hachi",
    style: style
  }, rest), /*#__PURE__*/React.createElement("g", {
    transform: "translate(50,52)"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M -26 -14 C -30 4 -22 22 -9 28 C -3 32 3 32 9 28 C 22 22 30 4 26 -14 L 23 -44 L 8 -23 L -8 -23 L -23 -44 Z",
    fill: "#D64933"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M -21 -40 L -11 -23 L -18 -23 Z",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M 21 -40 L 11 -23 L 18 -23 Z",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M -17 1 C -17 21 -7 28 0 28 C 7 28 17 21 17 1 C 9 -5 5 -8 0 -8 C -5 -8 -9 -5 -17 1 Z",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M -3 -8 L -2 -24 Q 0 -27 2 -24 L 3 -8 Z",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "-11",
    cy: "-13",
    r: "2.3",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "-13",
    r: "2.3",
    fill: "#F3E9D2"
  }), /*#__PURE__*/React.createElement("ellipse", {
    cx: "-11",
    cy: "-2",
    rx: "3.8",
    ry: "5",
    fill: "#1C1A20"
  }), /*#__PURE__*/React.createElement("ellipse", {
    cx: "11",
    cy: "-2",
    rx: "3.8",
    ry: "5",
    fill: "#1C1A20"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M -4 0 L 4 0 L 0 6 Z",
    fill: "#1C1A20"
  })));
}
Object.assign(__ds_scope, { HachiMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/hachi/HachiMark.jsx", error: String((e && e.message) || e) }); }

// components/hachi/LeashPrompt.jsx
try { (() => {
/**
 * LeashPrompt — Hachi's signature permission card. Calm, plain-language, never an error.
 * Dog icon + plain request + exact action (mono) + one-line "why" + three choices.
 * Caption: "you hold the leash".
 */
function LeashPrompt({
  request = "Hachi wants to run a command",
  action = "npm install",
  why = "Install the dependencies for your build",
  onDeny,
  onAllowOnce,
  onAlwaysAllow,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    role: "dialog",
    "aria-label": request,
    style: {
      width: 420,
      maxWidth: "100%",
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-lg)",
      padding: 24,
      display: "flex",
      flexDirection: "column",
      gap: 16,
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 14,
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flexShrink: 0,
      width: 48,
      height: 48,
      borderRadius: "var(--radius-md)",
      background: "var(--hachi-cream)",
      display: "grid",
      placeItems: "center"
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.HachiMark, {
    size: 34
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 4,
      paddingTop: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--text-heading)",
      fontSize: 18,
      lineHeight: "24px",
      color: "var(--text-default)"
    }
  }, request), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)"
    }
  }, "why: ", why))), /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--hachi-cream)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-md)",
      padding: "12px 14px",
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: "22px",
      color: "var(--text-default)",
      wordBreak: "break-word"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--hachi-brand)"
    }
  }, "hachi\xA0\u25B8"), " ", action), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "secondary",
    size: "md",
    onClick: onDeny,
    style: {
      flex: 1
    }
  }, "Deny"), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "primary",
    size: "md",
    onClick: onAllowOnce,
    style: {
      flex: 1
    }
  }, "Allow once"), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "ghost",
    size: "md",
    onClick: onAlwaysAllow,
    style: {
      flex: 1
    }
  }, "Always allow")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      font: "var(--text-small)",
      color: "var(--text-muted)",
      borderTop: "0.5px solid var(--hachi-line)",
      paddingTop: 12
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.HachiMark, {
    size: 16,
    variant: "knockout",
    style: {
      color: "var(--hachi-muted)"
    }
  }), "you hold the leash"));
}
Object.assign(__ds_scope, { LeashPrompt });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/hachi/LeashPrompt.jsx", error: String((e && e.message) || e) }); }

// components/hachi/RunCard.jsx
try { (() => {
/**
 * RunCard — a task with status, thin red progress bar, and always-visible budget.
 * Cost is a feature, not a setting to hide.
 */
function RunCard({
  title = "Refactor auth module",
  status = "working",
  progress = 0.4,
  spent = 0.02,
  budget = 1.0,
  meta,
  style = {},
  onClick
}) {
  const pct = Math.max(0, Math.min(1, progress));
  const money = n => "$" + n.toFixed(2);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    style: {
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-lg)",
      padding: 20,
      display: "flex",
      flexDirection: "column",
      gap: 14,
      cursor: onClick ? "pointer" : "default",
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--text-heading)",
      fontSize: 17,
      lineHeight: "22px",
      color: "var(--text-default)"
    }
  }, title), /*#__PURE__*/React.createElement(__ds_scope.StatusPill, {
    status: status
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      borderRadius: 999,
      background: "var(--hachi-line)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: pct * 100 + "%",
      height: "100%",
      background: "var(--hachi-brand)",
      borderRadius: 999,
      transition: "width var(--dur-slow) var(--ease)"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      font: "var(--text-small)",
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", null, meta || `${Math.round(pct * 100)}% complete`), /*#__PURE__*/React.createElement("span", null, "spent ", money(spent), " of ", money(budget))));
}
Object.assign(__ds_scope, { RunCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/hachi/RunCard.jsx", error: String((e && e.message) || e) }); }

// components/hachi/Terminal.jsx
try { (() => {
/**
 * Terminal — the dark mono surface with the red "hachi ▸" prompt.
 * `lines` is an array of { text, tone? } where tone tints the line.
 */
function Terminal({
  lines = [],
  prompt = "run build --watch",
  style = {}
}) {
  const toneColor = {
    muted: "#9C968C",
    brand: "#E25A44",
    working: "#E0922E",
    success: "#3F9D6B",
    danger: "#E05D4C",
    default: "#FBF7EF"
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: "#16151A",
      borderRadius: "var(--radius-lg)",
      padding: 20,
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: "22px",
      color: "#FBF7EF",
      ...style
    }
  }, lines.map((l, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      color: toneColor[l.tone] || toneColor.default,
      whiteSpace: "pre-wrap"
    }
  }, l.text)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#E25A44",
      flexShrink: 0
    }
  }, "hachi\xA0\u25B8"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FBF7EF"
    }
  }, prompt), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 16,
      background: "#E25A44",
      display: "inline-block",
      animation: "hachi-caret 1s steps(1) infinite",
      marginLeft: 1
    }
  })), /*#__PURE__*/React.createElement("style", null, `@keyframes hachi-caret{50%{opacity:0}}`));
}
Object.assign(__ds_scope, { Terminal });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/hachi/Terminal.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cli/Cli.jsx
try { (() => {
// Hachi CLI — a realistic terminal transcript in a window frame. Self-contained dark surface.
const C = {
  canvas: "#16151A",
  bar: "#201E25",
  line: "#322F38",
  ink: "#FBF7EF",
  muted: "#9C968C",
  brand: "#E25A44",
  amber: "#E0922E",
  green: "#3F9D6B",
  navy: "#7C9BD1",
  danger: "#E0594A"
};
function L({
  children,
  color = C.ink,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      color,
      whiteSpace: "pre-wrap",
      ...style
    }
  }, children);
}
function Prompt({
  children
}) {
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.green
    }
  }, "~/acme/api"), " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.muted
    }
  }, "$"), " ", children);
}
function Cli() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      display: "grid",
      placeItems: "center",
      padding: 28,
      boxSizing: "border-box",
      background: "var(--surface-page)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 760,
      maxWidth: "100%",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      border: "0.5px solid var(--hachi-line)",
      background: C.canvas
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "10px 14px",
      background: C.bar,
      borderBottom: `1px solid ${C.line}`
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 11,
      height: 11,
      borderRadius: "50%",
      background: "#E0594A"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 11,
      height: 11,
      borderRadius: "50%",
      background: "#E0922E"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 11,
      height: 11,
      borderRadius: "50%",
      background: "#3F9D6B"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      textAlign: "center",
      color: C.muted,
      fontFamily: "var(--font-mono)",
      fontSize: 12
    }
  }, "hachi \u2014 zsh")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: "22px",
      padding: 18,
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(Prompt, null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.brand
    }
  }, "hachi"), " run \"refactor auth module\" --budget 1.00"), /*#__PURE__*/React.createElement(L, {
    color: C.muted
  }, "hachi \u25B8 on watch \xB7 budget $1.00"), /*#__PURE__*/React.createElement(L, {
    color: C.muted
  }, "\u2192 scanning src/auth (12 files)"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 8
    }
  }), /*#__PURE__*/React.createElement(L, {
    color: C.brand
  }, "\u25B8 Hachi wants to run a command"), /*#__PURE__*/React.createElement(L, {
    color: C.ink
  }, "  ", "npm install"), /*#__PURE__*/React.createElement(L, {
    color: C.muted
  }, "  ", "why: install the dependencies for your build"), /*#__PURE__*/React.createElement(L, {
    style: {
      marginTop: 2
    }
  }, "  ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.navy
    }
  }, "[d]"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.muted
    }
  }, "eny  "), /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.brand
    }
  }, "[a]"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.muted
    }
  }, "llow once  "), /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.muted
    }
  }, "[A]lways"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.muted
    }
  }, "     ", "you hold the leash")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.brand
    }
  }, "\u276F"), " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: C.ink
    }
  }, "a")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 8
    }
  }), /*#__PURE__*/React.createElement(L, {
    color: C.green
  }, "\u2713 allowed \u2014 running npm install"), /*#__PURE__*/React.createElement(L, {
    color: C.muted
  }, "\u2192 added 214 packages in 3.1s"), /*#__PURE__*/React.createElement(L, {
    color: C.green
  }, "\u2713 session.ts \u2014 extracted token guard"), /*#__PURE__*/React.createElement(L, {
    color: C.green
  }, "\u2713 tests passing (28/28)"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 8
    }
  }), /*#__PURE__*/React.createElement(L, {
    color: C.ink
  }, "Task complete \u2014 Hachi is resting."), /*#__PURE__*/React.createElement(L, {
    color: C.muted
  }, "spent $0.21 of $1.00 \xB7 1m 04s"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 6
    }
  }), /*#__PURE__*/React.createElement(Prompt, null, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 15,
      background: C.brand,
      display: "inline-block",
      verticalAlign: "middle",
      animation: "hachi-caret 1s steps(1) infinite"
    }
  })))), /*#__PURE__*/React.createElement("style", null, `@keyframes hachi-caret{50%{opacity:0}}`));
}
window.Cli = Cli;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cli/Cli.jsx", error: String((e && e.message) || e) }); }

// ui_kits/tui/Tui.jsx
try { (() => {
// Hachi TUI (Textual) — full-screen terminal layout: header, runs panel, output log, leash dialog, footer.
// Colors are the dark-surface literals (the TUI is always dark).
const TUI = {
  canvas: "#16151A",
  surface: "#201E25",
  line: "#322F38",
  ink: "#FBF7EF",
  muted: "#9C968C",
  brand: "#E25A44",
  amber: "#E0922E",
  green: "#3F9D6B",
  danger: "#E0594A",
  navy: "#7C9BD1"
};
function Panel({
  title,
  accent = TUI.muted,
  children,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      border: `1px solid ${TUI.line}`,
      borderRadius: 8,
      background: TUI.surface,
      padding: "14px 14px 12px",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      top: -9,
      left: 12,
      padding: "0 6px",
      background: TUI.surface,
      color: accent,
      fontSize: 12
    }
  }, title), children);
}
function RunRow({
  run,
  active,
  onClick
}) {
  const dot = {
    working: TUI.amber,
    "on-watch": TUI.navy,
    done: TUI.green,
    blocked: TUI.danger
  }[run.status];
  const word = {
    working: "working",
    "on-watch": "on watch",
    done: "done",
    blocked: "blocked"
  }[run.status];
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "5px 8px",
      borderRadius: 5,
      cursor: "pointer",
      background: active ? TUI.canvas : "transparent",
      color: active ? TUI.ink : TUI.muted,
      borderLeft: `2px solid ${active ? TUI.brand : "transparent"}`
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: dot
    }
  }, "\u25CF"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }
  }, run.title), /*#__PURE__*/React.createElement("span", {
    style: {
      color: dot,
      fontSize: 12
    }
  }, word));
}
function LeashDialog({
  onChoose
}) {
  const [hov, setHov] = React.useState(null);
  const btn = (key, label, idx, color) => /*#__PURE__*/React.createElement("button", {
    onClick: () => onChoose(label),
    onMouseEnter: () => setHov(idx),
    onMouseLeave: () => setHov(null),
    style: {
      fontFamily: "inherit",
      fontSize: 13,
      cursor: "pointer",
      padding: "5px 12px",
      borderRadius: 5,
      border: `1px solid ${hov === idx ? color : TUI.line}`,
      background: hov === idx ? color : "transparent",
      color: hov === idx ? TUI.canvas : color
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.7
    }
  }, key), " ", label);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      inset: 0,
      background: "rgba(10,9,12,0.55)",
      display: "grid",
      placeItems: "center",
      borderRadius: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 440,
      border: `1px solid ${TUI.brand}`,
      borderRadius: 8,
      background: TUI.surface,
      padding: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      color: TUI.ink,
      fontSize: 14,
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.brand
    }
  }, "\u25B8"), " Hachi wants to run a command"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: TUI.muted,
      fontSize: 12,
      marginBottom: 12
    }
  }, "why: install the dependencies for your build"), /*#__PURE__*/React.createElement("div", {
    style: {
      background: TUI.canvas,
      border: `1px solid ${TUI.line}`,
      borderRadius: 5,
      padding: "9px 12px",
      color: TUI.ink,
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.brand
    }
  }, "hachi \u25B8"), " npm install"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, btn("d", "Deny", 0, TUI.navy), btn("a", "Allow once", 1, TUI.brand), btn("A", "Always allow", 2, TUI.muted)), /*#__PURE__*/React.createElement("div", {
    style: {
      color: TUI.muted,
      fontSize: 12,
      marginTop: 12,
      borderTop: `1px solid ${TUI.line}`,
      paddingTop: 10
    }
  }, "you hold the leash")));
}
function FooterKey({
  k,
  label
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      gap: 6,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.brand
    }
  }, k), /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.muted
    }
  }, label));
}
const RUNS = [{
  id: 1,
  title: "Refactor auth module",
  status: "working"
}, {
  id: 2,
  title: "Migrate tests to Vitest",
  status: "on-watch"
}, {
  id: 3,
  title: "Generate API docs",
  status: "done"
}, {
  id: 4,
  title: "Audit dependencies",
  status: "blocked"
}];
function Tui() {
  const [active, setActive] = React.useState(1);
  const [dialog, setDialog] = React.useState(true);
  const [log, setLog] = React.useState([{
    t: "hachi ▸ run refactor --watch",
    c: TUI.ink
  }, {
    t: "→ scanning src/auth (12 files)",
    c: TUI.muted
  }, {
    t: "✓ session.ts — extracted token guard",
    c: TUI.green
  }, {
    t: "on watch · spent $0.02 of $1.00",
    c: TUI.muted
  }]);
  const choose = label => {
    setDialog(false);
    const line = label === "Deny" ? {
      t: "✗ denied — Hachi is resting",
      c: TUI.danger
    } : {
      t: "✓ allowed — running npm install",
      c: TUI.green
    };
    setLog(l => [...l, line]);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: "22px",
      background: TUI.canvas,
      color: TUI.ink,
      height: "100%",
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      padding: "8px 14px",
      background: TUI.surface,
      borderBottom: `1px solid ${TUI.line}`
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.brand
    }
  }, "hachi\xA0\u25B8"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.muted,
      marginLeft: 10
    }
  }, "on watch"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.muted
    }
  }, "spent $0.41 of $5.00"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.line,
      margin: "0 10px"
    }
  }, "\u2502"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.muted
    }
  }, "14:22")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      gap: 12,
      padding: 14,
      minHeight: 0,
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement(Panel, {
    title: " runs \xB7 4 ",
    accent: TUI.brand,
    style: {
      width: 280,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, RUNS.map(r => /*#__PURE__*/React.createElement(RunRow, {
    key: r.id,
    run: r,
    active: active === r.id,
    onClick: () => setActive(r.id)
  })))), /*#__PURE__*/React.createElement(Panel, {
    title: " output \xB7 refactor auth module ",
    accent: TUI.muted,
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 1
    }
  }, log.map((l, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      color: l.c
    }
  }, l.t)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: TUI.brand
    }
  }, "hachi \u25B8"), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 15,
      background: TUI.brand,
      display: "inline-block",
      animation: "hachi-caret 1s steps(1) infinite"
    }
  })))), dialog && /*#__PURE__*/React.createElement(LeashDialog, {
    onChoose: choose
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 20,
      padding: "7px 14px",
      background: TUI.surface,
      borderTop: `1px solid ${TUI.line}`
    }
  }, /*#__PURE__*/React.createElement(FooterKey, {
    k: "^n",
    label: "new run"
  }), /*#__PURE__*/React.createElement(FooterKey, {
    k: "^p",
    label: "the pack"
  }), /*#__PURE__*/React.createElement(FooterKey, {
    k: "^k",
    label: "the kennel"
  }), /*#__PURE__*/React.createElement(FooterKey, {
    k: "^l",
    label: "leash"
  }), /*#__PURE__*/React.createElement(FooterKey, {
    k: "^q",
    label: "quit"
  })), /*#__PURE__*/React.createElement("style", null, `@keyframes hachi-caret{50%{opacity:0}}`));
}
window.Tui = Tui;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/tui/Tui.jsx", error: String((e && e.message) || e) }); }

// ui_kits/webapp/Sidebar.jsx
try { (() => {
// Hachi web app — left navigation rail. Wordmark, nav, and always-visible budget summary.
const {
  HachiMark
} = window.HachiDesignSystem_46e488;
function NavItem({
  icon,
  label,
  active,
  hint,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      width: "100%",
      padding: "9px 12px",
      borderRadius: "var(--radius-md)",
      border: "none",
      background: active ? "var(--hachi-cream)" : hover ? "var(--hachi-cream)" : "transparent",
      color: active ? "var(--text-default)" : "var(--text-muted)",
      font: "var(--text-body)",
      fontSize: 14,
      fontWeight: active ? 500 : 400,
      cursor: "pointer",
      textAlign: "left",
      transition: "background var(--dur) var(--ease)"
    }
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: icon,
    size: 18,
    style: {
      color: active ? "var(--hachi-brand)" : "currentColor"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, label), hint != null && /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)",
      fontVariantNumeric: "tabular-nums"
    }
  }, hint));
}
function Sidebar({
  active = "runs",
  onNavigate = () => {}
}) {
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 248,
      flexShrink: 0,
      background: "var(--surface-card)",
      borderRight: "0.5px solid var(--hachi-line)",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      padding: 16,
      boxSizing: "border-box"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "6px 8px 18px"
    }
  }, /*#__PURE__*/React.createElement(HachiMark, {
    size: 30
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 500,
      fontSize: 22,
      color: "var(--text-default)"
    }
  }, "hachi")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(NavItem, {
    icon: "list-checks",
    label: "Runs",
    hint: "3",
    active: active === "runs",
    onClick: () => onNavigate("runs")
  }), /*#__PURE__*/React.createElement(NavItem, {
    icon: "layers",
    label: "The pack",
    hint: "2",
    active: active === "pack",
    onClick: () => onNavigate("pack")
  }), /*#__PURE__*/React.createElement(NavItem, {
    icon: "shopping-bag",
    label: "The kennel",
    active: active === "kennel",
    onClick: () => onNavigate("kennel")
  }), /*#__PURE__*/React.createElement(NavItem, {
    icon: "terminal",
    label: "Terminal",
    active: active === "terminal",
    onClick: () => onNavigate("terminal")
  }), /*#__PURE__*/React.createElement(NavItem, {
    icon: "settings",
    label: "Settings",
    active: active === "settings",
    onClick: () => onNavigate("settings")
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--hachi-cream)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-md)",
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)",
      marginBottom: 8
    }
  }, "Today's budget"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 6,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 500,
      fontSize: 22,
      color: "var(--text-default)"
    }
  }, "$0.41"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)"
    }
  }, "of $5.00")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      borderRadius: 999,
      background: "var(--hachi-line)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: "8%",
      height: "100%",
      background: "var(--hachi-brand)",
      borderRadius: 999
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 7,
      marginTop: 12,
      font: "var(--text-small)",
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement(HachiMark, {
    size: 15,
    variant: "knockout",
    style: {
      color: "var(--hachi-muted)"
    }
  }), "you hold the leash")));
}
window.Sidebar = Sidebar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/webapp/Sidebar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/webapp/Workspace.jsx
try { (() => {
// Hachi web app — main Runs workspace. Interactive: start a run → leash prompt → allow → toast.
const {
  RunCard,
  LeashPrompt,
  Button,
  Toast
} = window.HachiDesignSystem_46e488;
const SEED_RUNS = [{
  id: 1,
  title: "Refactor auth module",
  status: "working",
  progress: 0.42,
  spent: 0.02,
  budget: 1.0,
  meta: "Editing session.ts"
}, {
  id: 2,
  title: "Migrate test suite to Vitest",
  status: "on-watch",
  progress: 0.15,
  spent: 0.01,
  budget: 0.5,
  meta: "Hachi is on watch"
}, {
  id: 3,
  title: "Generate API docs",
  status: "done",
  progress: 1,
  spent: 0.18,
  budget: 1.0,
  meta: "Hachi is resting"
}, {
  id: 4,
  title: "Audit dependencies for CVEs",
  status: "blocked",
  progress: 0.6,
  spent: 0.09,
  budget: 1.0,
  meta: "Needs your approval"
}];
function TopBar({
  onNewRun
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 16,
      padding: "0 32px",
      height: 68,
      flexShrink: 0,
      borderBottom: "0.5px solid var(--hachi-line)",
      background: "var(--surface-page)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: "var(--text-heading)",
      fontSize: 22,
      lineHeight: "26px"
    }
  }, "Runs")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      height: 38,
      padding: "0 12px",
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-md)",
      color: "var(--text-muted)",
      width: 220
    }
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "search",
    size: 16
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--text-small)"
    }
  }, "Search runs")), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    onClick: onNewRun,
    icon: /*#__PURE__*/React.createElement(window.Icon, {
      name: "plus",
      size: 16
    })
  }, "New run"));
}
function Workspace() {
  const [runs, setRuns] = React.useState(SEED_RUNS);
  const [prompt, setPrompt] = React.useState(null);
  const [toast, setToast] = React.useState(null);
  const flashToast = (message, tone = "success") => {
    setToast({
      message,
      tone
    });
    setTimeout(() => setToast(null), 3200);
  };
  const newRun = () => {
    setPrompt({
      request: "Hachi wants to run a command",
      action: "npm install && npm run build",
      why: "Set up the workspace for your new run"
    });
  };
  const allow = () => {
    const id = Date.now();
    setRuns(r => [{
      id,
      title: "Build and test workspace",
      status: "working",
      progress: 0.08,
      spent: 0.0,
      budget: 1.0,
      meta: "Hachi is working"
    }, ...r]);
    setPrompt(null);
    flashToast("On it — Hachi is working", "working");
  };
  const deny = () => {
    setPrompt(null);
    flashToast("Stayed put — Hachi is resting", "success");
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      height: "100%",
      flex: 1,
      minWidth: 0,
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement(TopBar, {
    onNewRun: newRun
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: 32
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--text-small)",
      color: "var(--text-muted)",
      marginBottom: 16
    }
  }, runs.length, " runs \xB7 ", runs.filter(r => r.status === "working").length, " working \xB7", " ", runs.filter(r => r.status === "blocked").length, " need you"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
      gap: 16,
      maxWidth: 1080
    }
  }, runs.map(r => /*#__PURE__*/React.createElement(RunCard, {
    key: r.id,
    title: r.title,
    status: r.status,
    progress: r.progress,
    spent: r.spent,
    budget: r.budget,
    meta: r.meta
  })))), prompt && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      inset: 0,
      background: "rgba(28,26,32,0.32)",
      display: "grid",
      placeItems: "center",
      padding: 24,
      zIndex: 10
    },
    onClick: deny
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement(LeashPrompt, {
    request: prompt.request,
    action: prompt.action,
    why: prompt.why,
    onDeny: deny,
    onAllowOnce: allow,
    onAlwaysAllow: allow
  }))), toast && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      bottom: 28,
      left: "50%",
      transform: "translateX(-50%)",
      zIndex: 20
    }
  }, /*#__PURE__*/React.createElement(Toast, {
    message: toast.message,
    tone: toast.tone
  })));
}
window.Workspace = Workspace;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/webapp/Workspace.jsx", error: String((e && e.message) || e) }); }

// ui_kits/webapp/icons.jsx
try { (() => {
// Lucide icons (ISC) — inline path data, stroke 1.75, currentColor. The documented Hachi icon set.
const HACHI_ICON_PATHS = {
  "list-checks": '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  "shopping-bag": '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  terminal: '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  "chevron-right": '<path d="m9 18 6-6-6-6"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  pause: '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  "git-branch": '<line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>'
};
function Icon({
  name,
  size = 18,
  strokeWidth = 1.75,
  style = {},
  ...rest
}) {
  return React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flexShrink: 0,
      ...style
    },
    dangerouslySetInnerHTML: {
      __html: HACHI_ICON_PATHS[name] || ""
    },
    ...rest
  });
}
window.Icon = Icon;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/webapp/icons.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.StatusPill = __ds_scope.StatusPill;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.LoyalLoop = __ds_scope.LoyalLoop;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.HachiMark = __ds_scope.HachiMark;

__ds_ns.LeashPrompt = __ds_scope.LeashPrompt;

__ds_ns.RunCard = __ds_scope.RunCard;

__ds_ns.Terminal = __ds_scope.Terminal;

})();
