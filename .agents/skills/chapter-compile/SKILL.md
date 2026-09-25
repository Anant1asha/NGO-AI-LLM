---
name: chapter-compile
description: >-
  Primary AASHA Super Admin intent command to autonomously compile a textbook chapter
  into an interactive, offline HTML5 module with bilingual Hindi definitions,
  simulations, and 0-spoiler assessments.
---

# /chapter-compile: AASHA AIOS Autonomous Chapter Compiler

This is the primary user-facing intent command for generating, compiling, and testing curriculum chapters under the AASHA AIOS orchestration engine.

## Authority Invariant

```
KARAKA DECIDES ➔ PROMPT COMPILER COMPILES ➔ ROUTER ROUTES ➔ AGENT EXECUTES ➔ VALIDATOR VERIFIES
```

1. **Super Admin**: Declares intent (`/chapter-compile "<Subject>" <Class> "<ChapterName>"`).
2. **Kāraka Compiler (`/karaka-compiler`)**: Resolves constraints, identifies curriculum scope, extracts negative invariants, and emits a sealed Decision Contract.
3. **Prompt Compiler (`/aasha-prompt-compiler`)**: Injects Section 24 contract, math insulation (`__AASHA_MATH_X__`), and local memory anchors into specialized agent prompts.
4. **Model Router (`/anti-bleed`)**: Routes tasks through Tier 1 OpenRouter free models; zero paid Gemini token bleed.
5. **Specialized Agents**: Synthesizes HTML5, simulation manipulatives, and 4-tier hints ($H_1 \rightarrow H_4$).
6. **Validation & State Update**: Runs Headless Chrome CDP tests, verifies 0 console errors and `<20MB` limit, and logs state to Native SQLite.
7. **HIL Output**: Emits technical proposal and Hindi Teacher Summary (`शिक्षक के लिए सारांश`).

## Quick Start

```bash
# Example invocation syntax:
/chapter-compile "Mathematics" 8 "Rational Numbers"
/chapter-compile "Science" 7 "Acids and Bases"
```
