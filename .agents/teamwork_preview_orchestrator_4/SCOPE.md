# Project: Delta Route Deployment & Question Banks
# Scope: Hatchable Project `proj_wDCbCrGwuVqy` Delta Endpoint

## Architecture
- **Target Route**: `api/chapters/deltas.js` on Hatchable isolate `proj_wDCbCrGwuVqy`.
- **Export Contract**: `export const access = "public"`.
- **Query Parameters**:
  - `?grade=6` / `?grade=7` / `?grade=8` -> Returns delta for specific grade.
  - `?chapter=ID` -> Returns delta for specific chapter ID.
  - No parameter / default -> Returns metadata index or all active deltas with summary.
- **Payload Target**: <50 KB per grade payload (compressed/compact JSON) for fast offline-sync over 2G/mobile hotspots.
- **Data Model**:
  - Chapter Metadata (ID, title, subject, grade, version, timestamp).
  - Bilingual Vocabulary Map (`window.WM` / `rt()` format for Hindi support).
  - Manipulative Configurations (SVG fraction bars, 2D grid models, balance scales).
  - 3-Tier Gamified Assessment Bank (100% textbook exercises):
    - Warm-up (`#section-warmup`): Tier 1 foundational items.
    - Deep Dive (`#section-deep_dive`): Tier 2 conceptual items with 4-tier scaffolding (`H1`-`H4`).
    - Boss Challenge (`#section-boss`): Tier 3 Foundation F01 (Escape Run) timed cognitive obstacle evasion questions with streak multipliers.
  - Anti-spoiler validation: Every distractor has `m` attribute diagnosing misconception without leaking answers or using forbidden words (`is`, `becomes`, `yielding`, `result is`, `should be`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Hatchable Endpoint Scaffold | `api/chapters/deltas.js` with public access, query routing, error handling | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Class 6 Mathematics Bank | Fractions: visual partition models, equivalent fractions, 100% textbook exercises | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Class 7 Mathematics Bank | Perimeter & Area: 2D grid models, decomposition, measurement, textbook exercises | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Class 8 Mathematics Bank | Rational Numbers & Linear Equations: Balance scale models, identities, number line | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Anti-Spoiler & L-Truth Schema | 4 options, 1 correct, non-empty `m` without leaks, `H1`-`H4` hints | M1 | ORIGINAL_REQUEST §R2 |
| 6 | Manipulatives & F01 Mechanics | SVG specs, balance scales, Foundation F01 Escape Run boss challenge config | M1 | ORIGINAL_REQUEST §R4 |
| 7 | Bilingual Vocabulary | Hindi word-tap translations & conceptual definitions | M1 | ORIGINAL_REQUEST §R4 |
| 8 | Live Deployment & Verification | `write_files`, `dry_run_deploy`, `deploy`, `run_function` testing across grades | M2 | ORIGINAL_REQUEST §R3 |
| 9 | Payload Optimization | Verification that each grade payload is <50 KB | M2 | ORIGINAL_REQUEST §R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 0 | Survey & Specification | Map Hatchable project state, extract curriculum item banks, gather F01/L-Truth specs | none | IN_PROGRESS |
| 1 | Delta Route Implementation & Deploy | Build `api/chapters/deltas.js`, deploy to `proj_wDCbCrGwuVqy` | M0 | PLANNED |
| 2 | Review, Stress Testing & Live Verify | Review code, test live via `run_function`, check payload limits & query filters | M1 | PLANNED |
| 3 | Forensic Integrity Audit | Full forensic audit for no-cheating, anti-spoiler compliance, genuine implementation | M2 | PLANNED |
| 4 | Final Synthesis & Sentinel Report | Final delivery report to parent Sentinel agent | M3 | PLANNED |
