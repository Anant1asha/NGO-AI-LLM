# 17_IMPACT_METRICS.md
# Real-World Educational Impact & Learning Verification Metrics

Showing screen time or quiz clicks does NOT constitute educational impact. This framework decouples superficial activity from verifiable learning mastery, retention, and educational equity.

---

## 1. Impact Measurement Hierarchy

```
LEVEL 5: TRANSFER & REAL-WORLD COMPETENCY (Application to novel unprompted problems)
  ▲
LEVEL 4: RETENTION & DURABLE UNDERSTANDING (Recall and accuracy after 14–30 day intervals)
  ▲
LEVEL 3: FIRST-ATTEMPT DIAGNOSTIC MASTERY (Unassisted accurate conceptual execution)
  ▲
LEVEL 2: FORMATIVE ENGAGEMENT & REMEDIATION (Retry persistence through misconceptions)
  ▲
LEVEL 1: SYSTEM ACTIVITY & OFFLINE ACCESS (Chapters loaded, steps viewed, devices reached)
```

---

## 2. Canonical Impact Metric Records

### METRIC IMP-001: First-Attempt Diagnostic Accuracy (FADA)
- **METRIC ID**: IMP-001
- **CATEGORY**: Learning / Diagnostic Mastery
- **DEFINITION**: The percentage of diagnostic questions answered correctly on the very first attempt across a topic node.
- **WHY IT MATTERS**: Eliminates the confounding variable of trial-and-error guessing in gamified environments; measures true initial conceptual internalization.
- **SOURCE**: Assessment Engine Diagnostic Ledger (`tier_1_attempts`).
- **FORMULA**:
  $$\text{FADA} = \frac{\sum \text{First-Attempt Correct Answers}}{\sum \text{First-Attempt Diagnostic Questions Presented}} \times 100$$
- **COLLECTION METHOD**: Emitted locally into offline event outbox on student answer tap; synced in aggregate.
- **FREQUENCY**: Continuous per session.
- **BASELINE**: ~35% on baseline NCERT paper diagnostic tests in pilot schools.
- **TARGET**: $\ge 70\%$ post-interaction with visual manipulatives.
- **LIMITATIONS**: Does not detect if a parent or peer provided the answer.
- **PRIVACY RISK**: Zero. Emitted as anonymous aggregate ratio per cohort.

---

### METRIC IMP-002: Misconception Resolution Ratio (MRR)
- **METRIC ID**: IMP-002
- **CATEGORY**: Formative Remediation Efficiency
- **DEFINITION**: The proportion of students who, after triggering a specific misconception (`m` field feedback), successfully correct their understanding on the immediate subsequent retry.
- **WHY IT MATTERS**: Validates whether the pedagogical verbal explanations are actionable and effective, or whether students remain confused.
- **SOURCE**: Assessment Engine Attempt Sequence Log.
- **FORMULA**:
  $$\text{MRR} = \frac{\text{Count}(\text{Attempt 1} = \text{Misconception } M_i \text{ AND } \text{Attempt 2} = \text{Correct})}{\text{Count}(\text{Attempt 1} = \text{Misconception } M_i)}$$
- **TARGET**: $\ge 80\%$.
- **INTERPRETATION**: An MRR $< 50\%$ indicates that the explanation for that distractor is unclear, misleading, or poorly translated.

---

### METRIC IMP-003: Device-Level Offline Continuity (DLOC)
- **METRIC ID**: IMP-003
- **CATEGORY**: Equity / Access
- **DEFINITION**: The percentage of total learning sessions completed entirely while the device is in disconnected / airplane mode.
- **WHY IT MATTERS**: Confirms the system serves rural students who have zero continuous connectivity, proving the offline-first engineering premise.
- **FORMULA**:
  $$\text{DLOC} = \frac{\text{Sessions completed with } \text{navigator.onLine} = \text{false}}{\text{Total Completed Sessions}} \times 100$$
- **TARGET**: $\ge 85\%$ in rural school deployments.
- **PRIVACY RISK**: Zero (boolean state flag attached to aggregate sync batch).

---

### METRIC IMP-004: Pipeline Unit Cost per Chapter (PUCC)
- **METRIC ID**: IMP-004
- **CATEGORY**: Program Sustainability / Operational Scale
- **DEFINITION**: Total LLM API and compute expenditure required to transform one complete textbook chapter PDF into a verified standalone HTML chapter.
- **SOURCE**: Pipeline orchestrator token ledger (`jobs/job_manifest.json`).
- **FORMULA**:
  $$\text{PUCC} = \sum (\text{Prompt Tokens} \times \text{Rate}_{\text{in}}) + \sum (\text{Completion Tokens} \times \text{Rate}_{\text{out}})$$
- **TARGET**: $< \$0.50$ per chapter.
- **CURRENT STATUS**: Verified at ~\$0.18–\$0.32 using OpenRouter auto/free and Gemini Flash tiers.
