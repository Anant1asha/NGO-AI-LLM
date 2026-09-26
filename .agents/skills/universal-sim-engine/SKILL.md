---
name: universal-sim-engine
description: Runbook for adapting, synthesizing, and testing high-production 60 FPS multi-step game engines across all K-12 subjects and boards without toy demo regressions.
---

# Universal Multi-Step Simulation & Game Engine Runbook

## Overview
This skill operationalizes the creation, configuration, and verification of high-production educational game engines utilizing the 190+ KingsMath mechanics and 20+ open-source foundations across any school subject, grade, or board.

## Core Rules & Invariants
1. **Never Fall Back to Toy Code**:
   Chapters must NEVER render basic 1-button toy demos or static counters. Always provide dynamic 60 FPS visual interactive experiences with particle sparks, radial timers, combo streaks, and celebratory feedback.
2. **Manipulative vs. Arena Routing**:
   - Specific tactile visual manipulatives (`TenFrame`, `FractionPizza`, `NumberHunter`, `SymmetryFold`) are dispatched when their specialized keywords or parameters match.
   - All other subjects and chapters (Science, Social Studies, History, Geography, Civics, English Grammar, Commerce, Mathematics) automatically route to `MultiStepArenaEngine` (`generateMultiStepArenaSim`).
3. **Compound Subject Collision Guard**:
   Always evaluate compound subjects (e.g., "Social Science", "Social Studies") prior to single-word checks ("science") to prevent domain false matches.
4. **Dynamic 3-Tier Problem Synthesis**:
   - Step 1: Hook / Formula / Premise identification.
   - Step 2: Intermediate computation / Application step.
   - Step 3: Boss Challenge: Verification / Edge Case / Synthesis.
   - Or directly ingest custom assessment items via `initialParams.rounds`.
5. **Anti-Freeze Telemetry Clearance**:
   - Simulations must bubble `aasha:telemetry` with `isCorrect: true` upon completion.
   - Buttons must update to green `#059669` with `"Solved! Start Assessment ➜"`.
   - V6 Compiler `advance()` must gracefully transition to assessment/completion.

## Verification Checklist
Before certifying any chapter or engine update, run all 4 benchmark suites:
```powershell
node Aasha-AI/benchmarks/test_universal_multistep_engine.js
node Aasha-AI/benchmarks/test_vertical_slice_tenframe.js
node Aasha-AI/benchmarks/test_kingsmath_foundations.js
node Aasha-AI/benchmarks/qa_ltruth_benchmark.js
```
All suites must score 100/100 with 0 failures, 0 spoilers, and 0 console errors.
