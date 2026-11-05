# AASHA AIOS — CANONICAL SIMULATION CONTRACT SPECIFICATION

**Directive ID**: `AASHA_TASK2_UNIFIED_SIMULATION_ARCHITECTURE_R2E`  
**Deliverable ID**: `AASHA_TASK2_CANONICAL_SIMULATION_CONTRACT_PROPOSAL.md`  
**Schema Version**: `1.0.0-canonical`  
**Date**: 2026-11-06  

---

## 1. Schema Overview

Every interactive simulation produced or adapted within the AASHA ecosystem must strictly conform to the `AashaCanonicalSimContract` JSON schema. This contract acts as the machine-verifiable interface between curriculum ingestion (`ingestSubagent`), simulation coordination (`simulationSubagent`), and client runtimes (`<aasha-sim>`).

```json
{
  "$schema": "https://aasha.ai/schemas/v1/canonical-simulation-contract.json",
  "id": "sim_squares_and_cubes_concept_1",
  "version": "1.0.0",
  "metadata": {
    "title": "Queen Ratnamanjuri's Lockers & Geometric Dot Grids",
    "conceptId": "concept_1",
    "chapterSlug": "squares_and_cubes",
    "grade": 8,
    "subject": "Mathematics",
    "board": "NCERT / Ganita Prakash",
    "learningObjectives": [
      "Understand square numbers as geometric area s × s",
      "Discover the odd number summation property sum(2k-1) = s^2",
      "Visualize gnomon peeling as subtractive odd borders"
    ],
    "provenance": {
      "sourceContract": "Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml",
      "foundationReuse": ["F02", "F20"],
      "license": "MIT"
    }
  },
  "mathematicalModel": {
    "modelType": "SquareGnomonModel",
    "invariants": [
      "totalArea == side * side",
      "currentGnomonUnits == 2 * activeSide - 1",
      "activeArea == activeSide * activeSide",
      "side >= 1 && side <= 10",
      "peeledLayers >= 0 && peeledLayers < side"
    ],
    "initialState": {
      "side": 5,
      "peeledLayers": 0,
      "activeSide": 5,
      "totalArea": 25,
      "activeArea": 25,
      "currentGnomonUnits": 9,
      "oddNumbersSequence": [1, 3, 5, 7, 9],
      "isPerfectSquare": true
    },
    "stateTransitionRules": {
      "setSide": {
        "parameters": { "side": "integer" },
        "range": [1, 10],
        "clamping": "enforced"
      },
      "peelGnomon": {
        "maxLayers": "side - 1"
      },
      "unpeelGnomon": {
        "minLayers": 0
      },
      "reset": {
        "target": "initialState"
      }
    }
  },
  "renderingEnvelope": {
    "primaryRenderer": "CANVAS_2D",
    "fallbackRenderer": "DOM_SVG",
    "selectionRationale": "Procedural 2D geometric visualization optimal on Canvas 2D with DOM/SVG controls.",
    "viewport": {
      "minWidthPixels": 360,
      "maxWidthPixels": 480,
      "aspectRatio": "flexible",
      "overflowX": "hidden"
    },
    "accessibility": {
      "touchTargetMinPixels": 44,
      "ariaLiveRegions": ["simReadout"],
      "keyboardOperable": true,
      "colorContrastRatio": ">= 4.5:1",
      "audioGating": "explicit_user_gesture",
      "audioMuteAvailable": true
    }
  },
  "telemetryEnvelope": {
    "standardEventName": "aasha:telemetry",
    "emittedEvents": [
      "mount",
      "side_change",
      "peel_gnomon",
      "pause",
      "resume",
      "reset",
      "destroy"
    ],
    "isolationRule": "Telemetry listeners must run inside try/catch error boundaries. Uncaught listener errors must never disrupt simulation state."
  },
  "packagingEnvelope": {
    "zeroExternalCDN": true,
    "zeroRemoteFonts": true,
    "offlineBundleCeilingBytes": 20971520,
    "maxClientScriptBytes": 122880
  }
}
```

---

## 2. Invariant Enforcement & Validation Rules

1. **Deterministic Validation**: Every contract must pass automated validation against this schema prior to script generation.
2. **Rejection of Unknown Models**: If `modelType` is not in the whitelist (`['SquareGnomonModel', 'IsometricCubeModel']`), the coordinator must fail closed with error `UNSUPPORTED_MODEL`.
3. **No LLM Mathematical Override**: The mathematical properties inside `initialState` and `invariants` cannot be modified or recomputed by LLM completions.
