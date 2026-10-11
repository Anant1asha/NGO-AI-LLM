# Full-Chapter PDF-to-Learning Workflow Design

**Status:** Proposed for founder review  
**Repository:** `Anant1asha/NGO-AI-LLM`  
**Design path:** CLI-first, using the existing AASHA pipeline and educator scorecard

## Goal

Make one complete textbook chapter PDF reproducibly transform into a source-grounded, interactive learning chapter, with verifiable coverage and teacher approval before classroom sharing. The output must represent the full chapter, not a demo or sample lesson.

## Evidence from the repository

- **FACT:** The parent repository points to `Aasha-AI` as a Git submodule entry, but has no `.gitmodules` file in the inspected `master` tree. Its pinned Aasha-AI commit contains `aasha-pipeline-with-master-json`.
- **FACT:** At that pinned commit, the pipeline describes a full-synthesis sequence that ingests a PDF, analyzes content, designs interactions, creates assessments, assembles HTML, runs QA, and writes outputs. It hashes the source PDF and records a source manifest.
- **FACT:** The parent repo's `multi-agent-tui` launches the Python pipeline and then opens an educator scorecard.
- **FACT:** The pipeline copies intermediate files to output names such as `<chapter>_pedagogy_map.json`. The TUI auditor searches only for unprefixed `pedagogy_map.json` and `assessment_suite.json`; when source exercises are missing it treats assessed count as extracted count, yielding 100%. It also accepts 90% exercise coverage.
- **FACT:** The TUI scorecard permits explicit educator sign-off, but its “Publish” wording is not evidence of an implemented classroom deployment service.
- **CONFLICT:** Some repository documents specify a 40 MB ceiling. The active AASHA control-plane specifies a 20,971,520-byte child bundle ceiling. This design keeps the stricter 20 MiB limit; changing governance is out of scope.

## Design options

1. **Strengthen the existing CLI pipeline and scorecard (recommended).** Add reproducible submodule setup, preserve full-chapter source mappings, repair fail-open audit behavior, and bind an educator decision to exact artifact hashes. This reuses the most relevant existing work and keeps the first slice bounded to one chapter workflow.
2. **Rebuild the transformation pipeline.** This could address deeper quality limits, but would discard working ingestion, synthesis, assembly, and offline chapter components before their current completeness is measured.
3. **Add a browser upload and review application now.** This may improve usability later, but adds a new interface and deployment surface before the full-chapter transformation is dependable.

## Proposed workflow

1. **Reproducible checkout and setup:** declare the repository's required submodule URLs and pins; document a clean clone, supported runtimes, dependency installation, and safe API-key configuration. One command path should reach the exact pinned pipeline code used by the TUI.
2. **Chapter intake:** accept one chapter-level PDF plus grade, subject, and curriculum metadata. Hash the PDF, validate it, and extract every page. If pages are unreadable or extraction is incomplete, stop and report the affected pages; do not fill gaps from model memory.
3. **Full-chapter mapping:** retain page and section provenance for source concepts, worked examples, figures, and exercises. Map every required learning element to one or more lesson elements, and map every source exercise to its assessment counterpart. Grouping is allowed; silent omission is not. Preserve source identifiers and page references through generation.
4. **Fail-closed audit:** compare source and output identifiers and hashes. Require complete evidence, exact exercise coverage, valid chapter schema, required interactive/visual content, offline safety, spoiler checks, and the 20 MiB bundle limit. Missing evidence, duplicate IDs, unmapped content, or unresolved extraction errors block review approval; no fallback may report success when evidence is absent.
5. **Teacher review:** show the complete generated lesson, QA results, and source-to-lesson coverage map. Require an explicit review action after preview. Save a review record bound to the source PDF hash and generated artifact hash. Any edited artifact requires a new review.
6. **Classroom-ready handoff:** keep generated content in a review-pending location until approval. After approval, mark/copy the exact reviewed artifact as ready for classroom sharing. This workflow does not deploy it to a school or distribute it automatically.

## Reuse strategy

- Reuse the existing full-synthesis pipeline, standalone chapter runtime/design, and teacher scorecard as the vertical-slice foundation.
- Reuse existing visual interaction examples and registry candidates only after checking their provenance, license, and offline behavior; do not treat a harvested example as certified merely because it exists in the repo.
- Reuse the chapter/content schema and assessment safeguards, including source exercise IDs, misconception explanations, and zero-spoiler checks. Extend contracts only where needed to carry source page and coverage identifiers through to teacher review.
- Do not replace the pipeline or invent a new learning contract before measuring the coverage failures in the current path.

## Scope and constraints

- First delivery is CLI-based; a browser upload UI is deferred.
- Process one complete chapter PDF per run. Do not limit the generated student lesson to a demo, preview, or selected excerpt.
- Keep child-facing artifacts offline-first and below 20,971,520 bytes.
- Keep TEAS and existing learning authorities intact. Do not alter student telemetry, add learner accounts, or infer missing textbook content.
- Use only source material with a lawful basis for the intended processing and distribution. Keep API credentials outside tracked files.
- This design does not assert that the current pipeline already meets full-chapter coverage; implementing and verifying that is the work.

## Acceptance criteria

- A clean checkout can initialize the pinned pipeline and run the documented CLI workflow without relying on an undocumented local folder.
- The run produces a full chapter artifact and a source-to-lesson manifest with stable IDs and page references.
- A source fixture with all mappings passes. Fixtures with a missing page element, dropped/duplicate exercise, missing intermediate file, hash mismatch, unreadable page, or oversized bundle block approval.
- The audit reads the prefixed pipeline outputs or an explicitly passed work directory; missing source evidence never passes by default.
- A teacher can preview the complete lesson and coverage map, then approve or reject. The saved review record is tied to the exact PDF and artifact hashes; changing the artifact invalidates that approval.
- No output is described as deployed or student-ready before teacher approval.
- Unit/integration validation covers the checks above. A live LLM generation run on a real chapter is separately required for end-to-end educational acceptance; it must use a named source chapter and a cost-bounded, explicitly configured provider.

## Open input for implementation

The first real chapter PDF to use for end-to-end educational acceptance has not been selected in this task. Synthetic fixtures can verify coverage enforcement, but cannot establish that the product transforms a real chapter completely. Choose/provide the chapter before claiming that final acceptance criterion is met.

## Risks and safeguards

- **Extraction gaps:** preserve page-level evidence and block on unreadable or unmapped source material.
- **Generated content looks complete but omits material:** require source-ID reconciliation, not a visual score or percentage-only proxy.
- **Approval attached to a different version:** hash the source and output at review and re-check before handoff.
- **Hidden runtime dependency:** pin and initialize the actual pipeline submodule, then document exact setup.
- **Unsupported completeness claims:** report measured coverage and unresolved items; do not label a demo or partial chapter as complete.
- **Conflicting bundle-size requirements:** follow the active 20 MiB control-plane ceiling unless governance is explicitly amended.
