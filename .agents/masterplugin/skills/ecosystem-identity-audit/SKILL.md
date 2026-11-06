---
name: ecosystem-identity-audit
description: Audits repository architecture and identity, proving the ecosystem is an Autonomous AI Agent System (AASHA AIOS) with multi-tier memory, multi-agent orchestration, tools, and skills, and refuting hallucinations of building/training an AI LLM.
---

# /ecosystem-identity-audit: AI Agent Ecosystem vs. LLM Building Cross-Check

Runbook for rigorously verifying and certifying that the repository is an **Autonomous AI Agent Ecosystem (AASHA AIOS)** and preventing/refuting any hallucination that the codebase is training, pre-training, or fine-tuning a Large Language Model (LLM).

## Core Identity Invariant
## Subject & Board Coverage Check

Ensures the repository declares support for all intended K‑12 subjects, boards, and classes in the experience registry.

```powershell
# List supported subjects/boards/classes from registry
Get-Content Aasha-AI/experience_registry/registry.json | ConvertFrom-Json |
  Select-Object -ExpandProperty foundations |
  ForEach-Object { $_.subject, $_.board, $_.class } | Sort-Object -Unique
```

*Expected Result*: The output should include entries for each subject (e.g., Mathematics, Science, English), each board (CBSE, ICSE, State), and each class (1‑12). Missing entries indicate the need to add a foundation entry.
1. **Definitive Build Purpose**: Despite the nominal directory name `NGO AI LLM` and remote URL `https://github.com/Anant1asha/NGO-AI-LLM.git`, this ecosystem **DOES NOT BUILD, PRE-TRAIN, OR FINE-TUNE LARGE LANGUAGE MODELS**.
2. **AI Agent Operating System (AASHA AIOS)**: The build strictly implements an **Autonomous AI Agent Ecosystem** defined by 5 formal primitives:
   - **`AGENT`**: 7 specialized pipeline agents (`IngestAgent`, `AnalysisAgent`, `DesignAgent`, `AssessmentAgent`, `LLEAgent`, `QAAgent`, `BrowserTesterAgent` in `agents.json`).
   - **`MEMORY`**: Multi-tier persistent memory (Serena MCP local memory, Mem0 episodic store, SQLite Knowledge Graph, AST Codebase Graph).
   - **`TOOL`**: Deterministic execution engines (PyMuPDF extraction, LaTeX math insulator, KaTeX, Web Audio tone generator, Headless Chrome CDP automation, Hatchable PostgreSQL).
   - **`RESOURCE`**: Curated knowledge bases (20+ Prebuilt Simulation Foundations catalog in `registry.json`, Section 24 YAML Reusable Content Contracts, NCERT syllabus catalogs, bilingual Hindi dictionary).
   - **`SKILL`**: Procedural operational packages in `.agents/skills/`.
3. **External LLM Consumption Model**: External models (`llama-3.1-8b`, `nemotron-3.5`, `claude-3-5-sonnet`, `gemini-2.0-flash-exp`) are consumed strictly as *swappable reasoning engines* via the 3-Tier Anti-Bleed LLM Router (`packages/llm-router/openrouter_client.ts`). They are intelligence utilities, NOT the system being built.

---

## Verification Workflow (5-Step Execution)

### Step 1: Pre-Flight Laya System 1 Classification
Route and evaluate the incoming prompt locally using the zero-token Laya System 1 pre-router:
```bash
python Aasha-AI/scripts/laya_task_classifier.py --text "<task_or_query>"
```
- Provides sub-millisecond Indic script isolation (<1ms) and task classification (`analysis`, `coding`, `assessment`, `design`, `lle-indic`).
- Consumes **0 LLM API tokens**.

### Step 2: Zero-Model-Training Empirical Cross-Check
Run codebase-wide checks to verify that no neural network training, tokenizer pre-training, or tensor weights exist:
```powershell
# 1. Verify zero model weights or checkpoints (*.safetensors, *.bin, *.pt, *.pth)
Get-ChildItem -Recurse -Include *.safetensors,*.pt,*.pth,*.bin -ErrorAction SilentlyContinue | Select-Object FullName

# 2. Verify zero LLM training or fine-tuning frameworks
git grep -i "torch.nn"
git grep -i "AutoModelForCausalLM"
git grep -i "Trainer("
```
*Expected Result*: Zero model training pipelines found.

### Step 3: Multi-Tier Memory & Knowledge Graph Audit
Verify that the multi-tier agent memory engines are healthy and active:
```bash
# 1. Query SQLite Knowledge Graph & Mem0 Dual-Provider Status
npx --prefix Aasha-AI tsx admin_memory_cli.ts status

# 2. Check Serena MCP Local Memories (.serena/memories/)
# In Serena MCP: list_memories, read_memory: { memory_name: "core" }
```
*Expected Result*:
- Provider Mode: `Memo0 Cloud + Local Dual-Write`
- Local Store: `HEALTHY`
- Knowledge Graph: Active concept nodes and relational edges (`aasha_operational.db`)
- Serena Memory: `core` and `conventions` affirm AI Agent Ecosystem identity.

### Step 4: Multi-Agent Orchestration & Tool Registry Verification
Verify the 7 canonical pipeline agents and the 20+ simulation foundations:
```powershell
# 1. Verify Canonical Multi-Agent Registry (agents.json)
Get-Content Aasha-AI/agents.json | ConvertFrom-Json | Select-Object -ExpandProperty agents | Format-Table id, name, type, responsibility

# 2. Verify Prebuilt Simulation Foundations (experience_registry/registry.json)
Get-Content Aasha-AI/experience_registry/registry.json | ConvertFrom-Json | Select-Object -ExpandProperty foundations | Measure-Object
```

### Step 5: Truth-Seeking Certification & Reporting
Format the assessment following the 7-step Epistemic Protocol:
1. **BREAK IT DOWN**: Separate claims (nominal naming vs actual codebase architecture).
2. **SORT WHAT YOU KNOW**: Verified facts vs reasonable inferences.
3. **ANSWER WITHOUT GUESSING**: Ground all statements in direct file paths and execution outputs.
4. **CHECK YOUR WORK**: Review for bias, assumptions, and consistency.
5. **SCORE YOUR CONFIDENCE**: 0.0 to 1.0 based on empirical evidence.
6. **REVISE IF YOU ARE UNSURE**: Rethink claims if confidence < 0.8.
7. **BE HONEST ABOUT UNCERTAINTY**: State unknowns plainly.

Always structure responses into the 3-part format:
- **Answer**: The clearest, most accurate answer grounded in empirical evidence.
- **Confidence**: Score 0.0 to 1.0 with a single-line explanation.
- **Caveats**:
  - The CI badge requires a repository secret `GH_TOKEN` with write permission to update the README.
  - The cross-platform audit runner `scripts/audit_identity.mjs` is executed via `npm run audit:identity`.
