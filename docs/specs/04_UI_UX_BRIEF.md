# AASHA AIOS — UI/UX Design & Viewport Specification
**Document Identifier:** `AASHA-SPEC-04-UI-UX-BRIEF`  
**Classification:** Canonical Interface & Design Specification  
**Version:** 2.0.0 (Unified Ecosystem Release)  
**Lifecycle Status:** APPROVED / LEVEL 1 SPECIFICATION  
**Primary Design Law:** Same-Frame Mobile Viewport Responsiveness (Zero Page Scrolling)

---

## 1. Design Philosophy & Visual Tenets

AASHA is designed for mobile-first, distraction-free educational engagement. It rejects the endless vertical scrolling feeds typical of web blogs. Instead, it adheres to the **Same-Frame Mobile Viewport Rule**:
* The entire learning card (concept definition, interactive simulation canvas, controls, and immediate feedback) must fit comfortably within the active viewport without requiring the student to scroll vertically.
* The interface provides tactile, high-contrast, thumb-friendly touch surfaces suitable for small budget smartphones (360px width) up to modern high-resolution displays.

---

## 2. Multi-Aspect Ratio Viewport Matrix

All compiled chapter modules must render cleanly without vertical page scroll across three canonical mobile device aspect ratios:

| Aspect Ratio | Device Archetype | Logical Dimensions | CSS Media Rule Clamping |
|---|---|---|---|
| **16:9 Budget Android** | Redmi 9A, Galaxy A03 | `360 x 640` px | `max-height: 640px` |
| **19.5:9 Modern iPhone** | iPhone 13/14/15 | `390 x 844` px | `max-height: 844px` |
| **20:9 Tall Android** | Galaxy S21/S22, Pixel 7 | `412 x 915` px | `max-height: 915px` |

### Hard Responsiveness Invariant
Automated Chrome CDP verification enforces the strict boundary assertion:
$$\text{document.documentElement.scrollHeight} \le \text{window.innerHeight} + 5\text{px}$$

---

## 3. Layout Architecture & Component Rules

### 3.1. Dynamic Canvas Sizing (`fitCanvas`)
Simulation canvases must adapt dynamically to available container dimensions while maintaining razor-sharp rendering on high-DPI retina screens:
```javascript
function fitCanvas(canvas, container) {
  const dpr = window.devicePixelRatio || 1;
  const rect = container.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
}
```

### 3.2. Single-Row Preset Navigation Bar
Control bars and parameter presets must never wrap onto multiple lines, which would break the vertical viewport budget:
```css
.preset-bar {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  overflow-x: auto;
  touch-action: pan-x;
  -webkit-overflow-scrolling: touch;
  gap: 8px;
  padding: 4px 8px;
}
.preset-bar::-webkit-scrollbar {
  display: none; /* Hide scrollbar for clean aesthetic */
}
```

### 3.3. 44x44px Minimum Touch Target Rule
In compliance with international accessibility standards (WCAG 2.1 Level AA) and tactile mobile ergonomics:
* Every interactive button, slider thumb, option card, and toggle switch must have a clickable bounding box of at least **$44 \times 44\text{ px}$**.
* If visual button size is smaller, an expanded touch target must be established using pseudo-elements (`::after` with negative margins).

### 3.4. Opaque Bottom Navigation Bar & Clearance
Fixed bottom navigation bars must prevent background simulation and card content from ghosting through:
```css
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: #ffffff;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.05);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 1000;
}

/* Scrollable container bottom clearance */
.screen, .card-container {
  padding-bottom: calc(72px + env(safe-area-inset-bottom, 16px));
}
```

---

## 4. Typography, Color System & Math Rendering

### 4.1. Color Palette (High-Contrast & Calming)
* **Surface Background:** `#F8FAFC` (Slate 50 — reduces eye strain).
* **Card Surface:** `#FFFFFF` with subtle border `1px solid #E2E8F0`.
* **Primary Accent:** `#2563EB` (Royal Blue 600 — interactive controls).
* **Success & Mastery:** `#059669` (Emerald 600 — correct feedback).
* **Diagnostic Amber:** `#D97706` (Amber 600 — gentle misconception cues; never alarming red).
* **Text High-Contrast:** `#0F172A` (Slate 900 — body readability).
* **Text Muted:** `#64748B` (Slate 500 — secondary annotations).

### 4.2. KaTeX Mathematical Typography
* Math formulas are rendered via local embedded KaTeX.
* Display formulas (`$$ ... $$`) are clamped to `font-size: 1.15rem` with horizontal overflow handling (`overflow-x: auto; overflow-y: hidden;`).
* Inline math (`\( ... \)`) aligns vertically with standard text baseline without causing line-height stutter.

### 4.3. Bilingual Tap Dialog Modal (`#wordDialog`)
* Placed at center screen or anchored as a bottom sheet.
* High z-index (`2000`) with semi-transparent backdrop (`rgba(15, 23, 42, 0.6)`).
* Displays bold Hindi word (e.g., `"विद्युत परिपथ"`), followed by simple phonetic pronunciation (`[vidyut paripath]`) and 1-line real-world explanation.
