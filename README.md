# AASHA AIOS — Offline-First Visual Learning Ecosystem

**AASHA AIOS** is the engineering and governance workspace for an educational technology initiative focused on transforming school textbook content into visual, interactive, bilingual learning experiences.

The project aims to help learners understand concepts rather than merely memorize answers. Its design combines textbook-grounded content, interactive simulations, scaffolded assessments, bilingual vocabulary support, and quality gates intended to prevent unsupported content and answer leakage.

> **Project status:** Active engineering workspace with specifications, agent contracts, prototypes, tests, and linked submodules. The presence of a specification or test report does not, by itself, prove that every planned feature is implemented or currently passing. Verify the relevant source and rerun tests before relying on a capability.

## Project goals

- **Start with the schoolbook.** Ground learning content and assessments in the source chapter and curriculum.
- **Explain visually.** Pair explanations with interactive visual models and simulations where appropriate.
- **Support bilingual learning.** Help learners connect English terminology with accessible Hindi meanings and pronunciation.
- **Use scaffolded practice.** Progress from foundational questions to more demanding challenges.
- **Protect learning integrity.** Detect misleading feedback, answer spoilers, and mathematical-tokenization collisions.
- **Design for constrained connectivity.** Produce standalone HTML5 learning modules that can run offline when their required assets are embedded.
- **Keep humans accountable.** Use explicit review and release gates instead of treating model output as automatically correct.

## Core learning experience

AASHA's documented pedagogical sequence is:

1. **WHAT** — introduce a question, observation, or phenomenon.
2. **WHY** — explain why the concept matters.
3. **HOW** — walk through the reasoning or method.
4. **SHOW** — demonstrate it with a visual model or simulation.
5. **TRY** — let learners practise.
6. **FEEDBACK** — diagnose the learner's misconception without giving away the answer.
7. **CONNECT** — support vocabulary and bilingual understanding.
8. **NAME** — connect the experience to formal academic terminology.

The exact sequence and content should be adapted to the chapter and validated against its source material.

## Architecture at a glance

The repository documents two broad areas:

### 1. Authoring, orchestration, and governance

The development-side architecture includes specifications and contracts for textbook extraction, concept decomposition, experience sequencing, assessment creation, bilingual vocabulary support, quality assurance, artifact verification, and human review.

The intended workflow is:

```text
Source textbook
      |
      v
Extraction and source verification
      |
      v
Concept / learning-node mapping
      |
      v
Learning sequence and assessment design
      |
      v
Interactive HTML5 compilation
      |
      v
Automated checks and adversarial review
      |
      v
Human review and controlled release
```

This is the documented target workflow, not a claim that every stage is fully automated in the current runtime.

### 2. Learner-facing learning modules

The intended delivery format is a portable HTML5 module that can bundle its HTML, CSS, JavaScript, and permitted assets. The technical specifications describe offline delivery, mobile-responsive layouts, interactive Canvas-based simulations, bilingual vocabulary interactions, and progressive assessment scaffolding.

Where offline operation is required, a module must be verified for external network requests and asset dependencies. Browser speech synthesis and other platform capabilities may vary by device and operating system.

## Learning integrity and quality principles

### Textbook-grounded content

Chapter content and assessments should be traceable to the supplied source material. When a source is missing, unreadable, or ambiguous, the pipeline should flag the gap instead of inventing material.

### Zero-spoiler feedback

Misconception feedback should help learners inspect their reasoning without exposing the answer. Automated checks can catch known leakage patterns, but they cannot guarantee the absence of every semantic spoiler; content review remains necessary.

### Mathematical and language separation

Mathematical notation and variables must be protected while bilingual text processing runs, then restored without changing the mathematical expression.

### Versioning and release control

Candidate artifacts should be validated before promotion. Failed checks should block release or send the candidate for human review rather than silently approving it.

### Offline-first delivery

Standalone modules should be tested in a disconnected environment. Do not infer offline readiness simply because a file has an HTML extension.

## Repository structure

The main repository contains the following notable paths:

| Path | Purpose |
| --- | --- |
| `.agents/` | Agent briefings, handoffs, local guidance, and skill resources |
| `.github/workflows/` | GitHub Actions workflow definitions |
| `docs/specs/` | Product, technical, application-flow, UX, schema, and implementation specifications |
| `docs/aios/` | AIOS contracts, governance documentation, and evidence records |
| `multi-agent-tui/` | TypeScript command-line interface for chapter generation and pedagogical auditing |
| `tests/` | End-to-end and adversarial test suites |
| `scripts/` | Supporting scripts |
| `AASHA_Visual_Mass_Harvest_Phase3/` | Visual resource harvesting and related materials |
| `external_sources/` | Git submodules referencing external projects |
| `Aasha-AI` | Git submodule for the principal AASHA AI workspace |
| `docs/specs/01_PRD.md` | Product requirements |
| `docs/specs/02_TRD.md` | Technical requirements |
| `docs/specs/03_APP_FLOW.md` | Application-flow specification |
| `docs/specs/04_UI_UX_BRIEF.md` | Interface and experience brief |
| `docs/specs/05_BACKEND_SCHEMA.md` | Backend schema specification |
| `docs/specs/06_IMPLEMENTATION_PLAN.md` | Implementation and certification roadmap |
| `TEST_INFRA.md` | Test design and verification infrastructure |
| `TEST_READY.md` | Recorded test-readiness report for a chapter |

This is a guide to notable paths, not a complete inventory. Specifications and reports may describe intended or historical states; check the current source and test output for runtime truth.

## Multi-agent terminal interface

The `multi-agent-tui/` package is a TypeScript command-line interface with scripts for building, starting, development, and pedagogical-auditor tests.

### Requirements

- Node.js compatible with the package and TypeScript toolchain.
- npm.
- Python and the AASHA pipeline environment for the PDF-to-chapter workflow.
- Any model-provider credentials required by the pipeline, stored locally and never committed to version control.

The package currently declares Node.js type definitions and TypeScript tooling, but the full pipeline has additional runtime requirements. Consult its own configuration and the linked AASHA workspace before setting up a machine.

### Run the terminal interface

From the repository root:

```bash
cd multi-agent-tui
npm install
npm run build
npm start
```

To run its declared pedagogical-auditor test:

```bash
npm test
```

The CLI source exposes an audit command for an existing HTML file and a generation command that calls the configured Python pipeline. The pipeline directory and Python executable must exist in the expected locations or be configured accordingly.

Examples, subject to local setup:

```bash
npm start -- audit path/to/chapter.html
npm start -- run --pdf path/to/chapter.pdf --subject math --grade 8
```

**Important:** These commands are derived from the checked-in CLI and package scripts. They are not a guarantee that the environment is installed or that end-to-end generation succeeds on a clean machine.

## Verification

Tests and reports currently present in this repository include:

- `tests/e2e_square_cube_suite.js`
- `tests/e2e_all_chapters_suite.js`
- `ltruth_benchmark_report.json`
- `TEST_INFRA.md`
- `TEST_READY.md`

The tracked readiness report records 34 assertions passing for a particular chapter test run. Treat that as historical evidence for the tested artifact and environment, not as a current whole-repository certification.

From the repository root, the recorded end-to-end test command is:

```bash
node tests/e2e_square_cube_suite.js
```

Before release, also identify the current chapter artifact and run its relevant L-Truth, browser, mathematical correctness, offline dependency, and mobile viewport checks. Record the commit, artifact hash, environment, test command, and result so that evidence can be reproduced.

## Git submodules

Some project components are referenced as Git submodules rather than ordinary directories. Clone with submodule initialization when those dependencies are required:

```bash
git clone --recurse-submodules https://github.com/Anant1asha/NGO-AI-LLM.git
cd NGO-AI-LLM
git submodule update --init --recursive
```

If you already cloned the repository without submodules, run the update command above.

## Security and responsible operation

- Never commit API keys, credentials, private student information, or unredacted sensitive documents.
- Keep secrets in local environment configuration and use a committed example file only for variable names and placeholders.
- Treat textbook extracts, external repositories, model responses, and tool outputs as untrusted inputs until validated.
- Avoid placing personally identifiable student information into prompts, logs, generated reports, or public issues.
- Review external asset licenses and attribution requirements before redistribution.
- Do not grant automated agents unrestricted write, shell, deployment, or release authority.
- Preserve provenance for source documents, generated artifacts, and quality results.
- Require human review where the governance contracts or release process specify it.

## Development principles

1. Inspect the current repository and submodule state before editing.
2. Read the relevant specification and contracts before implementation.
3. Make bounded, reviewable changes instead of broad rewrites.
4. Run tests against the exact candidate artifact.
5. Report failures and uncertainty honestly.
6. Keep specifications, implementation, and test evidence synchronized.
7. Do not treat a green test count as proof of untested properties.

## Roadmap

The repository's specification set describes work around:

- consolidating specifications and repository hygiene;
- registering and adapting reusable visual resources;
- strengthening standalone HTML5 compilation and lifecycle contracts;
- expanding automated and adversarial verification;
- requiring authenticated human approval for controlled release.

These are roadmap areas, not statements that the work is complete. Use current issues, implementation code, and reproducible test output to determine completion status.

## Contributing

Before submitting a change:

1. Explain the requirement or defect it addresses.
2. Identify the affected specification, contract, implementation, and tests.
3. Keep scope narrow and preserve existing architectural decisions unless a reviewed decision changes them.
4. Include reproducible validation results and note tests that could not be run.
5. Document changes to configuration, data formats, security boundaries, and offline behavior.

Open an issue for substantive architectural changes so the trade-offs and approval decision are recorded before implementation.

## License

No repository license was detected in the repository metadata reviewed for this draft. Unless a license file or other explicit permission applies, do not assume this code or its bundled assets may be freely reused, modified, or redistributed.

## Project

- **Repository:** https://github.com/Anant1asha/NGO-AI-LLM
- **Default branch:** `master`
- **Maintainer/owner:** [Anant1asha](https://github.com/Anant1asha)

---

*AASHA's goal is to make learning more understandable, visual, and accessible. Source grounding, reproducible verification, and human accountability are part of that goal, not optional decorations.*
