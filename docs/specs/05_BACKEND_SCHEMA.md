# AASHA AIOS — Backend Schema & Contract Specification
**Document Identifier:** `AASHA-SPEC-05-BACKEND-SCHEMA`  
**Classification:** Canonical Data Contract Specification  
**Version:** 2.0.0 (Unified Ecosystem Release)  
**Lifecycle Status:** APPROVED / LEVEL 1 SPECIFICATION  

---

## 1. Section 24 Reusable Content Contract (`contract.yaml`)

Every chapter compiled in AASHA is governed by a Section 24 YAML contract created before any code generation:

```yaml
schema_version: "2.4.0"
metadata:
  subject: "Physics"
  class_level: 8
  chapter_number: 11
  topic_title: "Force and Pressure"
  source_pdf:
    filename: "ncert_physics_class8_ch11.pdf"
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    page_range: [128, 142]

foundation_binding:
  foundation_id: "F04_PHET_SPRING"
  matched_component: "AVR-P317-parameterized-spring"
  adapter_class: "ParameterizedSpringAdapter"
  reuse_strategy: "EXTRACT"  # EXTRACT / INSPIRE / NATIVE

pedagogical_flow:
  phenomenon_hook:
    english: "Why does a mattress compress more when you stand on it than when you lie down?"
    hindi_definition_id: "def:pressure_concept"
  simulation_config:
    interactive_parameters:
      - name: "force"
        unit: "N"
        min: 1
        max: 50
        default: 10
      - name: "contact_area"
        unit: "m²"
        min: 0.1
        max: 2.0
        default: 1.0

exercises:
  tier_1_warmup:
    - id: "ex:11.1.w1"
      question: "What is the SI unit of pressure?"
      options:
        - text: "Pascal (N/m²)"
          is_correct: true
        - text: "Newton (N)"
          is_correct: false
          m: "Confusing force itself with force applied per unit area"
        - text: "Joule (J)"
          is_correct: false
          m: "Selecting energy unit instead of the force-to-area ratio"
      hints:
        h1: "Think about the formula: Force divided by Area."
        h2: "Force is measured in Newtons and area in square meters."
        h3: "Combine the units: N / m²."
        h4: "This combination is named after a French scientist."

  tier_2_deep_dive:
    - id: "ex:11.2.d1"
      question: "If a force of 40 N is distributed over an area of 2 m², what is the pressure?"
      options:
        - text: "20 Pa"
          is_correct: true
        - text: "80 Pa"
          is_correct: false
          m: "Multiplying force by area instead of applying the division formula"
        - text: "0.05 Pa"
          is_correct: false
          m: "Dividing area by force instead of force by area"
      hints:
        h1: "Look at the formula: P = F / A."
        h2: "F = 40 N and A = 2 m²."
        h3: "Set up the division: 40 / 2."
        h4: "Divide 40 into 2 equal parts."

  tier_3_boss:
    - id: "ex:11.3.b1"
      question: "Why do porter's turbans help when carrying heavy loads on their heads?"
      options:
        - text: "Increases contact area, reducing pressure on the skull"
          is_correct: true
        - text: "Reduces the actual mass of the luggage carried"
          is_correct: false
          m: "Assuming cloth can magically change the gravitational pull on the luggage"
```

---

## 2. Canonical IR Specification (`canonical_ir.json`)

Specialist agents compile normalized domain proposals into strict Canonical IR with opaque namespaces:

```json
{
  "$schema": "https://aasha.org/schemas/canonical_ir_v2.json",
  "ir_version": "2.0.0",
  "chapter_id": "ch:class8_physics_ch11",
  "namespaces": {
    "obj": "aasha:entity:object",
    "cpt": "aasha:entity:concept",
    "misc": "aasha:entity:misconception",
    "cnt": "aasha:entity:content",
    "exp": "aasha:entity:experience"
  },
  "concepts": [
    {
      "id": "cpt:pressure",
      "canonical_name": "Pressure",
      "hindi_label": "दाब",
      "formula_latex": "P = \\frac{F}{A}",
      "misconceptions": [
        "misc:force_pressure_conflation",
        "misc:area_multiplication_inversion"
      ]
    }
  ],
  "experience_binding": {
    "exp_id": "exp:spring_pressure_sim",
    "foundation_ref": "F04_PHET_SPRING",
    "component_ref": "AVR-P317-parameterized-spring",
    "web_component_tag": "aasha-sim"
  }
}
```

---

## 3. Experience Registry Schema (`experience_registry/registry.json`)

Registers both foundational open-source engines and harvested visual HTML assets:

```json
{
  "$schema": "https://aasha.org/schemas/experience_registry_v2.json",
  "version": "2.0.0",
  "foundations": [
    {
      "id": "F04",
      "name": "PhET Parameterized Physics",
      "license": "GPL-3.0",
      "isolation_strategy": "EXTRACT",
      "capabilities": ["spring_mechanics", "friction", "density", "fraction_strips"]
    }
  ],
  "components": [
    {
      "component_id": "AVR-P317-parameterized-spring",
      "foundation_id": "F04",
      "title": "Interactive Parameterized Spring Explorer",
      "source_path": "AASHA_Visual_Mass_Harvest_Phase3/resources/AVR-P317-parameterized-spring.html",
      "adapter_class": "ParameterizedSpringAdapter",
      "status": "APPROVED",
      "offline_compliant": true,
      "max_bytes": 124800,
      "telemetry_supported": ["SPRING_STRETCH", "MASS_ATTACHED", "OSCILLATION_RECORDED"]
    },
    {
      "component_id": "CINE-LAB-01-vernier-caliper",
      "foundation_id": "F02",
      "title": "Interactive Vernier Caliper Virtual Lab",
      "source_path": "external_sources/CinePhysicsHQ-Labs/vernier_caliper_lab/index.html",
      "adapter_class": "VernierCaliperAdapter",
      "status": "APPROVED",
      "offline_compliant": true,
      "max_bytes": 196400,
      "telemetry_supported": ["JAW_MOVED", "MEASUREMENT_READ", "ZERO_ERROR_ADJUSTED"]
    }
  ]
}
```

---

## 4. Telemetry Event Schema (`aasha_telemetry_db`)

```typescript
export interface AashaTelemetryEvent {
  event_id: string;              // UUID v4
  session_id: string;            // UUID v4 per active session
  sequence_number: number;       // Monotonic incremental sequence integer
  client_timestamp: number;      // Epoch milliseconds (Date.now())
  artifact_hash: string;         // SHA-256 of active chapter HTML
  event_type: 
    | 'SESSION_START'
    | 'CONCEPT_VIEWED'
    | 'WORD_TAP_OPENED'
    | 'SIM_INTERACTION'
    | 'HINT_REQUESTED'
    | 'ANSWER_SUBMITTED'
    | 'MASTERY_CALCULATED';
  payload: {
    concept_id?: string;
    word_id?: string;
    exercise_id?: string;
    hint_tier?: 'H1' | 'H2' | 'H3' | 'H4';
    is_correct?: boolean;
    distractor_selected?: string;
    teas_score?: number;
    interaction_delta?: Record<string, any>;
  };
}
```
