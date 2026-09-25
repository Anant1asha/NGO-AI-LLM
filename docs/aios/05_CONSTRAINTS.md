# 05_CONSTRAINTS.md
# Boundary Control & Mandatory System Constraints

This document defines non-negotiable boundaries, constraints, and prohibitions for all human contributors, AI models, and autonomous agents.

---

## 1. The 10 Critical Engineering Rules (Enforced by Automated QA)

1. **Zero Spoilers in Assessments**: Wrong answers must NEVER reveal the correct answer — only provide verbal, distractor-specific misconception explanations (`m` field).
2. **Mandatory Shuffling**: All quiz, visual question (VQ), solve, and worked example (WE) check options must be programmatically shuffled upon render.
3. **No Drag-and-Drop**: Touch interactions must use tap-to-select and tap-to-place ONLY (drag-and-drop is unreliable on low-cost resistive/capacitive screens).
4. **No Native Dialogs**: `confirm()`, `alert()`, or `prompt()` are strictly prohibited; they freeze low-end mobile webviews.
5. **Mandatory Skip Button**: Every interactive manipulative and simulation must include a visible skip button to prevent student entrapment.
6. **No Dead-End Buttons**: A navigation or submission button must NEVER be disabled if it is the only way forward.
7. **Phase State Tracking**: Multi-phase worked example check flows must track state using the `_weCheckRendered` pattern.
8. **Bounded LocalStorage**: Corrupt, missing, or out-of-bounds `localStorage` data must be handled gracefully with automatic fallback to default state without crashing.
9. **Instant Exit**: Calling `exit()` must perform an instantaneous reset and view switch without confirmation modal delays.
10. **Zero Dead Code**: Every kilobyte is proof of work — no unused CSS rules, orphaned JS functions, or extraneous polyfills.

---

## 2. Technical & Performance Constraints

- **Single File Target**: Generated student chapters must compile into a single `.html` file with all assets, styles, and scripts inlined.
- **Budget Target**: Target chapter size is <200 KB (maximum hard limit 1.0 MB for complex interactive sims).
- **Viewport**: Mobile-first design strictly constrained to `max-width: 480px`, centered on larger screens.
- **Offline Strictness**: Zero CDN links, zero remote web fonts, zero remote scripts, zero external image URLs.
- **Node.js Engines**: Node.js `>= 20` required across workspace packages.
- **Python Backend**: Python `>= 3.10` with strict Pydantic v2 schemas.

---

## 3. Privacy & Child Protection Constraints

- **Zero Student PII**: Student names, phone numbers, email addresses, biometric data, photos, audio recordings, or device hardware identifiers must NEVER be transmitted over network connections or stored in remote databases.
- **Anonymous Outbox Payloads**: Telemetry syncs must contain aggregate event counts, node completion flags, and anonymized diagnostic error codes only.
- **Local Profile Storage**: Student profiles (avatar choice, local nicknames) exist exclusively in device `localStorage`.

---

## 4. Licensing & Open-Source Constraints

- **Strict License Isolation**:
  - Core chapter output engine and framework are released under permissive open-source licenses (MIT).
  - External components with Copyleft (GPL-3.0, such as PhET) must not be statically linked/inlined in a manner that contaminates the entire MIT single-file chapter without legal compliance.
  - Components with Non-Commercial restrictions (such as GeoGebra) must NOT be distributed for commercial or unrestricted NGO grants without explicit written licensing.
- **Mandatory Registry Verification**: No third-party open-source library may be introduced into the build without an approved record in `18_OPEN_SOURCE_REGISTRY.md`.

---

## 5. Multi-Agent & LLM Operational Boundaries

- **Cost Cap**: LLM API costs for generating a complete chapter must remain `< $0.50` per textbook chapter.
- **Math Symbol Protection in LLE**: Translation engines must NEVER translate, transliterate, or mutate mathematical variables ($x$, $y$, $a$, $b$, $\pi$) or numerical expressions.
- **Least-Privilege Agency**: Agents have bounded scopes:
  - `IngestAgent` cannot modify source text or generate quizzes.
  - `AnalysisAgent` cannot exceed 5 concept nodes per chapter.
  - `QAAgent` cannot mutate content to force a test pass.
- **Human Approval Required For**:
  - Architectural modifications.
  - Schema alterations in `chapter_spec.json` or telemetry contracts.
  - Addition of new runtime dependencies.
  - Any destructive file operations.
