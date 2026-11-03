# Startup Specification: Annanth Aasha Learning & Impact Ecosystem (AASHA AIOS)

## 1. Executive Summary & Vision
**Annanth Aasha Learning Ecosystem** is an offline-first, autonomous AI agent platform designed to democratize high-impact K-12 STEM education. By transforming traditional static textbook curricula (NCERT, state boards, and international standards) into deeply engaging, gamified, and interactive digital experiences, AASHA bridges the educational divide for students regardless of internet availability or hardware constraints.

The long-term vision is an **Autonomous AI Educational Operating System (AIOS)** that empowers educators, NGOs, and students with self-adaptive pedagogical modules, verifiable learning telemetry, and localized vernacular support.

---

## 2. Current MVP Phase Focus: Autonomous Learning & Gamified Assessment Tool
For the MVP stage, the platform is laser-focused on:
- **Autonomous Multi-Subagent Builder**: An intelligent AI tool that orchestrates specialized subagents to generate complete, standalone, offline HTML5 learning and assessment experiences.
- **Action-Based Gamification (Kriyātmaka Bodha)**: Moving away from passive video and rote memorization to active discovery—interactive manipulatives, procedural Canvas/WebGL simulations, step-by-step physical puzzles, and gamified mastery ladders.
- **3-Tier Scaffolded Assessment with Anti-Spoiler Diagnostics**:
  - **Tier 1 (Warm-Up)**: Foundational comprehension, pattern recognition, and tactile interaction.
  - **Tier 2 (Deep Dive)**: Problem-solving, procedural application, and multi-step deduction.
  - **Tier 3 (Boss Challenge)**: Synthesis, gamified puzzles, and real-world scenario mastery.
  - **4-Tier Progressive Hints**: Hook ($H_1$), Visual Anchor ($H_2$), Elimination Strategy ($H_3$), and Procedural Step ($H_4$).
  - **Anti-Spoiler Misconception Explanations**: Diagnostic feedback targeting wrong options without leaking the correct answer.
- **Zero-CDN Offline Portability**: Single-file HTML5 delivery (<20 MB) running smoothly in any web browser without internet access, external fonts, or CDN dependencies.

---

## 3. Autonomous Multi-Subagent Architecture
The tool employs a collaborative multi-subagent hierarchy:

```
                  ┌──────────────────────────────────────────────┐
                  │          AASHA Master Orchestrator           │
                  │ (Coordination, State Bus, Memory & Telemetry)│
                  └───────┬──────────────────────────────┬───────┘
                          │                              │
        ┌─────────────────┴───────────────┐              │
        ▼                                 ▼              ▼
┌──────────────┐                 ┌──────────────┐ ┌──────────────┐
│ Ingest &     │                 │ Simulation & │ │ Gamified     │
│ Analysis     │                 │ Creative     │ │ Assessment   │
│ Subagent     │                 │ Engine       │ │ Subagent     │
│ (Curriculum, │                 │ (WebGL/2D,   │ │ (3-Tiers,    │
│ Concepts)    │                 │ F01-F20)     │ │ Hints, L-QA) │
└───────┬──────┘                 └───────┬──────┘ └──────┬───────┘
        │                                │               │
        └─────────────────┬──────────────┴───────────────┘
                          ▼
        ┌──────────────────────────────────────────────┐
        │ Bilingual Indic & Audio Subagent (LLE)        │
        │ - Math Insulator (__AASHA_MATH_X__)          │
        │ - Inlined Vocabulary & Phonics Audio         │
        └──────────────────────┬───────────────────────┘
                               ▼
        ┌──────────────────────────────────────────────┐
        │ Quality, Ergonomics & Chrome CDP Auditor     │
        │ - >=44px Touch Targets, Zero Console Errors  │
        │ - Mobile Viewport Clamping (16:9, 20:9)      │
        └──────────────────────────────────────────────┘
```

### Component Capabilities:
1. **Memory**: Serena local persistent memory, Mem0 episodic cache, SQLite knowledge graph.
2. **Skills**: Curated runbooks (`laya-cadence`, `universal-sim-engine`, `aasha-prompt-compiler`, `anti-bleed`).
3. **Curated Resources**: F01–F20 Foundation Catalog (PhET cleanroom, KingsMath, MicroSims, Physics Notebook).
4. **Plugins & MCP**: Chrome CDP automation, Playwright, Filesystem, Context7.
5. **Creative Freedom**: Generates procedural WebGL, HTML5 Canvas 2D, Web Audio API sound synthesis, and particle FX without runtime restrictions.

---

## 4. Interactive Startup Clarifications & Feedback
*(This section records the iterative inputs and decisions provided by the founder across 4 sequential questions.)*

### Q1: Primary Target Learner & Environment Focus
- **Question**: Which learner group and deployment environment should the MVP optimize for first?
- **Status**: Completed
- **Recorded Answer**: **Unified Hybrid (Mobile + Desktop)** — Fluid responsive layout that clamps smoothly across budget mobile viewports (360x640 to 412x915) with minimum 44x44px touch targets, and scales seamlessly up to 1080p desktop/lab screens.

### Q2: Interactive Simulation & Visual Tech Stack
- **Question**: What simulation rendering approach should be prioritized for chapter manipulatives?
- **Status**: Completed
- **Recorded Answer**: **Adaptive Hybrid with All Rich Languages and Tools** — Prioritize an adaptive hybrid pipeline leveraging Canvas 2D, WebGL/Three.js, SVG, KaTeX, and all rich languages/tools necessary to dynamically generate the final interactive learning and gamified assessment as a 100% self-contained offline HTML file.

### Q3: Gamification & Reward Mechanics
- **Question**: How should student progress and gamification be structured in the modules?
- **Status**: Completed
- **Recorded Answer**: **Adaptive Hybrid Approach** — Combines arcade reward feedback (XP, streaks, particle confetti FX, procedural audio chimes), narrative contextual hooks, and stress-free mastery progression (4-tier hints without penalty) so each student experiences motivating, tailored positive reinforcement.

### Q4: Content Pipeline & Ingestion Source
- **Question**: What primary source material format should the agent ingest for initial module creation?
- **Status**: Completed
- **Recorded Answer**: **Adaptive Hybrid Orchestration into Unified Pipeline** — Ingest across multiple modalities (raw textbook PDFs, structured YAML/JSON contracts, and natural language curriculum specifications) unified through an efficient, high-impact pipeline that guarantees proven build quality, zero external dependencies, and rigorous pedagogical fidelity.

---

## 5. MVP Synthesis & Execution Blueprint
Based on the founder's guided inputs, the **AASHA Autonomous Learning & Gamified Assessment Agent** operates with the following verified parameters:
- **Target Deployment**: Unified Hybrid (Mobile-first with >=44px touch ergonomics, scaling seamlessly to desktop/smartboard labs).
- **Visual Engine**: Adaptive Hybrid (Canvas 2D, Three.js WebGL, SVG, KaTeX typography, F01–F20 foundation reuse) producing a single, self-contained offline HTML5 bundle (strictly $\le 20,971,520\text{ bytes / 20 MiB}$).
- **Gamification Mechanics**: Adaptive Hybrid (XP/streak telemetry, particle confetti celebration, procedural Web Audio chimes, 4-tier hints without penalty, and diagnostic anti-spoiler feedback).
- **Content Ingestion**: Multi-modal Adaptive Orchestration (PDFs + YAML contracts + AI author prompts) unified into validated, zero-leak offline learning modules.

---

## 6. Companion Specifications & Bundle Authority

This startup brief is formally supported by the following companion architecture and planning specifications:
- **Principal Autonomous Build Agent Specification**: [`agent-startup-spec.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/agent-startup-spec.md)
- **Unified MVP Plan & Authority Register**: [`output/UNIFIED_MVP_PLAN.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/output/UNIFIED_MVP_PLAN.md)
- **Agent Registry & Boundary Governance**: [`output/AGENT_REGISTRY_AND_BOUNDARIES.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/output/AGENT_REGISTRY_AND_BOUNDARIES.md)
- **Antigravity Workspace Subagent Definitions**: [`.agents/agents/`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/.agents/agents/)
- **Installation & Verification Runbook**: [`INSTALLATION.md`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/INSTALLATION.md)


