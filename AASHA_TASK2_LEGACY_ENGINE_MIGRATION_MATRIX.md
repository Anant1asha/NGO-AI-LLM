# AASHA AIOS — LEGACY ENGINE MIGRATION & COMPATIBILITY MATRIX

**Directive ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE_R2E`  
**Deliverable ID**: `AASHA_TASK2_LEGACY_ENGINE_MIGRATION_MATRIX.md`  
**Date**: 2026-11-06  

---

## 1. Executive Summary & Migration Principles

This matrix governs the relationship between the legacy simulation engine (`Aasha-AI/packages/adapters/domain_sim_generators.ts`), the compiler consumer (`Aasha-AI/packages/v6-engine/v6_compiler.ts`), and the canonical Task 2 simulation engine (`packages/aasha-agent-builder/src/simulation_subagent.mjs`).

### Core Migration Principles:
1. **Zero Premature Deletion**: Legacy generators will NOT be deleted or mutated while existing chapter builds rely on them.
2. **Mathematical Centralization**: All new or updated chapters must draw mathematical logic strictly from the canonical headless models in `simulation_subagent.mjs`.
3. **Bridge Compatibility**: A backward-compatible adapter interface (`UnifiedSimCompatibilityBridge`) will allow the V6 Compiler to seamlessly consume canonical `<aasha-sim>` Web Component scripts without breaking legacy iframe embeds.

---

## 2. Legacy Consumer & File Dependency Mapping

| File Path | Role | Consumed By | Current Simulation Generation Method | Planned Migration Path |
|---|---|---|---|---|
| `Aasha-AI/packages/adapters/domain_sim_generators.ts` | Legacy simulation templates | `Aasha-AI/packages/v6-engine/v6_compiler.ts` (lines 154–168) | `DomainSimGenerators.generateSimScript(config)` and `generateHtmlResourceAdapterScript(config)` | **PHASE 1**: Retain untouched for legacy chapters.<br>**PHASE 2**: Update `v6_compiler.ts` to query canonical `simulationSubagent` first. |
| `Aasha-AI/packages/v6-engine/v6_compiler.ts` | Core offline HTML5 compiler | Build scripts (`npm run chapter:compile`) | Embeds `<aasha-sim>` custom element and inlines script from `domain_sim_generators.ts` | Update line 154 to support direct injection of scripts synthesized by `simulationSubagent`. |
| `Aasha-AI/chapters/build_square_cube_chapter.js` | Class 8 Chapter builder | Independent chapter compilation | Inlines `drawSquareGridSim` and `drawIsoCubeSim` from chapter v6 | Preserved as authoritative reference fixture. |

---

## 3. UnifiedSimCompatibilityBridge Specification

To allow `v6_compiler.ts` to consume canonical Task 2 simulation scripts without breaking backward compatibility:

```typescript
/**
 * Compatibility bridge enabling V6Compiler to consume canonical simulationSubagent
 * while preserving fallback to DomainSimGenerators for legacy topics.
 */
export async function resolveSimulationScriptForV6(config: {
  chapterSlug: string;
  grade: number;
  subject: string;
  topic: string;
  conceptId?: string;
}): Promise<string> {
  // 1. Check if canonical simulationSubagent supports this topic
  if (config.chapterSlug.includes('square') || config.chapterSlug.includes('cube')) {
    const simResult = await simulationSubagent({
      contractData: {
        chapter_meta: { slug: config.chapterSlug, class: config.grade },
        curriculum_intent: {
          core_concepts: [{ id: config.conceptId || 'concept_1', title: config.topic }]
        }
      }
    });
    if (simResult.success && simResult.clientScript) {
      return simResult.clientScript;
    }
  }

  // 2. Safe Fallback to legacy generator for unmigrated topics
  return DomainSimGenerators.generateSimScript({
    subject: config.subject,
    topic: config.topic,
    topicSlug: config.chapterSlug,
    grade: config.grade
  });
}
```

---

## 4. Rollback and Risk Mitigation Strategy

- **Risk**: A change in `simulation_subagent.mjs` breaks existing V6 HTML5 bundle generation.
- **Mitigation**: The bridge defaults to `DomainSimGenerators` if `simulationSubagent` fails or encounters an unsupported model.
- **Verification**: Run `npm --prefix Aasha-AI test` to verify that existing chapter builds pass regression fixtures.
