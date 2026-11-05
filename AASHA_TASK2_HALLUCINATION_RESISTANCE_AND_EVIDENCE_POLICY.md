# AASHA AIOS — HALLUCINATION RESISTANCE & EVIDENCE POLICY

**Directive ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE_R2E`  
**Deliverable ID**: `AASHA_TASK2_HALLUCINATION_RESISTANCE_AND_EVIDENCE_POLICY.md`  
**Policy Standard**: Source-Grounded Deterministic Simulation Execution  
**Date**: 2026-11-06  

---

## 1. Core Operating Principle: Zero Unverifiable AI Generation

> **Mandatory Policy Rule (HRP-01)**:  
> *No generative AI model may invent, hallucinate, synthesize, or modify mathematical formulas, concept hierarchies, or assessment grading rubrics.*  
> All mathematical logic, boundary clamping, and learning state transitions are strictly governed by immutable, deterministic TypeScript/ESM code. Generative reasoning engines are consumed strictly as unprivileged text parsers bounded by rigid JSON schemas and mathematical oracles.

---

## 2. Seven Mandatory Anti-Hallucination Controls

| Control ID | Control Name | Threat Mitigated | Enforced Technical Mechanism |
|---|---|---|---|
| **AHC-01** | **Source Evidence Grounding** | AI invents non-existent concepts or pedagogical claims. | Every simulation must trace back to a verified Section 24 YAML contract or textbook PDF SHA-256 hash. If source evidence is missing, the coordinator terminates with `INSUFFICIENT_SOURCE_EVIDENCE`. |
| **AHC-02** | **Model Whitelist Gate** | AI generates novel unverified models (e.g. `Fractal3DModel`). | Coordinator enforces strict whitelist: `['SquareGnomonModel', 'IsometricCubeModel']`. Unknown models fail closed with `UNSUPPORTED_MODEL`. Silent substitution is strictly prohibited. |
| **AHC-03** | **Mathematical Oracle Verification** | AI introduces mathematical calculation drift or off-by-one errors. | Automated unit tests evaluate headless models against mathematical oracle formulas ($s^2, 2s-1, n^3$) before script synthesis. |
| **AHC-04** | **Schema Clamping & Validation** | Out-of-bounds parameters crash student devices. | All model inputs are clamped to valid ranges ($s \in [1, 10], n \in [1, 5]$). Non-integer or out-of-range values trigger `SCHEMA_VALIDATION_FAILED`. |
| **AHC-05** | **Zero-State-Write LLM Boundary** | LLM outputs directly alter learner mastery or progress. | `V6RuntimeBus` and `TEAS` engine maintain learning state. LLM responses are treated as untrusted suggestions, strictly validated before state entry. |
| **AHC-06** | **Defensive Telemetry Isolation** | Malformed telemetry payload or listener exception crashes simulation. | All `dispatchEvent(new CustomEvent('aasha:telemetry'))` calls are wrapped in defensive `try/catch` error boundaries. |
| **AHC-07** | **Provenance & License Integrity** | Embedding unlicensed or copyleft libraries into child bundles. | Build gate verifies that all simulation assets match the foundation registry (`registry.json`) under MIT or Open Standard licenses. |

---

## 3. Standardized Error Taxonomy

When a simulation request violates hallucination resistance controls, the subagent must fail closed and emit one of the following structured error payloads:

```json
{
  "success": false,
  "error": {
    "code": "UNSUPPORTED_MODEL",
    "category": "VALIDATION_FAILURE",
    "message": "The requested model 'Unknown3DModel' is not in the canonical mathematical oracle whitelist.",
    "timestamp": 1793932800000,
    "context": {
      "requestedModel": "Unknown3DModel",
      "allowedModels": ["SquareGnomonModel", "IsometricCubeModel"]
    }
  }
}
```

### Full Category Register:
1. `INSUFFICIENT_SOURCE_EVIDENCE`: Missing curriculum contract or textbook grounding.
2. `UNSUPPORTED_MODEL`: Requested mathematical model not implemented or unverified.
3. `SCHEMA_VALIDATION_FAILED`: Parameter values outside bounded operational ranges.
4. `MATHEMATICAL_INVARIANT_FAILED`: Oracle check failed mathematical formula match.
5. `RENDERER_UNAVAILABLE`: Live browser lacks required rendering context (e.g. WebGL disabled) without Canvas 2D fallback.
6. `PROVENANCE_UNVERIFIED`: Asset license or provenance check failed.
7. `TEACHER_VALIDATION_REQUIRED`: Simulation requires explicit teacher sign-off before classroom deployment.

---

## 4. Policy Compliance Invariant

This policy applies universally across all subagents, compilers, and client runtimes. Any simulation failing automated validation against this policy is blocked from release staging and will not be packaged into pilot distribution bundles.
