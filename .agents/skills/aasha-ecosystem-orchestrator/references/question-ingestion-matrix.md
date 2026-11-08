# Universal Question Ingestion & Transformation Matrix

This reference specifies how the autonomous agent swarm ingests and standardizes any raw schoolbook question into the interactive `<aasha-game-quest>` Web Component.

---

## 1. Supported Raw Question Formats

```
                     ┌────────────────────────────────┐
                     │    Raw Textbook Question PDF   │
                     └───────────────┬────────────────┘
                                     │
         ┌───────────────┬───────────┴───────────┬───────────────┐
         ▼               ▼                       ▼               ▼
    [Format A]      [Format B]              [Format C]      [Format D]
    Standard MCQ    Cloze / Blanks          Match Columns   Numerical Steps
         │               │                       │               │
         └───────────────┼───────────────────────┼───────────────┘
                         ▼
        ┌─────────────────────────────────────────────────┐
        │  Method B Parser & Semantic Classifier (Laya)   │
        └────────────────────────┬────────────────────────┘
                                 │
                                 ▼
        ┌─────────────────────────────────────────────────┐
        │       Standardized `<aasha-game-quest>`         │
        │   - 3-Tier Mastery Loop (Discover/Apply/Master) │
        │   - 4-Tier Progressive Hints (H1 -> H4)         │
        │   - Anti-Spoiler Misconception Explanations (m) │
        │   - Web Audio Streak Shields & Haptic Feedback  │
        └─────────────────────────────────────────────────┘
```

---

## 2. Transformation Rules by Question Type

### Format A: Standard Multiple Choice Questions (MCQ)
* **Raw Input**: Stem text + 4 options (A, B, C, D).
* **Target Schema**: Single-tap choice cards (`data-tap-select="true"`, min $44 \times 44\text{px}$).
* **Socratic Requirement**: For each wrong choice, generate attribute `m` containing a targeted reasoning cue without mentioning the correct option index or value.

### Format B: Fill-in-the-Blank / Sentence Completion
* **Raw Input**: Text with missing term (`___`) and word bank.
* **Target Schema**: Interactive token shelf. Tapping a token moves it into the active sentence slot.
* **Socratic Requirement**: Incorrect token placements trigger semantic hints explaining the term's contextual meaning.

### Format C: Matching Pairs / Multi-Column Association
* **Raw Input**: Column I (Terms) vs Column II (Definitions/Images).
* **Target Schema**: Dual-column interactive nodes on SVG canvas. Tapping left node then right node draws an animated connecting line.
* **Socratic Requirement**: Mismatched pairs trigger elimination feedback ($H_3$).

### Format D: Multi-Stage Numerical Calculations
* **Raw Input**: Word problem requiring multi-step arithmetic/algebraic evaluation.
* **Target Schema**: Stepped calculation quest with intermediate milestone verification and parameter sliders.
* **Socratic Requirement**: $H_1$ gives physical intuition, $H_2$ provides visual diagram, $H_3$ gives formula relationship, $H_4$ gives step-by-step arithmetic check.

### Format E: Diagram / Structural Labelling
* **Raw Input**: Anatomical, botanical, or physical diagram with labelled pointers.
* **Target Schema**: 100% inlined SVG with clickable target zones. No external PNG/JPEG CDN dependencies.
* **Socratic Requirement**: Tapping wrong region displays directional guidance (e.g. "Notice: X is located above the primary valve").
