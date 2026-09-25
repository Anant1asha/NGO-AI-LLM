# 02_DECISIONS.md
# Architecture & Governance Decision Records

This document preserves the immutable record of major architectural, pedagogical, and engineering decisions. Never erase historical records; if superseded, add a superseding record referencing the previous ID.

---

### DEC-001: Standalone Single-File HTML Deployment for Student Chapters
- **DECISION ID**: DEC-001
- **DATE**: 2026-09-01
- **STATUS**: VERIFIED
- **CONTEXT**: Target students attend Indian government schools with negligible, intermittent, or zero classroom internet access. Devices are typically low-cost Android smartphones (often shared with parents) or refurbished tablets.
- **PROBLEM**: Traditional cloud-hosted Web/PWA SPAs fail when connectivity drops, fail over spotty 2G/3G networks, and introduce CDN load dependencies.
- **OPTIONS**:
  1. Multi-page web app deployed to cloud CDN.
  2. Native Android APK containing chapter assets.
  3. Single-file self-contained HTML (all CSS, JS, SVGs, audio inlined via Base64).
- **CHOSEN OPTION**: Option 3 (Single-file self-contained HTML v5/v6 engine).
- **RATIONALE**: HTML files can be shared peer-to-peer via Bluetooth/Nearby Share, run in standard Android WebViews/browsers without app store installation, have zero runtime external network requests, and work 100% offline.
- **TRADE-OFFS**: File size must be strictly audited (<200KB–1MB budget); dynamic backend features cannot exist; all state must reside in localStorage.
- **REJECTED OPTIONS**:
  - Option 1: Unusable in zero-connectivity rural classrooms.
  - Option 2: High friction of APK installation, storage bloat, OS version fragmentation, security permissions warnings.
- **EVIDENCE**: Fractions and Perimeter chapters proven across 9 test rounds; 16/16 ecosystem tests pass.
- **IMPACT**: Complete offline accessibility across all low-end devices.
- **REVERSIBILITY**: Moderate; wrappers or PWAs can embed the standalone files, but breaking out of single-file format would break peer-to-peer sharing.
- **APPROVAL**: Annanth Aasha Technical & Pedagogical Board
- **MODEL**: N/A (Foundational Human Architecture)
- **RELATED FILES**: `Aasha_MVP_6_Documents.md`, `chapters/*.html`, `aasha-pipeline-with-master-json/template/v5-engine-template.html`
- **RELATED DECISIONS**: DEC-003

---

### DEC-002: Two-Tier Attempt Tracking & TEAS Engine Mastery Decoupling
- **DECISION ID**: DEC-002
- **DATE**: 2026-09-03
- **STATUS**: VERIFIED
- **CONTEXT**: Gamified learning often creates a conflict between formative learning (encouraging students to retry without penalty) and diagnostic assessment (measuring true initial conceptual understanding).
- **PROBLEM**: If retries override previous scores, students guess until correct, inflating mastery metrics. If retries penalize students, anxiety increases and gamification fails.
- **OPTIONS**:
  1. Single score ledger overwritten by final attempt.
  2. Strict single-attempt testing (no retries).
  3. Two-tier decoupled tracking: First attempt recorded in diagnostic ledger; subsequent retries recorded in progression/practice ledger.
- **CHOSEN OPTION**: Option 3 (Two-Tier Tracking).
- **RATIONALE**: Preserves rigorous diagnostic truth for learning analytics while providing a safe, gamified space for practice, hints, and mastery attainment.
- **TRADE-OFFS**: Requires double state management in the engine and outbox payloads.
- **REJECTED OPTIONS**:
  - Option 1: Corrupts diagnostic validity and misleads teachers/impact analysts.
  - Option 2: Frustrates learners and causes abandonment on wrong answers.
- **EVIDENCE**: Node test `ISS-01: Two-tier attempt tracking decouples diagnostic score from retries` passes in `tests/unit/learner.test.js`.
- **IMPACT**: Truthful impact metrics without sacrificing psychological safety.
- **REVERSIBILITY**: High; state schema is fully isolated.
- **APPROVAL**: Learning Experience & Assessment Architect
- **MODEL**: Claude 3.5 Sonnet / Gemini Reasoning
- **RELATED FILES**: `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/tests/unit/learner.test.js`, `Aasha_MVP_6_Documents.md`
- **RELATED DECISIONS**: DEC-004

---

### DEC-003: Zero-Spoiler Socratic Misconception Architecture
- **DECISION ID**: DEC-003
- **DATE**: 2026-09-04
- **STATUS**: VERIFIED
- **CONTEXT**: When students choose an incorrect answer, traditional quizzes either say "Wrong, the answer is C" or provide explanations that reveal the correct calculation.
- **PROBLEM**: Spoilers eliminate cognitive engagement and prevent genuine conceptual resolution.
- **OPTIONS**:
  1. Generic "Incorrect, try again" message.
  2. Full explanation displaying the correct formula and result.
  3. Distractor-specific verbal misconception explanations (`m` field) that diagnose the error without revealing the answer.
- **CHOSEN OPTION**: Option 3 (Zero-Spoiler Misconception Explanations).
- **RATIONALE**: Forces the learner to re-evaluate their mental model and re-engage with the manipulative or text.
- **TRADE-OFFS**: Requires significant pedagogical authoring effort per question distractor; verified by automated QA anti-spoiler linter.
- **REJECTED OPTIONS**:
  - Option 1: Provides zero formative feedback.
  - Option 2: Spoils the problem and rewards passive copying.
- **EVIDENCE**: Node test `P0-B & P0-D: Question engine extracts distractor-specific feedback and misconception IDs` passes.
- **IMPACT**: Significant increase in conceptual retention and error diagnosis.
- **REVERSIBILITY**: Low (core pedagogical tenet).
- **APPROVAL**: Assessment & Learning Architecture Lead
- **MODEL**: Claude 3.5 Sonnet
- **RELATED FILES**: `Aasha-AI/Aasha-AIOS/skills/assessment-authoring/SKILL.md`, `Aasha_MVP_6_Documents.md`
- **RELATED DECISIONS**: DEC-002

---

### DEC-004: Aggregate-Only Student Telemetry & Absolute Child Privacy
- **DECISION ID**: DEC-004
- **DATE**: 2026-09-05
- **STATUS**: VERIFIED
- **CONTEXT**: The platform operates in vulnerable communities and school environments where student data privacy is paramount.
- **PROBLEM**: Cloud telemetry often captures device fingerprints, IPs, student names, and granular timestamped location traces, violating child safety ethics.
- **OPTIONS**:
  1. Centralized user accounts with cloud database tracking individual student profiles.
  2. Local-only profile storage on physical device; telemetry payload strictly limited to anonymous aggregate competency gains and event counts.
- **CHOSEN OPTION**: Option 2 (Local-only PII + Aggregate Outbox Sync).
- **RATIONALE**: Student names and personal identifiers never leave the device. Telemetry contains only concept mastery, question attempts, and error code distributions.
- **TRADE-OFFS**: Cannot recover lost student profiles if a device is factory reset.
- **REJECTED OPTIONS**:
  - Option 1: High privacy liability, regulatory risk under child protection laws, and server maintenance overhead.
- **EVIDENCE**: Node test `impact reporting is aggregate-only` passes in `tests/integration/ecosystem.test.js`.
- **IMPACT**: Uncompromising child data protection and regulatory compliance.
- **REVERSIBILITY**: Low (ethical baseline).
- **APPROVAL**: Security & Privacy Reviewer, Product Lead
- **MODEL**: N/A
- **RELATED FILES**: `Aasha-AI/Aasha-Learning-Impact-Ecosystem-v0.3-full-repo/tests/integration/ecosystem.test.js`, `Aasha-AIOS/AGENTS.md`
- **RELATED DECISIONS**: DEC-001
