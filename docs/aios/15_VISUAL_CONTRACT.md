# 15_VISUAL_CONTRACT.md
# Visual Manipulative & Educational Gamification Contracts

Visual and interactive elements must serve concrete pedagogical functions. Gamification purely for superficial engagement without conceptual alignment is strictly prohibited.

---

### VISUAL CONTRACT: VIS-001 Interactive SVG Fraction Bar
- **VISUAL ID**: VIS-001
- **CONCEPT**: Unit Whole Partitioning & Fractional Shading
- **LEARNING OBJECTIVE**: Visually demonstrate that equal partition size is required for fractional equivalence.
- **INPUT**:
  - Number of partitions: integer slider/stepper (range 2 to 12).
  - Shaded segments: tap-to-select toggle on individual segment rects.
- **INTERACTION**:
  - Tap '+' or '-' buttons to partition the bar into $N$ equal slices.
  - Tap any slice to toggle shaded state (green fill vs light gray outline).
  - **Prohibition**: No drag-and-drop gestures.
- **STATE**:
  ```json
  {
    "partitions": 4,
    "shadedIndices": [0, 1],
    "fractionValue": 0.5,
    "displayNumerator": 2,
    "displayDenominator": 4
  }
  ```
- **VISUAL REPRESENTATION**: Inline vector `<svg>` element with `viewBox="0 0 400 80"`. Slices rendered as distinct `<rect>` elements with 2px stroke borders and smooth CSS fill transitions.
- **FEEDBACK**:
  - Real-time reactive mathematical fraction readout ($\frac{2}{4}$) displayed above bar.
  - Verbal message: "2 out of 4 equal parts shaded".
- **SUCCESS CONDITION**: Matches target problem criteria (e.g. "Create $\frac{3}{4}$"). Triggers star animation and enables "Continue" button.
- **FAILURE / HINT CONDITION**: If user taps check before matching: displays hint highlighting remaining slices to tap.
- **ACCESSIBILITY**:
  - Keyboard accessible via `tabindex="0"` and arrow key controls (verified in `P0-A & ISS-02: Visual engine renders interactive SVG fraction bar with keyboard accessibility`).
  - High-contrast color palette: Dark green (`#16a34a`) on light background (`#f8fafc`).
- **TEXT & LANGUAGE**: All labels paired with bilingual Hindi phonetic tooltips (`CONN` tokens).
- **GAME MECHANIC**: Step completion grants +10 XP and triggers lightweight confetti burst.
- **ASSESSMENT CONNECTION**: Feeds directly into question `ASM-FRAC-001`.
- **DATA OUTPUT**: Emits `{ "tool": "fraction_bar", "actions_count": 5, "final_state": "3/4", "duration_sec": 18 }`.

---

### VISUAL CONTRACT: VIS-002 2D Perimeter & Area Grid Visualizer
- **VISUAL ID**: VIS-002
- **CONCEPT**: 2D Surface Area vs 1D Perimeter
- **LEARNING OBJECTIVE**: Allow students to construct rectilinear shapes and dynamically compare boundary perimeter against enclosed square units.
- **INPUT**: Grid dimensions $W \times H$ (tap steppers) and tile toggle taps.
- **STATE**: Grid matrix of boolean cells; boundary path calculation.
- **VISUAL REPRESENTATION**: Grid of $1 \times 1$ unit squares. Enclosed surface painted in teal; outer boundary traced with animated dashed orange line.
- **READOUT**: Dual simultaneous meters:
  - Perimeter Meter: $P = 2 \times (L + W) \text{ units}$
  - Area Meter: $A = L \times W \text{ square units}$
- **GAME MECHANIC**: "Garden Fencing Challenge" — student must fence an area of 24 with minimum wire.
- **EVIDENCE**: Verified by test `Generalization: Visual Engine renders modular 2D Grid Area model with dual readouts` (Node test 9 passing).
