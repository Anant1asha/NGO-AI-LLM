---
name: aasha-ecosystem
description: >-
  Operational runbook for the AASHA Learning Ecosystem. Provides procedures,
  commands, and architectural rules for Super Admin Memory, the 20+ Prebuilt
  Open-Source Experience Foundations matcher, Dual-Benchmark certification,
  and Zero-Token Bleed circuit breaker routing.
---

# AASHA Learning Ecosystem Operational Skill

This skill guides agents and developers in operating the Annanth AASHA Foundation learning platform across any school, board (CBSE, ICSE, NCERT, State Boards), class (Class 1–10), and subject.

## Core Mandates & Golden Invariants

1. **Never Build From Scratch**:
   Always query the 20+ prebuilt open-source experience foundations in `Aasha-AI/experience_registry/registry.json` before designing any new simulation, game, or interactive exercise. Adapt foundations under `AashaExperienceContract`.

2. **Automated Chapter Contract & Resource Matcher**:
   Before generating or updating any chapter, initialize its Section 24 contract and matched foundation via:
   ```bash
   npm run chapter:init -- "<Subject>" <Class> "<Topic>"
   ```
   This automatically queries the 20+ foundations, creates `content/contracts/<Subject>_Class<Class>_<Topic>.yaml`, embeds the Resource Match Report, and binds the simulation adapter. The `AASHAGatekeeper` automatically enforces this in the background.

3. **Zero-Token Bleed Circuit Breaker**:
   Keep `ALLOW_PAID_GEMINI_FALLBACK=false` in `Aasha-AI/.env` to prevent cascading billing leakage during automated tasks. Automated batch jobs route through free OpenRouter models with 3s backoff on 429s.

4. **Pre-LLE Math Insulation**:
   Always insulate LaTeX math (`\( ... \)`, `$$ ... $$`, `$...$`) and single-letter algebraic variables with `__AASHA_MATH_X__` using `packages/aasha-rules/math_insulator.ts` before bilingual dictionary wrapping.

5. **Dual-Benchmark 100% Quality Invariant**:
   All chapters must pass both benchmarks:
   - Benchmark 1: `node benchmarks/qa_ltruth_benchmark.js` (100/100, 0 spoilers, 0 math collisions)
   - Benchmark 2: Headless Chrome CDP automation (`automated_browser_verification.js`: 0 console errors, 5-step navigation)

6. **GPL-3.0 License Isolation Policy**:
   Foundations licensed under GPL-3.0 (F04 PhET, F09 Escapp, F17 Code for Life) must strictly use `EXTRACT` or `INSPIRE` reuse strategies (extracting mathematical models, mechanics, and public assets) or run via clean iframe/adapter isolation to prevent copyleft contagion into the MIT core chapter files.

7. **Hindi-Focused Bilingual Substrate & Auto-Caching Engine**:
   Right now, **Hindi** is the sole active Indic language for bilingual word-tap popups (`window.WM`). Focus verification on 100% Hindi dictionary coverage, pronunciation accuracy, and math insulation. Whenever LLE Cascade translates a new word via Layer 2 or Layer 3, it automatically persists the translated entry into `hi.json` without BOM so subsequent builds reuse Layer 1 dictionary entries at 0 API cost and maximum efficiency.

8. **Unified 3-in-1 Pipeline Execution Modes**:
   - **Mode A (Autonomous Worker)**: Headless pipeline running Ingest -> QA with automated self-repair on benchmark failures.
   - **Mode B (Interactive Gate)**: `--interactive` flag pauses after Section 24 contract creation for Super Admin review.
   - **Mode C (Batch Folder Runner)**: `--batch-dir` processes full textbook directories under zero-bleed model rotation.

9. **Simulation Web Component & Telemetry (`<aasha-sim>`)**:
   All interactive simulations must adapt to `AashaExperienceContract` wrapped in the universal `<aasha-sim>` Web Component emitting bubbling `aasha:telemetry` and `aasha:state_change` CustomEvents.

10. **Balanced Runtime Lifecycle ($\ge 4$ GB RAM Invariant)**:
    All target deployment hardware possesses $\ge 4$ GB RAM. Never destroy DOM nodes or wipe canvas contexts on card collapse. Implement a non-destructive lifecycle: `pause()` (halts `requestAnimationFrame` loops and interval timers to save CPU and battery while preserving simulation state and canvas buffers) and `resume()`.

11. **Smart Dual Inlining & File Size Limit (20 MB)**:
    To prevent the 33% Base64 text overhead:
    - Inline raw JavaScript directly in `<script>` tags and CSS directly in `<style>` tags.
    - Reserve Base64 Data URIs (`data:...;base64,`) strictly for binary assets (images, audio, fonts).
    - Maximum self-contained chapter file size is 20 MB with SHA-256 local disk caching and 5s remote network timeouts.

12. **100% Textbook Exercise Utilization & Gamified 3-Tier Scaffolding**:
    Every single problem and exercise from the chapter PDF must be extracted and mapped into the 3-tier gamified progression:
    - **Tier 1: Warm-up** (`#section-warmup`) - Foundational mechanics & MCQs.
    - **Tier 2: Deep Dive** (`#section-deep_dive`) - Multi-step interactive problems linked to visual simulation.
    - **Tier 3: Boss Challenge** (`#section-boss`) - Complex textbook challenge problems.
    All questions must have pre-embedded misconception diagnostics (`m` attribute) and 4-tier progressive hints (`H1` hook $\rightarrow$ `H2` concept $\rightarrow$ `H3` formula $\rightarrow$ `H4` intermediate step) without any answer spoilers (L-Truth standard).

13. **Human-in-the-Loop (HIL) Teacher Console & Instant Browser Preview (`[O]`)**:
    The `multi-agent-tui` console enforces the 4-pillar pedagogical audit, provides a concise Hindi summary (`शिक्षक के लिए सारांश`) for non-technical educators, and enables instant browser verification via the `[O]` keystroke before final `[S]` sign-off.

14. **Python f-string Curly Brace Invariant**:
    In Python code synthesizers generating HTML/CSS/JS via f-strings, all literal braces must be double-escaped as `{{` and `}}` to prevent `NameError` runtime crashes.

15. **Multi-Agent TUI & Streaming JSON IPC Architecture**:
    The system follows a strict two-tier architecture:
    - **Tier 1: Autonomous Pipeline (Headless Background)**:
      • PyMuPDF ingestion & KaTeX math shielding (`packages/aasha-rules/math_insulator.ts`).
      • Phenomenon-First Micro-Worlds matched against Foundations F01–F20 (`Aasha-AI/experience_registry/registry.json`).
      • 3-Tier gamified assessment with strict 0-spoiler misconception diagnostics (`m` attribute).
      • Smart dual inlining (raw `<script>`/`<style>`, Base64 only for binaries, $\le 20\text{ MB}$ ceiling).
      • Emits structured line-delimited streaming events via `--json-events` flag.
    - **Tier 2: Multi-Agent TUI (Educator Standards & Readiness Console)**:
      • **Live Pipeline Monitor**: Real-time stage progress, agent activity stream, multimodal SHA-256 cache hits, and token usage tracker.
      • **4-Pillar Pedagogical Scorecard**:
        1. *Pillar 1: Golden Flow* (Discovery Order: WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME).
        2. *Pillar 2: Two-Layer Rigor* (Layer A Student Clarity vs Layer B Formal Academic/KaTeX Math).
        3. *Pillar 3: Misconception Audit* (100% diagnostic explanations in `m` attribute, strict 0 spoilers).
        4. *Pillar 4: Air-Gapped Child Safety* (0 external URLs, 0 tracking scripts, mobile viewport compliant).
      • **Remediation Workflow**:
        - `[R]`: Targeted Agent Auto-Repair (re-prompts flagged rule/agent).
        - `[E]`: Quick Inline Terminal Patch (in-place interactive regex text patch).
        - `[O]`: Instant browser preview (`शिक्षक पूर्वावलोकन`).
      • **Sign-Off Gating**:
        - Critical Flaws (spoilers, external URLs, corrupted math): HARD LOCKED (`signOffAllowed = false`).
        - Advisories (pacing, reading level): EDUCATOR OVERRIDE allowed.
        - `[S]`: One-Key Final Sign-Off certifying chapter for classroom deployment.

16. **Strict Question Schema Validation Engine**:
    All assessment questions and textbook exercises must be verified using `QuestionSchemaValidator` (`Aasha-AI/benchmarks/question_schema_validator.js` and `packages/aasha-rules/question_schema_validator.ts`). Never allow trivial placeholders (`"Review the concept"`) or numerical answer leaks in misconception explanations or progressive hints. Math text must be normalized (`normalizeMathText`) and short answers (< 3 chars) checked with word-boundary patterns.

17. **Multi-Aspect Ratio Same-Frame Layout Standard**:
    All standalone chapters must pass headless Chrome verification across 16:9 (360x640), 19.5:9 (390x844), and 20:9 (412x915).
    - Canvas must adapt via `fitCanvas(canvas)` using CSS logical pixels and DPR.
    - Preset bars must never wrap to multi-line (`flex-wrap: nowrap; overflow-x: auto; touch-action: pan-x;`).
    - Viewport overflow is strictly prohibited (`scrollH <= winH + 5`).
    - Touch targets must remain $\ge 44\times 44\text{px}$ across all viewports.

---

## 20+ Prebuilt Open-Source Foundations Catalog

| ID | Name | Core Mechanics & Prebuilt Capabilities | Primary Subjects & Grades |
| :--- | :--- | :--- | :--- |
| **F01** | **Escape Run** | Adaptive micro-skill practice, mastery gating, spaced repetition, PWA offline | Math, General (Grades 1–8) |
| **F02** | **MicroSims** | Concept simulations, interactive diagrams, visual models, parameter sliders | Math, Physics, Science, CS (Grades 4–10) |
| **F03** | **All Science Sims** | Offline browser science discovery models, chemistry/biology interactives | Science, Physics, Chemistry, Biology (Grades 6–10) |
| **F04** | **PhET Simulations** | Fraction bars, number line integers, equality explorer, friction, density | Math, Physics, Chemistry (Grades 3–10) |
| **F05** | **Lightbot** | Algorithmic sequencing, loops, conditionals, computational thinking | Computer Science, Math (Grades 2–9) |
| **F06** | **MathFluency** | Arithmetic fluency drills, misconception diagnostic gating | Mathematics (Grades 1–8) |
| **F07** | **Wiki Physics Game** | Story $\rightarrow$ Concept $\rightarrow$ Interaction $\rightarrow$ Question $\rightarrow$ Simulation | Physics, Science (Grades 6–10) |
| **F08** | **Physics Notebook** | Interactive canvas, parameter sliders, dynamic formula linkages | Physics, Mathematics (Grades 7–10) |
| **F09** | **Escapp** | Educational escape rooms, progressive clue tiers, hints, analytics | All Subjects, Science, Social (Grades 5–10) |
| **F10** | **QuestJS** | Branching narratives, scenario-based decisions, consequence tracking | History, Civics, Literature (Grades 5–10) |
| **F11** | **Squiffy** | Interactive branching fiction, ethical dilemma simulations | Civics, Moral Science, English (Grades 4–10) |
| **F12** | **GeoGuess** | Spatial reasoning, Indian geography, landmarks, map pin drops | Geography, Social Studies (Grades 3–10) |
| **F13** | **Learn Worldmap** | Spaced-repetition geography retrieval, outline map drills | Geography, Social Studies (Grades 4–10) |
| **F14** | **Geographical Adventures** | Spatial exploration missions, route planning, terrain mechanics | Geography, Environmental Science (Grades 4–9) |
| **F15** | **The Long Game** | Practical financial literacy, rupee currency, UPI, household budgeting | Financial Literacy, Math (Grades 6–10) |
| **F16** | **FinanceGame / LearnBu** | Scenario-based financial decision making, savings vs investment | Financial Literacy, Economics (Grades 7–10) |
| **F17** | **Code for Life** | Structured coding challenges, algorithmic logic | Computer Science (Grades 3–10) |
| **F18** | **Secure Code Game** | Digital safety, cybersecurity awareness, phishing prevention | Digital Literacy, Computer Science (Grades 6–10) |
| **F19** | **Chocolate Broccoli Challenge** | Quality-gated learning loops: Observe $\rightarrow$ Decide $\rightarrow$ Act $\rightarrow$ Result | All Subjects (Grades 1–10) |
| **F20** | **GameBox / Mini Games** | Offline touch interaction loops, mini-canvas tactile exercises | Math, Logic, Science (Grades 1–6) |

---

## Super Admin CLI Quick Reference

Run these commands from `c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI`:

```bash
# Check status of Dual Memory (Memo0 Cloud API + Local SQLite Graph)
npm run admin:status

# Auto-generate Resource Match Report & Section 24 YAML Contract
npm run chapter:init -- "Mathematics" 8 "Rational Numbers"
npm run chapter:init -- "Science" 7 "Acids and Bases"

# Generate standalone Resource Match Report for any topic
npm run admin:match -- "Mathematics" 8 "Rational Numbers"
npm run admin:match -- "Science" 7 "Acids and Bases"

# Seed all 24 AASHA pedagogical rules into the Knowledge Graph
npm run admin:seed

# Seed the 20 Open-Source Experience Foundations into Graph & Memory
npm run admin:seed-foundations

# Cement all 10 architectural chat trail pillars into persistent memory
npm run admin:learn

# Export complete memory snapshot with SHA-256 integrity checksum
npm run admin:backup

# Execute Dual-Benchmark QA suite
npm run test:all
```

---

## 7. Automated End-to-End Manual Verification Protocol

Whenever manual verification is requested or needed before chapter release, execute the automated headless Chrome CDP verification suite (`node verify_all_manual_steps.js`):

### Architecture & Runtime
1. **In-Process HTTP Server**: Spawns an internal HTTP server on an ephemeral or dedicated port (e.g. `3333`) serving HTML, JS modules, CSS, JSON, and web assets with correct MIME types and CORS headers.
2. **Headless Chrome CDP Harness**:
   - Launches Chrome with flags: `--remote-debugging-port=9223`, `--headless=new`, `--disable-gpu`, `--no-sandbox`.
   - Connects via WebSocket to the DevTools Protocol (`Page`, `Runtime`, `Emulation`).
   - Emulates mobile viewports (e.g. 390x844 @ 3x DPR).
3. **Execution Invariant**: Every `Runtime.evaluate` script payload MUST be enclosed in block scope `{ ... }` or IIFE `(() => { ... })()` to eliminate global identifier collision errors across multi-step browser evaluations.

### 7-Stage Verification Checklist
1. **Profile Onboarding**: Input learner details (`learnerName`, `classLevel`) and verify greeting rendering.
2. **Dynamic Chapter Switching**: Verify smooth switching across curriculum catalog (e.g. Fractions, Rational Numbers, Electric Circuits, Algebra) with dynamic DOM updates.
3. **Bilingual LLE Word-Tap**: Click vocabulary terms; verify `#wordDialog` modal displays correct Indic (Hindi) translation, definition, and phonetics. Verify math insulation prevents symbol corruption.
4. **Interactive Manipulatives**: Trigger touch events on simulation manipulatives (e.g., fraction slice partitioning, circuit switch toggle); verify synchronized DOM text readout updates.
5. **3-Tier Gamified Assessment & Hints**: Verify 4-tier scaffolding hint state machine ($H_1 \rightarrow H_4$) with strict 0-spoiler adherence; submit answer and verify XP/coin rewards.
6. **60 FPS Practice Loop**: Verify game loop HUD maintaining steady 60 FPS under active simulation and tactile card pairing mechanics in Match Arena.
7. **Evidence Ledger**: Verify auditable telemetry and assessment event persistence.
8. **Live Screenshot Artifacts**: Capture PNG screenshots (`Page.captureScreenshot`) at each milestone, save them into the active conversation artifact directory, and embed them in `walkthrough.md` via GFM ````carousel ```` components.

### 18. TypeScript Test Runner Standard (`npx tsx`)
When executing standalone TypeScript test files or modules (e.g. `packages/canonical-ir/test_canonical_ir.ts`), use `npx tsx` rather than `npx ts-node`. On Node v24+, `ts-node` without local `tsconfig.json` bindings can crash with `TypeError: Cannot read properties of undefined (reading 'fileExists')`. `npx tsx` provides fast, zero-config ESM and CommonJS TypeScript execution.

### 19. Canonical Prototype IR & Stateful V6 Engine Runbook
1. **Pipeline Execution**: Specialist agent proposals in YAML (`chapter_spec.yaml`) are compiled into Canonical IR (`canonical_ir.json`) via `IRAssembler.assemble()` (`packages/canonical-ir/ir_assembler.ts`).
2. **Stateful Compilation**: Canonical IR instances are compiled into single-file offline V6 HTML5 packages via `V6Compiler.compile()` (`packages/v6-engine/v6_compiler.ts`).
3. **Runtime Event Bus**: Client interaction state and TEAS mastery are managed by `V6RuntimeBus` (`packages/v6-engine/v6_runtime_bus.ts`) with offline event ledger persistence.

### 20. External Resource Discovery & Controlled Adapter Integration
When integrating external learning repositories (e.g. CinePhysics, PhET, OpenSourcePhysics):
1. **Strict Non-Negotiable Scope**: Focus only on Interactive Labs, Simulation Mechanics, Micro-Topic Mappings, and Math Rendering. Exclude external AI tutors, worksheet builders, site CSS, branding, and curriculum authorities.
2. **Audit Sequence**: `UNDERSTAND AASHA` -> `DISCOVER EXTERNAL RESOURCES` -> `RESOURCE MATCH REPORT` -> `LICENSE & OFFLINE AUDIT` -> `FOUR-CAPABILITY MATRIX` -> `MINIMAL ADAPTER INTEGRATION`.
3. **Experience Contract Compliance**: Wrap external simulations into ES6 classes extending `AashaExperienceAdapter` (`mount`, `getState`, `pause`, `resume`, `reset`, `destroy`, `emitTelemetry`).
4. **Offline Insulation**: Purge external CDN scripts (MathJax CDN, Google Tag Manager, remote fonts); insulate math formulas with AASHA's local KaTeX engine and `math_insulator.ts`.
5. **Curriculum Authority Invariant**: AASHA remains the sole canonical curriculum authority (`Class -> Subject -> Chapter -> Topic -> Experience`). External taxonomy datasets are mapped as supporting metadata under `content/mappings/`.

### 21. Compiler Inline Event Handler Quote Insulation (Dataset Pattern)
When writing code generators or HTML compilers (such as `v6_compiler.ts`) that produce inline event handlers inside template literals:
1. **Never nest quoted arguments**: Avoid `onclick="exp.action('${var}')"` inside template strings, as nested single/double quotes collapse or collide across compiler template strings.
2. **Use Dataset Attributes**: Pass dynamic values via HTML5 `data-*` attributes and read them in the handler:
   ```html
   <button data-optid="${opt.id}" onclick="exp.checkOption(this.dataset.optid)">
   ```
3. **Zero-Argument Helpers**: For static actions, expose dedicated zero-argument methods on the runtime bus (e.g. `exp.retry()`, `exp.startLab()`, `exp.simReset()`).

### 22. Zero-Dependency Headless Chrome CDP Verification Pattern
For offline, local, and air-gapped environments:
1. Standardize on Node.js native `WebSocket` (Node v22+) connecting directly to Chrome's `--remote-debugging-port`.
2. Do not require Puppeteer or Playwright for standard milestone verification.
3. Enforce the CDP Evaluation Scope Invariant: All scripts sent via `Runtime.evaluate` must be wrapped in an IIFE `(() => { ... })()` to prevent `Identifier has already been declared` syntax crashes across sequential evaluations.

### 23. Windows PowerShell Verbatim File Writing Invariant
When writing multi-line code files, JSON payloads, or Markdown with backticks or LaTeX symbols in Windows PowerShell:
1. Never pipe multi-line strings through `node -e "..."` or inline double quotes.
2. Always use a PowerShell verbatim here-string with single quotes (`@' ... '@`) to prevent PowerShell from stripping backticks or expanding `$variable` expressions:
   ```powershell
   @'
   <verbatim content with `backticks` and $symbols>
   '@ | Set-Content -Path '<target_file>' -Encoding UTF8
   ```

### 24. Certified Testing & Verification Commands
The following certified commands serve as operational runbook entries (note: commands are operational entries, not proof of execution by themselves):
```bash
# 1. L-Truth Ground Truth Benchmark (10-Chapter Batch Regression)
cd Aasha-AI && npm run test:ltruth

# 2. Synthetic Fault Injection Hardening (10 Failure Scenarios)
cd Aasha-AI && npx tsx tests/test_fault_injection_hardening.ts

# 3. Fork-Join Concurrency Verification (5 Scenarios)
cd Aasha-AI && npx tsx tests/test_concurrency_wiring.ts

# 4. V6 Chapter Compilation
cd Aasha-AI && npx tsx packages/v6-engine/compile_linear_equations_class8.ts
```

### 25. Bounded 2-Tier Repair Loop & Fork-Join Concurrency Invariants
1. **Bounded Repair & Quarantine**: `INITIAL_INVOCATION = 1`, `MAX_AUTONOMOUS_REPAIR_ATTEMPTS = 2`, `MAX_TOTAL_ATTEMPTS = 3`. On repair exhaustion: activate quarantine, emit structured `QuarantinePacket` (`actionRequired: "SUPER_ADMIN_INTERVENTION"`), raise `QuarantineError`, block downstream stages, and suppress memory banking (quarantined output must never enter `ContextBus` experience memory).
2. **Fork-Join Concurrency**: Eligible parallel branches are `DesignAgent`, `AssessmentAgent`, and `LLEAgent` executed via `Promise.all()`. Precondition: `AnalysisAgent` must complete first.
3. **Recursive Deep-Freeze Barrier**: Upstream analysis snapshot must be deeply cloned and recursively frozen via `deepFreeze()`. Shallow `Object.freeze()` is strictly insufficient; verified recursive freezing of all nested mutable structures is mandatory.
4. **Deterministic Join**: Stable assembly order is strictly preserved: `JOIN_ORDER = ["analysis", "design", "assessment", "lle"]`. Unordered object traversal and race-dependent assembly are prohibited.
5. **Failure & Non-Cancellation Semantics**: If any parallel branch fails, downstream synthesis halts, failure state is preserved in the quarantine packet, and unverified output is not propagated. Standard `Promise.all()` does not cancel already-running sibling branches; halting downstream synthesis is required, but sibling execution cancellation is NOT claimed.

### 26. Canonical AASHA AIOS Autonomous Orchestrator & Integration Adapters
1. **The 8 Typed Integration Contracts (`packages/adapters/contracts.ts`)**:
   - `JobContract`: Durable lifecycle state model (`CREATED` ➔ `QUEUED` ➔ `INGESTING` ➔ `STRUCTURING` ➔ `GENERATING` ➔ `COMPILING` ➔ `QA` ➔ `READY_FOR_REVIEW` ➔ `APPROVED` ➔ `DEPLOYED`, `QUARANTINED`, `FAILED`).
   - `HandoffEnvelope`: Standardized ingress payload across n8n webhook and Teacher Studio.
   - `ContextBus`: Typed immutable memory bus enforcing recursive freeze barriers across parallel agents.
   - `ArtifactManifest`: Content-addressed release certificate binding artifact hash, contract hash, IR hash, and foundation versions.
   - `DiagnosticDossier`: Minimal typed failure packet feeding targeted bounded repairs without dumping raw logs.
   - `CertificationCertificate`: Sealed HMAC-SHA256 QA seal asserting 100/100 L-Truth, 0 spoilers, and 5-viewport mobile matrices.
   - `RevisionRequest`: Structured teacher feedback spawning a new immutable $v2$ job without mutating $v1$.
   - `AASHA_PREVIEW_BRIDGE`: PostMessage protocol across sandboxed iframes (`sandbox="allow-scripts"` with opaque origin) validated via source window, cryptographic session nonces, and strict sequence checks.

2. **AIOS Control Plane Orchestrator (`packages/adapters/aios_orchestrator.ts`)**:
   - Sole process owner and execution authority running the 8-stage state machine.
   - Enforces `GENERATION_HIL = FALSE`: 100% autonomous execution from upload to review.
   - Bounded repair loop: initial attempt + $\le 2$ targeted repairs (maximum 3 total attempts) before terminal quarantine.
   - Binds directly to `ChapterContractManager`, `MathInsulator`, `IRAssembler`, and `V6Compiler`.

3. **Next.js Teacher Studio Routes (`annanth-aasha-foundationweb`)**:
   - `/studio`: Dashboard with live metrics, active jobs, and deployed chapters.
   - `/studio/ingest`: Textbook PDF dropzone embedding adapted `PdfUploader`.
   - `/studio/review/[jobId]`: Sandboxed chapter preview with side-by-side Dual-Benchmark Audit Panel.
   - `/api/studio/jobs` & `/api/studio/jobs/[jobId]`: Durable state endpoints and revision spawner.
   - `/api/artifacts/[sha256]`: Content-addressed immutable artifact server.

4. **Universal Curriculum Scope**:
   - Universal Scope: Any board (NCERT, CBSE, ICSE, State Boards), any class (K-12), any subject (Math, Science, Social Studies, English).
   - Core Law: `UNKNOWN > HALLUCINATION`. Evidence-driven capability discovery over speculative model knowledge.

### 27. Immutable Version Manager & Asynchronous Telemetry Architecture

1. **Immutable Version Manager (`packages/aios/version_manager.ts`)**:
   - **Authoritative Identity**: Content-addressed `SHA-256(content)`.
   - **Lineage Chain**: Strict sequential progression $v_1 \rightarrow v_2(\text{parent\_hash} = \text{hash}(v_1)) \rightarrow v_3(\text{parent\_hash} = \text{hash}(v_2))$.
   - **Scope-Locked 20 MB Gate**: `CHILD_HTML5_BUNDLE_MAX_BYTES = 20_971_520` (20 MB). Enforced strictly on `CHILD_HTML5_BUNDLE` distributable artifacts; does not constrain PDFs, contracts, ASTs, DBs, or server infrastructure.
   - **Local Recovery Layer**: Stored in `.scratch/versions/<artifact_id>/` with immutable `<artifact_hash>.html` and append-only `version_ledger.json`.
   - **CLI Commands (Verified)**:
     ```bash
     # Snapshot a compiled chapter to the immutable ledger
     npm run version:snapshot -- <filePath> [status]

     # Inspect version lineage, hashes, and parent links
     npm run version:list -- <artifactId>

     # Verify byte-for-byte snapshot disk integrity
     npm run version:verify -- <artifactId> <versionOrHash>

     # Safe rollback to historical version without deleting history
     npm run version:rollback -- <artifactId> <targetVersionOrHash> <destinationPath>
     ```

2. **Asynchronous Semantic Telemetry Client (`packages/v6-engine/aasha_telemetry_client.ts`)**:
   - **Core Invariant**: $\text{LEARNING\_STATE} \neq \text{TELEMETRY\_STATE}$. Telemetry failure, storage exhaustion, or network latency must NEVER block child learning, assessments, simulations, or navigation.
   - **Exact Identity Binding**: Every event binds to exact `artifact_hash`, `version`, `event_id`, `session_id`, `client_timestamp`, monotonic `sequence_number`, `event_type`, and `schema_version`.
   - **Ordering Authority**: Per-session monotonic `sequence_number` is the primary logical ordering authority against device clock drift. Timestamps (`client_timestamp`, `sync_timestamp`, `server_received_at`) are preserved as secondary metadata. Note: sequence numbers order events within a single session, but do not solve cross-device temporal synchronization.
   - **Local Event Buffering & Durability**: Asynchronous, non-blocking storage in browser-native IndexedDB (`aasha_telemetry_db`). In-memory queue is an emergency non-blocking fallback (NOT durable evidence). If storage is unavailable, continue learning, record telemetry degradation, attempt recovery, and never fabricate persistence.
   - **Performance Target**: Telemetry emission must be non-blocking and sufficiently lightweight that learning interaction is not perceptibly blocked (operational target $<2\text{ms}$).
   - **Async Batch Sync**: Transmits batches in background when connectivity is available with bounded exponential backoff; never infinite loops.
   - **Interface**:
     ```typescript
     import { AashaTelemetryClient } from './packages/v6-engine/aasha_telemetry_client';

     const telemetry = new AashaTelemetryClient({
       artifactHash: '6e1152d8...',
       version: 1,
       learnerPseudonymousId: 'anon_student_42'
     });

     // Immediate, non-blocking emission
     telemetry.recordEvent('CONCEPT_STARTED', {}, { conceptId: 'cpt:square_roots' });
     telemetry.recordEvent('ANSWER_SUBMITTED', { isCorrect: true }, { exerciseId: 'ex:1.1.q4' });
     ```

3. **Capability Broker & Local Zero-Cost Asset Substrate (`packages/aios/capability_broker.ts`)**:
   - **Resource-First Global Reuse Architecture**: Enforces `EXACT_REUSE -> PARAMETRIC_ADAPT -> COMPOSE -> LOCAL_ADAPTATION -> CERTIFIED_GENERATION -> SAFE_FALLBACK`. Always queries local `experience_registry/registry.json` before generating code. Resources are cross-chapter capabilities, not single-chapter code.
   - **Zero-Cost Bilingual Substrate**: `lookupVocabulary(terms: string[])` queries local `experience_registry/aasha_dictionary_db.json` with 0 API tokens consumed.
   - **Auto-Persistence & Build Sync**: `autoPersistMissingVocabulary()` and `syncChapterVocabulary()` automatically scan new chapter builds and append newly introduced vocabulary to the local database (`npm run vocab:sync`).
   - **Verified Repository Assets (as of 2026-09-22)**:
     - Experience Registry: 22 verified foundations (F01–F20, PhET isolated via `EXTRACT`, Escape Run, MicroSims, MathFluency).
     - Local Bilingual Dictionary: **1,365 verified Hindi conceptual definitions and phonetic guides** (expanded from chapters via automated build-sync).
     - AST Knowledge Graph: 8,035 nodes and 9,514 edges indexed across 30 languages with `tree-sitter-sql` verified.
     - Production Chapters: **10/10 chapters certified 100/100** on `qa_ltruth_benchmark.js` (0 spoilers, 0 collisions).
   - **Verification**: `npx tsx tests/test_capability_broker.ts` passes 100% across routing, foundation matching, and dictionary queries.

4. **Longitudinal Telemetry, 24-Hour Analytics & Teacher Remediation Grid**:
   - **Separation of Concerns**: Initial concept introduction (`CONCEPT_COMPLETED`) is tracked separately from repeated retrieval practice.
   - **In-Situ Local Adaptation**: Dynamic hint tier escalation ($H_1 \rightarrow H_4$), parameter variations, and drill repetition execute locally in IndexedDB without mutating the certified HTML artifact or changing its SHA-256 hash.
   - **Systemic Optimization Gate**: Multi-signal misconception clusters prompt AIOS to compile candidate $v_{N+1}$ (`parent_hash = hash(v_N)`), requiring full Dual-Benchmark QA certification and Super Admin HIL approval before deployment. Never auto-deploy.
   - **Analytics Ingestion Cadence**: Bounded batched ingestion with scheduled 24-hour consolidation plus an on-demand, rate-controlled `[Sync & Refresh Analytics]` trigger.
   - **4-Pillar Longitudinal Model**:
     - *Concept Coverage %*: Initial 1-time concept completion percentage.
     - *Practice Velocity*: Average repeat practice sessions per student over 7 and 30 days.
     - *Attempts-to-Mastery*: Average attempts needed to reach $\ge 80\%$ TEAS score.
     - *TEAS Retention Health %*: Canonical time-weighted retention score ($0.60 \times \text{HistoricalScore} + 0.40 \times \text{RecentScore}$).
   - **Actionable Remediation Suite**: Derived strictly from corroborated evidence for at-risk cohorts:
     - `[Generate Hindi Teacher Practice Plan]`: Targeted 15-minute classroom intervention guide.
     - `[Spawn Micro-Drill Pack]`: 5-question targeted offline refresher without altering core chapter.
     - `[View Misconception Breakdown]`: Diagnosed procedural error patterns ($m$ attributes).
     - Low-confidence signals remain `UNKNOWN` to avoid fabricating student weaknesses.

5. **Public Desktop Distribution & SignPath Code-Signing Runbook (`aasha-studio`)**:
   - **Dual-Track Separation**: The public transformation tool (`aasha-studio`) is strictly isolated from NGO internal telemetry, AIOS student memory, and field datasets.
   - **Zero-Rust 3-Tier Execution**:
     - *Tier 1 (End-Users)*: Cloud-built `.msi`/`.exe` binaries compiled in GitHub Actions (`windows-latest`).
     - *Tier 2 (CLI / Automation)*: Cross-platform pure Node.js package (`@aasha/cli`).
     - *Tier 3 (Local Browser Studio)*: Zero-Rust browser GUI (`aasha studio`) launching the identical visual studio in Edge/Chrome via local Node server.
   - **Free Authenticode Code-Signing via SignPath Foundation**:
     - For open-source educational releases, do not purchase costly commercial certificates.
     - Register the repository at `about.signpath.io/open-source` under AGPL-3.0.
     - Configure GitHub Secrets `SIGNPATH_API_TOKEN` and `SIGNPATH_ORGANIZATION_ID`.
     - Wire conditional submission in `.github/workflows/release-desktop.yml`:
       - When secrets exist: automatically signs `.msi` and `.exe` binaries with Authenticode.
       - When secrets are absent (interim 24–48h review period): safely falls back to standard release with clear SmartScreen bypass notes in the release body ("More info" -> "Run anyway").
   - **Zero-Key Offline Demo Showcase**:
     - Any public distribution bundle must include pre-converted offline demo chapters in `samples/demo_chapters/` (Class 8 Math, Class 8 Science, Class 6 Math, Class 1 English, Class 5 EVS).
     - First-time users must be able to launch `aasha studio` and immediately experience `<aasha-sim>` manipulatives, 4-tier progressive hints, and Hindi word-tap modals before entering any API keys.

6. **Governed Experience Registry & 3-Tier Capability Matcher**:
   - **Capability-First Matcher (`ThreeTierMatcher`)**: Capability selection matches by interaction mechanics, inputs, outputs, state model, and offline requirements—never keyword search alone.
     - *Tier 1 (Certified AASHA Component)*: Searches `experience_registry/components/` and `registry.json` for components with `status === 'CERTIFIED'`.
     - *Tier 2 (Approved Foundation Adapter)*: Adapts F01–F20 catalog entries with approved licenses (`license_status === 'APPROVED'`).
     - *Tier 3 (Fresh AASHA-Native Synthesis)*: Synthesizes novel `<aasha-sim>` Web Component adapters via `DomainSimGenerators` in `CANDIDATE` state.
   - **Governed Registry Ingestion Engine (`RegistryIngestionEngine`)**: Candidate components undergo 11 mandatory gates (`FUNCTIONAL`, `CAPABILITY_CONTRACT`, `BROWSER_RUNTIME`, `OFFLINE`, `PROVENANCE`, `LICENSE`, `ACCESSIBILITY`, `PERFORMANCE`, `SECURITY_CHILD_SAFETY`, `MAINTAINABILITY`, `AASHA_INTEGRATION`). If ANY gate is `FAIL` or `UNKNOWN`, candidate promotion is `BLOCKED`.
   - **Certification Separation Invariant**: `CHAPTER_CERTIFICATION !== COMPONENT_CERTIFICATION`. A passing chapter test does not automatically certify components inside it; component promotion requires an explicit benchmark evidence SHA-256 digest.

7. **Universal PDF File Resolver & Real Source Byte Hashing**:
   - **Real PDF Content Hashing**: PDF content hashes are calculated directly from source file bytes (`crypto.createHash('sha256').update(fs.readFileSync(pdfPath)).digest('hex')`). Placeholder/basename hashes or hardcoded strings are forbidden in production.
   - **Multi-Location Path Resolution (`resolvePdfFilePath`)**: PDF references passed via CLI or ingestion jobs are smartly resolved across absolute paths, relative paths, `content/pdfs/` directory matches, and fuzzy filename matching for dirty string inputs.
   - **Fail-Closed Protection**: If a specified PDF file cannot be located on disk in any valid path, the orchestrator fails closed with an explicit diagnostic error log to prevent unverified source hashes.

