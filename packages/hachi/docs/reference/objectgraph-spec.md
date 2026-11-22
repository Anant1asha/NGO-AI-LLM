# ObjectGraph (.og) — The Token-Efficient Agent File System

> **A complete specification, design rationale, gap analysis, rich format reference, transpiler architecture, and OG Reader implementation guide.**

| Field | Value |
|---|---|
| Version | 1.0.0 — Initial Specification |
| Status | Draft for Review |
| Classification | Technical Whitepaper + Implementation Guide |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem: Why Markdown Fails Agents](#2-the-problem-why-markdown-fails-agents)
   - 2.1 [How Agents Use Files Today](#21-how-agents-use-files-today)
   - 2.2 [The Token Waste Problem — Quantified](#22-the-token-waste-problem--quantified)
   - 2.3 [Structural Limitations of Markdown](#23-structural-limitations-of-markdown)
   - 2.4 [The 8 Critical Gaps](#24-the-8-critical-gaps)
3. [Introducing ObjectGraph (.og)](#3-introducing-ObjectGraph-og)
   - 3.1 [Core Philosophy](#31-core-philosophy)
   - 3.2 [Design Principles](#32-design-principles)
   - 3.3 [The 3-Pass Reading Model](#33-the-3-pass-reading-model)
4. [The .og Rich Format Specification](#4-the-og-rich-format-specification)
   - 4.1 [File-Level Tags](#41-file-level-tags)
   - 4.2 [Node Container Tags](#42-node-container-tags)
   - 4.3 [Content-Type Tags](#43-content-type-tags)
   - 4.4 [Navigation Tags](#44-navigation-tags)
   - 4.5 [Agent Behaviour Tags](#45-agent-behaviour-tags)
   - 4.6 [Complete Tag Reference](#46-complete-tag-reference)
5. [Solving All 8 Gaps](#5-solving-all-8-gaps)
   - 5.1 [Gap 1: Query-Aware Partial Loading](#51-gap-1-no-query-aware-partial-loading)
   - 5.2 [Gap 2: Compression Layer](#52-gap-2-no-compression-layer-for-llms)
   - 5.3 [Gap 3: Confidence & Staleness Signals](#53-gap-3-no-confidence-or-staleness-signals)
   - 5.4 [Gap 4: Session-Aware Skip Hints](#54-gap-4-no-memory-of-what-the-agent-already-knows)
   - 5.5 [Gap 5: Diff-Loading for Updates](#55-gap-5-no-diff-loading-for-updated-files)
   - 5.6 [Gap 6: Inter-Agent Role Scoping](#56-gap-6-no-inter-agent-communication-format)
   - 5.7 [Gap 7: Executable Assertions](#57-gap-7-no-executable-assertions)
   - 5.8 [Gap 8: Progressive Disclosure Architecture](#58-gap-8-progressive-disclosure-architecture)
6. [Token Efficiency Analysis](#6-token-efficiency-analysis)
   - 6.1 [Baseline vs ObjectGraph Comparison](#61-baseline-vs-ObjectGraph-comparison)
   - 6.2 [The 3-Pass Cost Model](#62-the-3-pass-cost-model)
   - 6.3 [Real-World Benchmark](#63-real-world-benchmark-scenario)
7. [The Transpiler: MD → OG](#7-the-transpiler-md--og)
   - 7.1 [Architecture Overview](#71-architecture-overview)
   - 7.2 [Stage 1: Rule-Based Structural Extraction](#72-stage-1-rule-based-structural-extraction)
   - 7.3 [Stage 2: LLM Metadata Generation](#73-stage-2-llm-metadata-generation)
   - 7.4 [Stage 3: Verification Pass](#74-stage-3-verification-pass)
   - 7.5 [Full Transpiler Orchestrator](#75-full-transpiler-orchestrator)
8. [The OG Reader](#8-the-og-reader)
   - 8.1 [Architecture](#81-architecture)
   - 8.2 [Full OG Reader Implementation](#82-full-og-reader-implementation)
   - 8.3 [MCP Tool Wrapper](#83-mcp-tool-wrapper)
9. [Agent Writing .og Files Natively](#9-agent-writing-og-files-natively)
   - 9.1 [System Prompt Rules](#91-system-prompt-rules-for-agents)
   - 9.2 [Quality Rubric for Dense Blocks](#92-quality-rubric-for-dense-blocks)
10. [Adoption Strategy](#10-adoption-strategy)
    - 10.1 [Markdown-Like Syntax](#101-markdown-like-syntax--low-migration-effort)
    - 10.2 [Migration Path](#102-migration-path)
    - 10.3 [Framework Integration](#103-framework-integration-priority)
11. [Complete .og File Example](#11-complete-og-file-example)
12. [Conclusion & Future Work](#12-conclusion--future-work)

---

## 1. Executive Summary

Large Language Model agents and multi-agent systems increasingly depend on massive skill files, complex knowledge bases, and enterprise configuration documents. While Markdown serves human readers well, it is fundamentally misaligned with autonomous agentic reading. Every time an agent reads a skill file, it reads the **entire file** — regardless of how much of it is relevant. For a massive 100,000-token enterprise runbook, this creates severe context window bloat, catastrophic token costs, and compounding history penalties over multi-turn workflows.

**ObjectGraph (.og)** is a true **Agentic File System**. It is a file format and query protocol designed specifically for autonomous agents to navigate massive scale knowledge. It uses a familiar, Markdown-like syntax and adds a rich 4-dimensional semantic layer of structured tags that enable O(1) query-routing, dependency traversal (edges), executable programmatic assertions, role-based access control (RBAC), and session memory.
Together, these properties prevent context compounding and let an agent load only the nodes a task needs instead of the whole file, turning static text into an Executable Runbook. (For a reproducible measurement on the bundled skills, see [`tests/test_og_benchmark.py`](tests/test_og_benchmark.py), CI-enforced at ≥80% savings.)

| Property | Detail |
|---|---|
| **Problem** | Agents must absorb massive Markdown files entirely, causing context compounding bloat |
| **Solution** | ObjectGraph (.og) — structured, queryable, agent-native file format |
| **Scale Target** | Enterprise documentation, massive mono-repos, complex operational runbooks |
| **Token Savings** | Loads only the nodes a task needs instead of the whole file — reproducible benchmark in [`tests/test_og_benchmark.py`](tests/test_og_benchmark.py) (CI-enforced ≥80%) |
| **Compatibility** | Markdown-like syntax — skills stay human-readable and are low-effort to author and port |
| **Capabilities** | Executable assertions, edge traversal, RBAC filtering, staleness signals |
| **Tooling** | Transpiler (MD→OG) + OG Engine (Native LLM Tool Calling) |

---

## 2. The Problem: Why Markdown Fails Agents

### 2.1 How Agents Use Files Today

Modern AI agents — whether built on LangChain, CrewAI, AutoGen, or raw Claude tool use — interact with skill and knowledge files through a simple read-entire-file pattern. When an agent is instructed to "use the deployment skill", the current flow is:

```python
# Typical agent file interaction today
agent_instruction = "Deploy the application to production"

# Agent reads the ENTIRE skill file
content = read_file("deploy-skill.md")   # 2,400 tokens

# Agent processes everything to find relevant section
# Actual useful content for this query: ~80 tokens

# Token waste: 2,320 tokens (96.7% wasted)
```

This pattern is not a bug — it is the **only option available with Markdown**. The format provides no mechanism for partial, query-aware loading. The agent has no choice but to read everything and filter mentally.

---

### 2.2 The Token Waste Problem at Scale

To understand the scale of waste, consider an enterprise AI agent system navigating a massive 50,000-token mono-repo standards document:

| Metric | Markdown (.md) | ObjectGraph (.og) |
|---|---|---|
| Avg file size | 50,000 tokens | 50,000 tokens (same content) |
| Tokens read per query | 50,000 (full file) | ~1,200 (index + required nodes) |
| Relevant content | ~1,000 tokens (2%) | ~1,000 tokens (85% of read) |
| Waste per read | 49,000 tokens | ~200 tokens |
| Multi-turn cost (5 loops) | ~150,000 tokens (compounding) | ~3,500 tokens |
| 10 agents × 20 queries/day | 30,000,000 tokens/day | 700,000 tokens/day |
| Monthly cost (at $3/MTok) | ~$2,700/month | ~$63/month |

> **The problem is not the file size. The problem is that the agent has no choice but to absorb the entire file into its compounding context window.**

---

### 2.3 Structural Limitations of Markdown

Markdown was designed in 2004 by John Gruber for human blog writing. It has served the web extraordinarily well. But its design goals are fundamentally misaligned with agent consumption:

| Limitation | Description |
|---|---|
| **Linear Structure** | Markdown flows top-to-bottom. There is no concept of jumping to a specific section without reading everything before it. |
| **No Node Identity** | Sections have headings but no stable machine-readable IDs. An agent cannot say "fetch node install-guide". |
| **No Semantic Content Types** | A code block, a warning, and a step-by-step guide all look the same to an agent — just text with different visual hints. |
| **No Compression Layer** | There is no mechanism for a dense summary layer. An agent reads 200 tokens of explanation to learn a 5-token fact. |
| **No Relationship Model** | Links exist but carry no typed semantics. An agent cannot traverse "what does this section depend on?" |
| **No Agent Metadata** | Confidence, staleness, scope, skip hints — none of these can be expressed in standard Markdown. |
| **No Partial Loading Protocol** | No standard way to say "read only the section about X". The entire file must be loaded. |
| **No Execution Hooks** | Markdown cannot encode "after running this step, assert the output contains Y". All validation logic lives in prompts. |

---

### 2.4 The 8 Critical Gaps

Through analysis of real-world agent systems, we identified 8 fundamental gaps in Markdown-based agent file systems. Each gap represents a capability that agents need but Markdown cannot provide:

| # | Gap | Impact |
|---|---|---|
| **G1** | No Query-Aware Partial Loading | Files must be read fully regardless of query relevance |
| **G2** | No Compression Layer for LLMs | No dense summary layer; full prose always read |
| **G3** | No Confidence or Staleness Signals | Agents cannot assess information freshness or reliability |
| **G4** | No Memory of What the Agent Already Knows | Everything re-read from scratch every session |
| **G5** | No Diff-Loading for Updated Files | Full re-read required even when only one section changed |
| **G6** | No Inter-Agent Communication Format | Same file served to all agents regardless of role |
| **G7** | No Executable Assertions | Success/failure conditions cannot be encoded in the file |
| **G8** | No Progressive Disclosure Architecture | No tiered reading model (index → dense → full) |

---

## 3. Introducing ObjectGraph (.og)

### 3.1 Core Philosophy

ObjectGraph is built on a single foundational insight that distinguishes it from every prior attempt at improving Markdown for agents:

> **"A file is not a document to be read — it is a database to be queried. But unlike a database, it needs no infrastructure, no schema migrations, no query language — just an agent that knows the 3-pass reading model."**

ObjectGraph does not ask agents to learn a new language. It extends Markdown with structured semantic blocks that are immediately understandable to any LLM from a single system prompt example. The format is designed to be **zero-shot parseable** — meaning an agent with no prior training on `.og` files can correctly read and write them from instructions alone.

---

### 3.2 Design Principles

| Principle | Description |
|---|---|
| **P1 — Markdown-Like Syntax** | A familiar Markdown-like base with added `::` semantic blocks — skills stay human-readable and low-effort to author and port. |
| **P2 — Query-First Architecture** | Files answer queries, not pages. The index comes first, content comes on demand. |
| **P3 — LLM as Traversal Engine** | The agent IS the query engine. No external infrastructure required. |
| **P4 — Semantic Content Typing** | Every content block declares what kind of content it is — code, steps, table, warning. |
| **P5 — Bounded LLM Risk** | LLM only generates navigational metadata (dense, index). Never touches actual content. |
| **P6 — Layered Compression** | Three reading depths: index (30 tokens) → dense (10 tokens/node) → full (complete content). |
| **P7 — Agent Metadata First-Class** | Confidence, staleness, scope, skip hints are native format features, not comments. |
| **P8 — Deterministic Verification** | Every converted file has a quantified accuracy score before first agent use. |

---

### 3.3 The LLM-Native Routing Architecture

The single most important architectural decision in ObjectGraph is the **LLM-Native Tool Routing**. Instead of using fuzzy algorithms to guess what an agent needs, ObjectGraph exposes two high-speed tools directly to the LLM:

| Tool | Action | Token Cost | Decision Made |
|---|---|---|---|
| **Pass 1 — `search_skill_index`** | Returns the `::index` block matching keywords | ~30 tokens | Which nodes are relevant to my task? |
| **Pass 2 — `resolve_skill_context`** | Fetches the full node content and automatically traverses `->[:requires]` dependencies | ~150–500 tokens | Execute the task |

In practice, the LLM acts as its own router. It searches the index, decides exactly which nodes it needs, and pulls only the required tokens. This reduces the average token cost per file interaction from **1,800 tokens** (full Markdown read) to approximately **200 tokens**.

---

## 4. The .og Rich Format Specification

The richness of the `.og` format is what enables accuracy during conversion and precise consumption during reading. Each tag carries specific semantic meaning that neither Markdown formatting nor plain text can express. The complete tag system is designed so that every piece of information has exactly one correct home.

---

### 4.1 File-Level Tags

File-level tags appear at the top of every `.og` file and are read during Pass 1.

#### `::meta` — File Metadata

```
::meta
  title: Python Deployment Skill
  version: 2.3.1
  author: devops-team
  created: 2024-11-01
  updated: 2025-04-15
  domain: deployment|python|devops
  scope: all              # all | orchestrator | worker | readonly
  min-agent-version: 1.0  # minimum og Reader version required
  checksum: sha256:a3f9..  # integrity verification
::end
```

Every field in `::meta` is machine-readable. The `checksum` enables verification after transfer. The `scope` field determines which agents receive this file in multi-agent systems.

---

#### `::index` — Query Routing Table

```
::index
  # node-id          | type      | scope  | conf | query-keywords
    install            | step      | all    | 0.99 | install,setup,uv,sync,dependencies,python
  configure          | step      | all    | 0.97 | config,env,environment,variables,settings
  deploy-prod        | step      | all    | 0.95 | deploy,production,release,ship,push
  deploy-staging     | step      | all    | 0.95 | staging,test,preview,sandbox
  rollback           | step      | all    | 0.93 | rollback,revert,undo,restore
  api-keys-secret    | step      | orchestrator | 0.99 | api,key,secret,vault,credentials
  troubleshoot       | step      | all    | 0.90 | error,fail,debug,broken,exception
  __changelog        | meta      | all    | 1.00 | changelog,updates,changes,new,diff
::end
```

The index is the **single most important innovation** in ObjectGraph. It is a complete routing table for the entire file — an agent reads this (~30 tokens) and immediately knows exactly which nodes to fetch without reading any other content.

---

#### `::schema` — Domain Type Definitions

```
::schema
  node-types: [concept, step, warning, example, reference, assertion, meta]
  edge-types: [requires, precedes, contains, contradicts, attributed-to]
  scope-levels: [all, orchestrator, worker, readonly, admin]
  confidence-range: [0.0, 1.0]  # 1.0 = verified, 0.0 = deprecated
::end
```

---

#### `::changelog` — Delta Loading Support

```
::node[id=__changelog type=meta]
::changelog
  2025-04-15 | added    | node[kubernetes-deploy] | New Kubernetes support
  2025-04-10 | updated  | node[install]           | Added --legacy-peer-deps flag
  2025-03-01 | deprecated | node[heroku-deploy]   | Heroku free tier removed
  2025-02-15 | added    | node[rollback]          | New rollback procedure
::end
::end
```

An agent that has previously read this file only needs to read the `__changelog` node (~30 tokens) to discover what changed, then fetch only the delta nodes. This solves **Gap 5** (Diff-Loading) at the format level.

---

### 4.2 Node Container Tags

Every piece of content in a `.og` file lives inside a node. Nodes are the fundamental unit of ObjectGraph.

```
::node[id=<unique-id> type=<node-type> confidence=<0-1> scope=<scope>
       updated=<YYYY-MM> supersedes=<old-node-id> skip-if-known=<true|false>
       entry=<true|false> depth-limit=<int> priority=<edge-type-list>]

  # Node content goes here using content-type tags

::end
```

#### Node Attribute Reference

| Attribute | Type | Description |
|---|---|---|
| `id` | string | Unique stable identifier for this node. Used for edge references and direct fetch. |
| `type` | enum | Content type: `concept` \| `step` \| `warning` \| `example` \| `reference` \| `assertion` \| `meta` |
| `confidence` | float 0–1 | Reliability score. `1.0` = verified production-tested. `0.5` = experimental. `<0.3` = deprecated. |
| `scope` | enum | Access level: `all` \| `orchestrator` \| `worker` \| `readonly` \| `admin` |
| `updated` | YYYY-MM | When this node was last verified accurate. Used for staleness detection. |
| `supersedes` | node-id | This node replaces the named older node. Reader should ignore the old one. |
| `skip-if-known` | boolean | If `true`, agent may skip this node if it has visited it this session. |
| `entry` | boolean | If `true`, this is a valid traversal entry point for this file. |
| `depth-limit` | integer | Maximum edge hops an agent should follow from this node. |

---

### 4.3 Content-Type Tags

This is where ObjectGraph is **fundamentally richer than Markdown**. Every content block inside a node declares exactly what kind of content it is. This enables agents to reason about content semantics, not just content presence.

#### `::dense`
Compressed 10–15 token keyword summary. Read in Pass 2. Generated by LLM once at creation time by compressing the `::full` block. Never generated from code or table content.

```
::dense
python3.11+|uv|sync|dependencies|project-env|.venv|uv.lock
::end
```

---

#### `::full`
Complete human-readable prose. Read in Pass 3 when dense is insufficient. Copied **verbatim** during MD→OG conversion — never paraphrased, never modified.

```
::full
# Installation
Ensure Python 3.11 or higher is installed on the target system.
Sync and manage project dependencies using uv.
::end
```

---

#### `::code[lang=X]`
Executable or technical content with language tag. Always copied verbatim. Never summarized in `::dense`. The `lang` attribute enables syntax identification.

```
::code[lang=bash]
uv sync
uv run python --version
uv run hachi --help
::end
```

---

#### `::steps`
Ordered sequential instructions. Order matters. Rendered as a numbered list. Each step is preserved exactly.

```
::steps
1. Sync project dependencies: uv sync
2. Validate Python runtime: uv run python --version
3. Validate command wiring: uv run hachi --help
::end
```

---

#### `::list`
Unordered enumerable items. Order does not matter. All items preserved verbatim.

```
::list
- Supports Python 3.11, 3.12, 3.13
- Compatible with Linux, macOS, Windows
- Requires uv >= 0.4
::end
```

---

#### `::table`
Structured data. All rows and columns preserved exactly. Never paraphrased or summarized. This is a critical accuracy requirement — table data must never be touched by LLM.

```
::table
| Flag        | Default | Description              |
|-------------|---------|--------------------------|
| --verbose   | false   | Enable debug output      |
| --timeout   | 30      | Request timeout in secs  |
| --retry     | 3       | Max retry attempts       |
::end
```

---

#### `::warning`
Critical callout. High-priority content. Agent should always read `::full` for warning nodes, even if `::dense` seems sufficient.

```
::warning
Never install packages globally. Always use a virtual environment.
Mixing system and project packages causes unresolvable dependency conflicts.
::end
```

---

#### `::note`
Informational aside. Lower priority than `::warning`. May be skipped in dense-only passes.

```
::note
On macOS with Homebrew Python, use python3 instead of python.
::end
```

---

#### `::example`
Concrete illustration of a concept. May be skipped if the concept is already known to the agent in this session.

```
::example
# Example: Installing in a CI environment
uv sync --frozen --extra dev
uv run pytest -q
::end
```

---

#### `::reference`
External link or citation. Includes URL and description.

```
::reference
    url: https://docs.astral.sh/uv/
    title: Official uv Documentation
  accessed: 2025-04
::end
```

---

#### `::assertion`
Executable validation condition. Contains pass/fail logic and routing. See Section 5.7 for full details.

---

#### `::summary`
Pre-written human summary of a long node. Faster than `::dense` for prose-heavy nodes where keyword compression loses too much meaning.

```
::summary
This node covers complete Python environment setup including uv-based dependency
sync, command execution, and reproducible lockfile workflows.
::end
```

---

### 4.4 Navigation Tags

#### `::edges` — Typed Relationship Declarations

```
::edges
  ->[:precedes]    configure          # this step comes before configure
  ->[:requires]    concept-virtualenv  # this step requires virtualenv knowledge
  <-[:used-in]     deploy-prod        # deploy-prod uses this step
  <>[:related]     troubleshoot       # bidirectional relationship
  ->[:see-also condition='query contains kubernetes'] kubernetes-deploy
::end
```

| Edge Syntax | Meaning |
|---|---|
| `->[:label]` | Directed outbound edge from this node to target |
| `<-[:label]` | Directed inbound edge — target points to this node |
| `<>[:label]` | Bidirectional edge between this node and target |
| `->[:label condition='...']` | Conditional edge — only follow if condition matches query |

**Supported edge types:** `:precedes`, `:requires`, `:contains`, `:contradicts`, `:elaborates`, `:see-also`, `:supersedes`, `:used-in`, `:attributed-to`

---

#### `::traverse` — Traversal Hints

```
::traverse
  entry: true                          # valid starting point for traversal
  depth-limit: 3                       # stop after 3 edge hops
  priority: [:precedes, :requires]     # follow these edge types first
  summarize-at: 500                    # summarize context after 500 tokens
  avoid: [:deprecated, :see-also]      # do not follow these edge types
::end
```

---

### 4.5 Agent Behaviour Tags

#### `::assertion` — Executable Validation

```
::node[id=install-verify type=assertion]
::assertion
  trigger: after[install]
  check: tool_output contains 'Successfully installed'
  check: command 'python --version' matches 'Python 3\.1[0-9]'
  on-fail: ->[:retry] install
  on-fail: ->[:escalate] troubleshoot
  on-pass: ->[:proceed] configure
  max-retries: 2
::end
::end
```

---

#### Role-Scoped Nodes — Inter-Agent Communication

```
# Orchestrator agents see the real secret path
::node[id=api-key-access type=step scope=orchestrator confidence=1.0]
::full
  Retrieve the production API key from Vault:
  vault kv get secret/prod/api-key
::end
::end

# Worker agents get a safe abstraction
::node[id=api-key-access type=step scope=worker confidence=1.0]
::full
  API keys are managed by the orchestrator.
  Request access via: get_secret('prod/api-key')
::end
::end
```

---

### 4.6 Complete Tag Reference

| Tag | Level | When LLM Reads | Pass |
|---|---|---|---|
| `::meta` | File | Always | 1 |
| `::index` | File | Always | 1 |
| `::schema` | File | On demand | 1 |
| `::node[...]` | Container | Opens block | Any |
| `::dense` | Content | Pass 2 | 2 |
| `::full` | Content | Pass 3 | 3 |
| `::code[lang=X]` | Content | When needed | 3 |
| `::steps` | Content | When needed | 3 |
| `::list` | Content | When needed | 3 |
| `::table` | Content | When needed | 3 |
| `::warning` | Content | Always (high priority) | 2+ |
| `::note` | Content | Optional | 3 |
| `::example` | Content | Optional | 3 |
| `::reference` | Content | On demand | 3 |
| `::assertion` | Behaviour | After named trigger | Runtime |
| `::edges` | Navigation | When traversing | 2 |
| `::traverse` | Navigation | At entry nodes | 1 |
| `::changelog` | Meta | On diff-load | 1 |
| `::schema-def` | Meta | When type needed | 3 |
| `::end` | Structural | Closes any block | Any |

---

## 5. Solving All 8 Gaps

This section provides detailed technical solutions for each of the 8 gaps identified in Section 2.4. Each solution is implemented at the format level — no external infrastructure or additional tooling required beyond the OG Reader.

---

### 5.1 Gap 1: No Query-Aware Partial Loading

**Problem:** Agents must read entire files even when only one section is relevant. A 2,000 token file read to answer a 40-token question wastes 1,960 tokens.

**Solution:** The `search_index` and `resolve_context` API natively supports partial loading. The agent reads the index, matches keywords, then fetches only the matching nodes along with their dependencies.

```python
# Agent query: "how do I deploy to Vercel?"
# OG Engine process:

# Turn 1: Agent calls search
index_payload = engine.search_index("skill.og", "deploy vercel")
# Returns: "Node: deploy-vercel | Keywords: deploy, vercel, production"
# Cost: ~30 tokens

# Turn 2: Agent calls resolve_context
context_payload = engine.resolve_context("skill.og", ["deploy-vercel"])
# Engine automatically traverses ->[:requires] edges (e.g. pulling env-management)
# Returns: Formatted markdown containing ONLY the vercel and env nodes.
# Cost: ~400 tokens

# Total: 430 tokens instead of 2,000 tokens
# Savings: 78.5%
```

---

### 5.2 Gap 2: No Compression Layer for LLMs

**Problem:** Markdown has no built-in compression. Agents read 200 tokens of explanation to learn a 10-token fact. There is no way to serve a dense summary to agents that already understand the domain.

**Solution:** The `::dense` block provides a compressed keyword representation of every node. For agents doing quick reasoning or routing decisions, `::dense` provides sufficient context in 10–15 tokens. Only agents needing execution details proceed to `::full`.

```
::node[id=install type=step confidence=0.99]

::dense
python3.11+|uv|sync|dependencies|project-env|.venv|uv.lock
::end

::full
# Installation
Ensure Python 3.11 or higher is installed on the target system.
Use uv to create/manage the project environment and install dependencies:

    uv sync
    uv run python --version
    uv run hachi --help

Optional: use `uv sync --frozen` in CI to enforce lockfile reproducibility.
::end

::end
```

> **Key insight:** The `::dense` block is generated by an LLM **once** at file creation time. Every subsequent read is pure text retrieval — no LLM required at read time.

---

### 5.3 Gap 3: No Confidence or Staleness Signals

**Problem:** Agents reading Markdown have no way to assess if the information is current, verified, or deprecated. A guide written in 2022 looks identical to one written yesterday. Agents may confidently follow outdated instructions.

**Solution:** Every node carries `confidence` (0.0–1.0) and `updated` (YYYY-MM) attributes. The OG Reader can filter or warn based on these values. Agents can be instructed to skip nodes with confidence below threshold or flag nodes older than N months.

```python
# In ::index — confidence is visible at Pass 1
::index
    install            | step | all | 0.99 | install,setup,uv,sync
  deploy-heroku      | step | all | 0.10 | heroku,deploy   # deprecated!
  deploy-kubernetes  | step | all | 0.97 | k8s,kubernetes,deploy
::end

# OG Reader applies confidence filtering
nodes = og_reader.query(file, query, min_confidence=0.80)
# deploy-heroku (0.10) is automatically excluded
# Agent never reads deprecated content

# Staleness detection
stale = og_reader.find_stale_nodes(file, max_age_months=6)
# Returns nodes with updated date > 6 months ago
# Agent can flag these for human review
```

---

### 5.4 Gap 4: No Memory of What the Agent Already Knows

**Problem:** In a multi-step agent workflow, the agent re-reads foundational concept nodes every time they appear in traversal, even if it visited them 3 steps ago. No mechanism exists to track visited nodes within a session.

**Solution:** The `skip-if-known=true` attribute allows the OG Reader to maintain a visited-set per session. Background concept nodes that have `skip-if-known` set are automatically skipped if the node ID appears in the session's visited-set.

```python
# Node marked as skippable once known
::node[id=concept-virtualenv type=concept skip-if-known=true priority=low]
::dense
uv|isolated|python-env|project-env|lockfile
::end
::full
A virtual environment isolates Python packages per project...
::end
::end

# OG Engine session management
session = OGSession()

# First traversal — node is read and returned
engine.resolve_context(file, ["concept-virtualenv"], session=session)
# session.visited = {"concept-virtualenv"}

# Second traversal — node is skipped
engine.resolve_context(file, ["concept-virtualenv"], session=session)
# Returns: "" (skipped — already known this session)
# Tokens saved: ~80 per skip
```

---

### 5.5 Gap 5: No Diff-Loading for Updated Files

**Problem:** When a skill file is updated, agents re-read the entire file to get the changes — even if only one section was modified. For large files updated frequently, this is extremely wasteful.

**Solution:** The `::changelog` node provides a structured diff of all changes since the file was last read. Agents that cache file metadata can read only the changelog (30 tokens) and fetch only the changed nodes, completely skipping unchanged content.

```python
# Agent caches last-read version
cache = {"skill.og": {"version": "2.2.0", "read_at": "2025-04-01"}}

# On next interaction, engine checks changelog first
delta = engine.get_delta(file, since_version="2.2.0")
# delta = {
#   "added": ["kubernetes-deploy"],
#   "updated": ["install"],    # --legacy-peer-deps flag added
#   "deprecated": ["heroku-deploy"]
# }
# Cost: 30 tokens (changelog only)

# Agent fetches only the changed nodes in a single call
engine.resolve_context(file, delta["updated"])
# Cost: ~90 tokens for 1 updated node

# Total cost of update check: 120 tokens
# vs full re-read: 1,800 tokens
# Savings: 93.3%
```

---

### 5.6 Gap 6: No Inter-Agent Communication Format

**Problem:** In multi-agent systems, orchestrators and workers need different information from the same file. A worker should not see production secrets. An orchestrator needs detailed control information. Markdown serves everyone the same content with no role awareness.

**Solution:** The `scope` attribute on nodes and the OG Reader's role-based filtering serve different views of the same file to different agent types. The `::index` also carries scope information, so agents immediately know at Pass 1 which nodes are available to their role.

```python
# Same file, different views based on RBAC

# Orchestrator Agent Call
nodes = engine.search_index(file, query, agent_role="orchestrator")
# Returns: index string containing nodes with scope=orchestrator OR scope=all
# Including: api-key-access (real vault path)

# Worker Agent Call
nodes = engine.search_index(file, query, agent_role="worker")
# Returns: index string containing ONLY nodes with scope=worker OR scope=all
# Excluding: api-key-access (scope=orchestrator)
# Including: api-key-access-summary (scope=worker) — safe abstraction
```

---

### 5.7 Gap 7: No Executable Assertions

**Problem:** Skill files describe what to do but cannot encode success criteria. Agents complete steps without knowing if they succeeded, leading to silent failures where subsequent steps execute on a broken foundation. All validation logic lives in prompts, consuming tokens on every interaction.

**Solution:** The `::assertion` node type encodes validation conditions, retry routing, and escalation paths directly in the file. The OG Reader executes assertions automatically after their trigger nodes complete.

```
::node[id=post-install-check type=assertion]
::assertion
  trigger: after[install]

  # Multiple checks — all must pass
  check: command('python --version') matches 'Python 3\.1[0-9]'
    check: command('uv run python -c "import requests"') exits 0
  check: file_exists('.venv/bin/activate')

  # Routing on outcomes
  on-pass: ->[:proceed] configure
  on-fail: ->[:retry limit=2] install
  on-fail-after-retries: ->[:escalate] troubleshoot
  on-fail-after-retries: notify[orchestrator] 'Install failed after 2 retries'

  max-retries: 2
  timeout: 30s
::end
::end
```

---

### 5.8 Gap 8: Context Window Bloat & Compounding History

**Problem:** In traditional Agentic RAG, every tool call compounds the conversation history. If an agent loops 5 times (Search -> Read -> Read -> Search), the context window bloats massively because LLM APIs are stateless. For small skill files, this multi-turn compounding overhead can cost *more* tokens than simply dumping the whole file into the prompt.

**Solution:** ObjectGraph solves Context Compounding through two distinct architectures depending on file scale:

1. **One-Shot Extraction (For Small Files < 10k tokens):**
   Instead of forcing the agent to use a `search` tool, the dense `.og` index (~150 tokens) is injected directly into the agent's System Prompt. The agent reads the index upfront and calls `resolve_context` *exactly once*. Zero compounding history.

2. **Context Isolation via Delegate Agents (For Enterprise Scale):**
   A "Router" agent (using a cheap, fast model like Haiku) gets the `search_skill_index` tool. It outputs a JSON array of `node_ids`. The orchestration system calls `resolve_context` locally and injects ONLY the final payload into an "Executor" agent (using an advanced model like Sonnet). The Executor sees zero tool-calling history, ensuring perfect, bloat-free execution.

---

## 6. Token Efficiency Analysis

> **Note:** The figures in this section are an **illustrative cost model**, not a measured benchmark. They model the 3-pass cost formula against a hypothetical file to show where the savings come from. For an actual, reproducible measurement on the bundled skills, see [`tests/test_og_benchmark.py`](tests/test_og_benchmark.py), which compares loading one node against dumping every skill into context and is CI-enforced at ≥80% savings.

### 6.1 Baseline vs ObjectGraph Comparison (Illustrative Model)

The following analysis uses a realistic skill file: 600 lines, 8 major sections, covering installation, configuration, deployment, rollback, and troubleshooting. The numbers below are an illustrative model, not a measured benchmark.

| Scenario | Markdown Tokens | ObjectGraph Tokens | Savings |
|---|---|---|---|
| Full file read | 1,840 | 1,840 (same content) | 0% (baseline) |
| Query: install guide | 1,840 | 42 (index + dense) | **97.7%** |
| Query: deploy to prod | 1,840 | 138 (index + dense + full) | **92.5%** |
| Check for updates (cached) | 1,840 | 30 (changelog only) | **98.4%** |
| 10 queries same session | 18,400 | 380 (skip-if-known) | **97.9%** |
| Worker agent (scoped) | 1,840 | 95 (filtered scope) | **94.8%** |
| Multi-agent, 5 agents | 9,200 | 475 (role-scoped each) | **94.8%** |

---

### 6.2 The 3-Pass Cost Model

The cost formula for any ObjectGraph query is:

```
Total Cost = C_index + (N_dense × C_dense) + (N_full × C_full)
```

| Variable | Value | Description |
|---|---|---|
| `C_index` | ~30 tokens (fixed) | Cost to read `::meta` + `::index` — always the same regardless of file size |
| `N_dense` | 1–3 nodes typically | Number of nodes matched by query keywords |
| `C_dense` | ~10–15 tokens/node | Cost to read one `::dense` block |
| `N_full` | 0–2 nodes typically | Number of nodes requiring full content |
| `C_full` | ~100–300 tokens/node | Cost to read one `::full` block (varies by content) |

**Example calculation for a typical install query:**
```
Total = 30 + (2 × 12) + (1 × 90)
      = 30 + 24 + 90
      = 144 tokens  (vs 1,840 full Markdown read)
      = 92.2% savings
```

---

### 6.3 Illustrative Cost Scenario

Consider a production deployment pipeline agent running 50 skill file queries per day across 5 skill files. The monthly token cost comparison below (at Claude Sonnet pricing, ~$3/MTok input) is an illustrative model, not a measured benchmark:

| Metric | Markdown | ObjectGraph | Monthly Saving |
|---|---|---|---|
| Queries/day | 50 | 50 | — |
| Avg tokens/query | 1,840 | 115 | — |
| Daily tokens | 92,000 | 5,750 | 86,250 |
| Monthly tokens | 2,760,000 | 172,500 | 2,587,500 |
| Monthly cost | $8.28 | $0.52 | **$7.76 (93.7%)** |

---

## 7. The Transpiler: MD → OG

### 7.1 Architecture Overview

The transpiler converts existing Markdown files to ObjectGraph format through a **3-stage hybrid pipeline**. The core design principle is: **LLMs never touch actual content**. They only generate navigational metadata (`::dense` and `::index` keywords). All content is copied verbatim by deterministic rule-based parsing.

```
┌─────────────────────────────────────────────────────────────┐
│                    TRANSPILER PIPELINE                      │
├──────────────────┬──────────────────┬───────────────────────┤
│  Stage 1         │  Stage 2         │  Stage 3              │
│  Rule-Based      │  LLM Metadata    │  Verification         │
│  Structural      │  Generation      │  Pass                 │
│  Extraction      │                  │                       │
├──────────────────┼──────────────────┼───────────────────────┤
│  Input: .md      │  Input: nodes    │  Input: .md + .og     │
│  Output: nodes   │  Output: dense   │  Output: accuracy     │
│                  │  + index keys    │  score + diff report  │
├──────────────────┼──────────────────┼───────────────────────┤
│  No LLM          │  1 LLM call/node │  No LLM               │
│  Zero halluc.    │  Bounded risk    │  Deterministic        │
│  Verbatim copy   │  Nav only        │  Zero false negatives │
└──────────────────┴──────────────────┴───────────────────────┘
```

---

### 7.2 Stage 1: Rule-Based Structural Extraction

Stage 1 is a pure text parser. It has no intelligence, makes no interpretations, and copies all content verbatim. Its only job is to identify content type boundaries and label them correctly.

#### Markdown → ObjectGraph Mapping Rules

| Markdown Pattern | ObjectGraph Tag | Notes |
|---|---|---|
| `# Title` | `::meta title` + entry node | Top-level heading becomes file title |
| `## Section Heading` | `::node[id=slug type=section]` | Slugified for stable ID |
| `### Subsection` | `::node[id=parent-slug type=subsection]` | Nested under parent |
| ` ```lang\ncode\n``` ` | `::code[lang=lang]` | Verbatim copy, no modification |
| `\| table \|` | `::table` | All rows/columns preserved exactly |
| `1. 2. 3.` | `::steps` | Order preserved, item text verbatim |
| `- bullet` | `::list` | All items verbatim |
| `> blockquote` | `::reference` | With source if link present |
| `**bold** phrase` | Preserved in `::full` | Visual emphasis kept as-is |
| `` `inline code` `` | Preserved in `::full` | Not extracted — stays inline |
| `[text](url)` | `::reference` if standalone | Inline links stay in `::full` |
| `---` | Node boundary signal | May indicate new section |
| Regular paragraph | `::full` | Prose content, verbatim |
| `> [!WARNING]` | `::warning` | GitHub-style callouts mapped |
| `> [!NOTE]` | `::note` | GitHub-style callouts mapped |

#### Stage 1 Python Implementation

```python
import re, hashlib
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class OGNode:
    node_id: str
    node_type: str
    content_blocks: List[dict] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    confidence: float = 0.95
    scope: str = "all"
    updated: str = ""

class Stage1Parser:
    def __init__(self):
        self.nodes = []
        self.current_node = None

    def slugify(self, text: str) -> str:
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[\s_-]+", "-", text).strip("-")

    def parse(self, md_content: str) -> List[OGNode]:
        lines = md_content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Heading → new node boundary
            if line.startswith("## "):
                self._close_node()
                title = line[3:].strip()
                self.current_node = OGNode(
                    node_id=self.slugify(title),
                    node_type="step" if "step" in title.lower() else "concept"
                )
                self.current_node.content_blocks.append(
                    {"type": "full", "content": f"# {title}\n"})

            # Code block → ::code verbatim
            elif line.startswith("```"):
                lang = line[3:].strip() or "text"
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                # VERBATIM — no modification
                self._add_block("code", "\n".join(code_lines), lang=lang)

            # Table → ::table verbatim
            elif line.startswith("|"):
                table_lines = []
                while i < len(lines) and lines[i].startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                self._add_block("table", "\n".join(table_lines))
                continue

            # Ordered list → ::steps
            elif re.match(r"^\d+\.\s", line):
                steps = []
                while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                    steps.append(lines[i])
                    i += 1
                self._add_block("steps", "\n".join(steps))
                continue

            # Bullet list → ::list
            elif line.startswith("- ") or line.startswith("* "):
                items = []
                while i < len(lines) and (lines[i].startswith("- ") or
                                          lines[i].startswith("* ")):
                    items.append(lines[i][2:])
                    i += 1
                self._add_block("list", "\n".join(items))
                continue

            # Warning callout
            elif line.startswith("> [!WARNING]"):
                warning_lines = []
                i += 1
                while i < len(lines) and lines[i].startswith("> "):
                    warning_lines.append(lines[i][2:])
                    i += 1
                self._add_block("warning", "\n".join(warning_lines))
                continue

            # Regular prose → ::full (verbatim append)
            elif line.strip() and self.current_node:
                self._append_full(line)

            i += 1

        self._close_node()
        return self.nodes

    def _add_block(self, btype, content, **kwargs):
        if self.current_node:
            block = {"type": btype, "content": content}
            block.update(kwargs)
            self.current_node.content_blocks.append(block)

    def _append_full(self, line):
        if self.current_node:
            for b in self.current_node.content_blocks:
                if b["type"] == "full":
                    b["content"] += line + "\n"
                    return
            self._add_block("full", line + "\n")

    def _close_node(self):
        if self.current_node:
            self.nodes.append(self.current_node)
            self.current_node = None
```

---

### 7.3 Stage 2: LLM Metadata Generation

Stage 2 uses exactly **one LLM API call per node** to generate the `::dense` block and index keywords. This is the only place in the pipeline where an LLM is involved. Critically, the LLM receives only the full content and is asked to produce keywords — it **never paraphrases, never summarizes for display, and never touches code or tables**.

```python
import anthropic

class Stage2LLMMetadata:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_dense(self, node: OGNode) -> tuple[str, str]:
        """Returns (dense_keywords, index_keywords)"""

        # Build content summary for LLM — ONLY prose, never code/table
        prose_only = []
        for block in node.content_blocks:
            if block["type"] in ("full",):
                prose_only.append(block["content"][:500])

        if not prose_only:
            # For code-only nodes, generate keywords from structure
            prose_only = [f"Code node: {node.node_id}"]

        prompt = f"""You are generating search index keywords for a knowledge file.
Node ID: {node.node_id}
Node Type: {node.node_type}
Content (prose only):
{chr(10).join(prose_only[:3])}

Task 1 — DENSE BLOCK:
Generate 8-12 pipe-separated keywords that compress the core technical facts.
Rules: No verbs. No articles. Technical terms only. Max 15 tokens total.
Format: keyword1|keyword2|keyword3...

Task 2 — INDEX KEYWORDS:
Generate 5-8 comma-separated search keywords an agent would use to find this node.
Think: what queries should route here? Include synonyms.
Format: keyword1,keyword2,keyword3...

Respond with exactly two lines:
DENSE: <dense keywords>
INDEX: <index keywords>

Do not add any explanation or other text."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        lines = text.split("\n")
        dense = lines[0].replace("DENSE:", "").strip()
        index = lines[1].replace("INDEX:", "").strip() if len(lines) > 1 else dense
        return dense, index
```

---

### 7.4 Stage 3: Verification Pass

The verification pass is **non-negotiable**. It runs deterministically after conversion and produces a quantified accuracy score. Any file scoring below 0.95 is flagged for human review before being used by agents.

```python
import re
from dataclasses import dataclass

@dataclass
class VerificationReport:
    accuracy_score: float
    missing_code_blocks: list
    missing_table_rows: list
    heading_coverage: float
    content_added: list   # content in OG not in MD (bad)
    passed: bool

class Stage3Verifier:
    def verify(self, original_md: str, converted_OG: str) -> VerificationReport:
        errors = []
        checks_passed = 0
        checks_total = 0

        # Check 1: Every code block in MD exists verbatim in OG
        md_code_blocks = re.findall(r"```[\w]*\n([\s\S]*?)```", original_md)
        for block in md_code_blocks:
            checks_total += 1
            block_clean = block.strip()
            if block_clean in converted_OG:
                checks_passed += 1
            else:
                errors.append(f"MISSING CODE: {block_clean[:50]}...")

        # Check 2: All table rows preserved
        md_tables = re.findall(r"(\|.+\|)", original_md)
        for row in md_tables:
            if "---" in row: continue  # separator rows ok to skip
            checks_total += 1
            if row.strip() in converted_og:
                checks_passed += 1
            else:
                errors.append(f"MISSING ROW: {row[:60]}")

        # Check 3: All headings became node IDs
        md_headings = re.findall(r"^#{1,3}\s+(.+)$", original_md, re.MULTILINE)
        og_node_ids = re.findall(r"::node\[id=([\w-]+)", converted_og)
        heading_coverage = 0
        for heading in md_headings:
            checks_total += 1
            slug = re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
            if slug in og_node_ids:
                checks_passed += 1
                heading_coverage += 1
            else:
                errors.append(f"MISSING NODE: {slug}")

        # Check 4: No content in OG that wasn't in MD
        # (LLM should only add ::dense and ::index keywords)
        og_full_blocks = re.findall(r"::full([\s\S]*?)::end", converted_og)
        added_content = []
        for block in og_full_blocks:
            for sentence in block.strip().split("."):
                if len(sentence) > 20:  # skip short fraOGents
                    if sentence.strip() not in original_md:
                        added_content.append(sentence.strip()[:80])

        # Calculate final score
        base_score = checks_passed / checks_total if checks_total > 0 else 1.0
        penalty = len(added_content) * 0.02   # -2% per added sentence
        final_score = max(0.0, base_score - penalty)

        return VerificationReport(
            accuracy_score=round(final_score, 4),
            missing_code_blocks=[e for e in errors if "CODE" in e],
            missing_table_rows=[e for e in errors if "ROW" in e],
            heading_coverage=heading_coverage / len(md_headings)
                             if md_headings else 1.0,
            content_added=added_content,
            passed=final_score >= 0.95
        )
```

---

### 7.5 Full Transpiler Orchestrator

```python
import json, datetime
from pathlib import Path

class OGTranspiler:
    def __init__(self, anthropic_api_key: str):
        self.parser = Stage1Parser()
        self.llm = Stage2LLMMetadata(anthropic_api_key)
        self.verifier = Stage3Verifier()

    def transpile(self, md_path: str, output_path: str = None) -> dict:
        md_path = Path(md_path)
        output_path = Path(output_path or md_path.with_suffix(".og"))

        original_md = md_path.read_text(encoding="utf-8")

        # Stage 1: Parse structure (no LLM)
        print("Stage 1: Parsing structure...")
        nodes = self.parser.parse(original_md)
        print(f"  → {len(nodes)} nodes extracted")

        # Stage 2: Generate metadata (LLM)
        print("Stage 2: Generating metadata...")
        index_entries = []
        for node in nodes:
            dense, index_kw = self.llm.generate_dense(node)
            node.dense = dense
            node.index_keywords = index_kw
            index_entries.append(
                f"  {node.node_id:<20} | {node.node_type:<10} | "
                f"{node.scope:<12} | {node.confidence:.2f} | {index_kw}"
            )
            print(f"  → {node.node_id}: dense={dense[:40]}...")

        # Stage 3: Write .og file
        OG_content = self._write_OG(md_path, nodes, index_entries)
        output_path.write_text(OG_content, encoding="utf-8")

        # Stage 4: Verify
        print("Stage 3: Verifying accuracy...")
        report = self.verifier.verify(original_md, OG_content)
        print(f"  → Accuracy: {report.accuracy_score:.1%}")
        print(f"  → Passed: {report.passed}")

        if not report.passed:
            print("  ⚠ WARNING: Score below 0.95 — human review required")
            for err in report.missing_code_blocks[:3]:
                print(f"    {err}")

        return {"output": str(output_path), "report": report.__dict__}

    def _write_OG(self, md_path, nodes, index_entries) -> str:
        lines = []
        today = datetime.date.today().strftime("%Y-%m")

        # File header
        lines.append("::meta")
        lines.append(f"  title: {md_path.stem}")
        lines.append(f"  version: 1.0.0")
        lines.append(f"  updated: {today}")
        lines.append(f"  source: {md_path.name}")
        lines.append("  scope: all")
        lines.append("::end")
        lines.append("")

        # Index
        lines.append("::index")
        lines.append("  # node-id               | type       | scope        | conf | keywords")
        lines.extend(index_entries)
        lines.append("::end")
        lines.append("")

        # Nodes
        for node in nodes:
            lines.append(
                f"::node[id={node.node_id} type={node.node_type} "
                f"confidence={node.confidence} scope={node.scope}]"
            )
            lines.append("::dense")
            lines.append(node.dense)
            lines.append("::end")
            lines.append("")

            for block in node.content_blocks:
                btype = block["type"]
                content = block["content"]
                if btype == "code":
                    lang = block.get("lang", "text")
                    lines.append(f"::code[lang={lang}]")
                elif btype == "table":
                    lines.append("::table")
                elif btype == "steps":
                    lines.append("::steps")
                elif btype == "list":
                    lines.append("::list")
                elif btype == "warning":
                    lines.append("::warning")
                else:
                    lines.append("::full")
                lines.append(content)
                lines.append("::end")
                lines.append("")

            if node.edges:
                lines.append("::edges")
                lines.extend(node.edges)
                lines.append("::end")

            lines.append("::end  # " + node.node_id)
            lines.append("")

        return "\n".join(lines)


# Usage
if __name__ == "__main__":
    transpiler = OGTranspiler(api_key="your-key")
    result = transpiler.transpile("deploy-skill.md")
    print(f"Output: {result['output']}")
    print(f"Accuracy: {result['report']['accuracy_score']:.1%}")
```

---

## 8. The OG Reader

### 8.1 Architecture

The OG Reader is the runtime query engine for `.og` files. It is a pure Python library requiring **no LLM, no database, no server** — just a file path and a query. It implements the 3-pass reading model and all 8 gap solutions in approximately 350 lines of code.

The OG Reader is the critical piece that makes ObjectGraph actually save tokens. Without it, `.og` files are just well-organized Markdown. With it, agents stop reading files and start querying them.

---

### 8.2 Full OG Reader Implementation

### 8.2 Engine Architecture

The OG Engine (`objectgraph.reader`) is built on a two-tier architecture designed for massive files and zero-overhead routing:

#### 1. The Lexical Parser (`parser.py`)
A high-speed, regex-driven state machine that parses `.og` files directly from disk. It never loads the full file into memory. Instead, it streams the file and yields node blocks.
- **`parse_index`**: Scans the top of the file, builds the `OGIndex` dictionary in milliseconds, and stops immediately when it hits `::end` of the index block.
- **`extract_nodes_batch`**: Scans the file *exactly once* to extract a specific set of `node_ids`. This means whether an agent requests 1 node or 50 nodes, the I/O cost is identically bounded to a single sequential read.

#### 2. The Agentic Engine (`engine.py`)
The orchestration layer that LLMs interact with via tools.
- **`search_index`**: Fetches the index and performs highly-optimized keyword matching and role-based filtering, returning a condensed string for the LLM.
- **`resolve_context`**: Handles the multi-node retrieval, parses `->[:requires]` dependency edges, and formats the output into a single, clean markdown payload optimized for the LLM's context window.
- **`traverse`**: An advanced BFS graph-walker that can autonomously chase edges up to a `depth_limit`.

---

### 8.3 Agentic Tooling (MCP)

To integrate the OG Engine into any agent framework, expose its core methods as MCP tools. This allows Claude, GPT-4, or any other LLM agent to call it natively:

```python
# mcp_og_tools.py
from mcp import tool
from objectgraph.reader.engine import OGReader

reader = OGReader()

@tool
def search_skill_index(filepath: str, query: str) -> str:
    """Search the ObjectGraph skill file to find relevant node IDs."""
    return reader.search_index(filepath, query)

@tool
def resolve_skill_context(filepath: str, node_ids: list[str]) -> str:
    """Fetch the full instructions and dependencies for specific node IDs."""
    return reader.resolve_context(filepath, node_ids)

@tool
def check_skill_changelog(filepath: str) -> str:
    """Fetch the changelog of the skill file to see recent additions, updates, and deprecations."""
    delta = reader.get_delta(filepath)
    if delta:
        lines = ["CHANGELOG:"]
        for entry in delta.entries:
            lines.append(f"- [{entry.date}] {entry.action.upper()}: {entry.node_id} ({entry.description})")
        return "\n".join(lines)
    return "No changelog found."
```

---

## 9. Agent Writing .og Files Natively

One of ObjectGraph's most important properties is that agents can write valid `.og` files **without retraining** — using only a system prompt addition. This section provides the exact rules and quality rubric needed.

### 9.1 System Prompt Rules for Agents

```
## ObjectGraph (.og) File Writing Rules

When creating or updating knowledge/skill files, use .og format.

### REQUIRED Structure (in this order):
1. ::meta block with title, version, updated, scope
2. ::index block — one line per node with keywords
3. One ::node block per major topic

### Content Tag Rules:
- Use ::code[lang=X] for ALL code — never put code in ::full
- Use ::steps for numbered sequential instructions (order matters)
- Use ::list for bullet points (order does not matter)
- Use ::table for structured data — preserve all rows exactly
- Use ::warning for critical information the agent must never skip
- Use ::full for prose explanations only

### ::dense Rules (CRITICAL):
- Write ::dense AFTER writing ::full for each node
- Maximum 15 tokens — this is a hard limit
- Pipe-separated technical keywords only
- No verbs, no articles, no filler words
- Think: "what would a search index contain for this node?"
- NEVER summarize ::code or ::table in ::dense — just list the topic

### ::index Rules:
- Every node must have an index entry
- Keywords are comma-separated
- Include synonyms and common misspellings
- Format: node-id | type | scope | confidence | keywords

### What NOT to do:
- Never put code inside ::full blocks
- Never paraphrase table data — copy it exactly
- Never skip the ::dense block
- Never make up content that wasn't in the source
```

---

### 9.2 Quality Rubric for Dense Blocks

| Criterion | Good Example | Bad Example |
|---|---|---|
| Under 15 tokens | `uv\|sync\|python3.11\|dependencies\|uv.lock` | "You should use uv to manage and sync dependencies" |
| No verbs | `kubernetes\|helm\|namespace\|replica-set` | "deploy to kubernetes using helm charts" |
| Technical specificity | `sha256\|hmac\|jwt\|bearer-token\|expiry` | "security authentication tokens" |
| Pipe-separated | `nginx\|ssl\|443\|reverse-proxy\|upstream` | "nginx, ssl, port 443, reverse proxy" |
| No code snippets | `project-env\|sync\|lockfile` | `uv sync --extra dev` |
| Includes synonyms | `install\|setup\|uv\|sync\|dependencies` | "uv sync" |

---

## 10. Adoption Strategy

### 10.1 Markdown-Like Syntax — Low Migration Effort

A key adoption decision is that ObjectGraph uses a **familiar, Markdown-like syntax**. Most of an existing `.md` skill's prose carries over directly; you add the structured `::` blocks (index, dense, edges, assertions) incrementally to unlock query-aware loading. Because the body stays Markdown-like, `.og` files remain human-readable and render legibly even without a dedicated reader.

> **Porting a Markdown skill is incremental — keep the prose, add `::` semantic blocks to unlock the optimization benefits.**

The adoption analogy is TypeScript vs JavaScript. TypeScript didn't ask JavaScript developers to relearn programming — it added types on top. ObjectGraph adds semantic structure on top of a Markdown-like base, so migration effort is low and the benefit grows as you annotate more of the file.

---

### 10.2 Migration Path

| Timeline | Step |
|---|---|
| **Week 1** | Ship transpiler as open source CLI: `og transpile skill.md → skill.og` |
| **Week 2** | Ship GM Reader package with uv install path: `uv add og-reader` |
| **Week 3** | Auto-transpile all existing skill files in your repo (one command) |
| **Week 4** | Add GM Reader as MCP tool to agent system prompt |
| **Month 2** | Measure token savings, publish benchmark numbers |
| **Month 3** | Submit PR to LangChain/CrewAI for native `.og` support |
| **Month 6** | VS Code extension for `.og` syntax highlighting and validation |

---

### 10.3 Framework Integration Priority

The fastest path to industry adoption is through **one framework partnership**. The target is whichever framework adopts it first as their recommended SKILL file format:

| Framework | Integration Point | Impact |
|---|---|---|
| **Claude Tool Use / MCP** | Add `og_query` as built-in MCP tool | Immediate — all Claude agents benefit |
| **LangChain** | Add `GMFileLoader` to document loaders | Large ecosystem — 50k+ repos |
| **CrewAI** | Replace agent YAML configs with `.og` files | Agent framework — high fit |
| **AutoGen** | Add `GMSkillFile` as native skill type | Microsoft ecosystem |
| **LlamaIndex** | `GMReader` as native document reader | RAG pipeline replacement |

---

## 11. Complete .og File Example

The following is a complete, production-ready `.og` skill file demonstrating all features: rich content types, role scoping, assertions, edges, changelog, and progressive disclosure architecture.

```
# deploy-skill.og — Python Application Deployment Skill
# ObjectGraph v1.0 — Complete example with all features

::meta
  title: Python Application Deployment Skill
  version: 2.3.0
  author: devops-team
  created: 2024-11-01
  updated: 2025-04
  domain: deployment|python|devops|production
  scope: all
  min-agent-version: 1.0
::end

::schema
  node-types: [concept, step, warning, example, assertion, meta]
  edge-types: [precedes, requires, see-also, supersedes, contradicts]
  scope-levels: [all, orchestrator, worker]
::end

::index
  # node-id               | type      | scope         | conf | keywords
    install                 | step      | all           | 0.99 | install,setup,uv,sync,dependencies,python,venv
  configure               | step      | all           | 0.97 | config,env,environment,variables,settings,.env
  deploy-prod             | step      | all           | 0.95 | deploy,production,release,ship,push,prod
  deploy-staging          | step      | all           | 0.95 | staging,test,preview,sandbox,stage
  rollback                | step      | all           | 0.93 | rollback,revert,undo,restore,previous
  api-keys                | step      | orchestrator  | 0.99 | api,key,secret,vault,credentials,auth
  api-keys-worker         | step      | worker        | 0.99 | api,key,credentials,auth,access
  troubleshoot            | step      | all           | 0.90 | error,fail,debug,broken,exception,crash
  post-install-check      | assertion | all           | 1.00 | verify,check,assert,validate,test
  __changelog             | meta      | all           | 1.00 | changelog,updates,changes,new,diff,version
::end

# ═══════════════════════════════════════════════════════════
# CHANGELOG NODE — read this first if you have a cached version
# ═══════════════════════════════════════════════════════════

::node[id=__changelog type=meta]
::changelog
  2025-04-15 | added    | node[kubernetes-deploy] | New k8s support
    2025-04-10 | updated  | node[install]           | Added uv sync --frozen guidance
  2025-03-01 | deprecated | node[heroku-deploy]   | Heroku free tier ended
::end
::end # __changelog

# ═══════════════════════════════════════════════════════════
# INSTALL NODE
# ═══════════════════════════════════════════════════════════

::node[id=install type=step confidence=0.99 scope=all updated=2025-04 entry=true]

::dense
python3.11+|uv|sync|dependencies|project-env|.venv|uv.lock
::end

::full
# Installation
Ensure Python 3.11 or higher is installed on the target system.
::end

::steps
1. Sync project dependencies: uv sync --extra dev
2. Validate runtime: uv run python --version
3. Validate package wiring: uv run hachi --help
4. Run tests in managed env: uv run pytest
5. For CI, enforce lockfile with: uv sync --frozen --extra dev
::end

::warning
Never install project dependencies globally.
Use uv-managed project environments to avoid dependency conflicts.
::end

::code[lang=bash]
uv sync --extra dev
# Verify installation
uv run python --version
uv run python -c "import requests"
::end

::edges
  ->[:precedes]    configure
  ->[:precedes]    post-install-check
  ->[:requires]    concept-virtualenv
::end

::end # install

# ═══════════════════════════════════════════════════════════
# POST-INSTALL ASSERTION
# ═══════════════════════════════════════════════════════════

::node[id=post-install-check type=assertion]
::dense
verify|python3.11|uv|sync|dependencies|assertion
::end
::assertion
  trigger: after[install]
  check: command('python --version') matches 'Python 3\.1[0-9]'
    check: command('uv run python -c "import requests"') exits 0
  check: file_exists('.venv/bin/activate')
  on-pass: ->[:proceed] configure
  on-fail: ->[:retry limit=2] install
  on-fail-after-retries: ->[:escalate] troubleshoot
  max-retries: 2
::end
::end # post-install-check

# ═══════════════════════════════════════════════════════════
# ROLE-SCOPED API KEY NODES (Gap 6)
# ═══════════════════════════════════════════════════════════

::node[id=api-keys type=step confidence=1.0 scope=orchestrator]
::dense
vault|prod-api-key|secret-path|orchestrator-only
::end
::full
Retrieve the production API key from the internal Vault instance.
::end
::code[lang=bash]
vault kv get secret/prod/api-key
export API_KEY=$(vault kv get -field=value secret/prod/api-key)
::end
::end # api-keys

::node[id=api-keys-worker type=step confidence=1.0 scope=worker]
::dense
api-key|get_secret|orchestrator-managed|tool-call
::end
::full
API keys are managed by the orchestrator.
Request credentials using the get_secret tool — do not access Vault directly.
::end
::code[lang=python]
api_key = get_secret("prod/api-key")
::end
::end # api-keys-worker

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

::node[id=configure type=step confidence=0.97 scope=all updated=2025-04]
::dense
.env|environment-vars|DATABASE_URL|SECRET_KEY|DEBUG=false|config
::end
::full
# Configuration
Copy the environment template and populate all required variables.
::end
::code[lang=bash]
cp .env.example .env
# Edit .env with production values
::end
::table
| Variable     | Required | Default | Description                 |
|--------------|----------|---------|-----------------------------|
| DATABASE_URL | Yes      | —       | PostgreSQL connection string |
| SECRET_KEY   | Yes      | —       | Django/Flask secret key     |
| DEBUG        | No       | false   | Enable debug mode           |
| PORT         | No       | 8000    | Application port            |
::end
::edges
  ->[:precedes]  deploy-prod
  ->[:precedes]  deploy-staging
::end
::end # configure

# ═══════════════════════════════════════════════════════════
# TROUBLESHOOT
# ═══════════════════════════════════════════════════════════

::node[id=troubleshoot type=step confidence=0.90 scope=all skip-if-known=false]
::dense
error|debug|logs|exception|crash|fix|diagnose|trace
::end
::full
# Troubleshooting Guide
Check application logs first before attempting any fixes.
::end
::steps
1. Check logs: docker logs <container> or tail -f app.log
2. Verify environment: python -c 'import django; print(django.__version__)'
3. Test database: python manage.py dbshell
4. Check disk space: df -h
5. Memory: free -m
::end
::code[lang=bash]
# Quick diagnostic
python manage.py check --deploy 2>&1 | head -50
::end
::traverse
  entry: true
  depth-limit: 2
  priority: [:requires, :precedes]
::end
::end # troubleshoot
```

---

## 12. Conclusion & Future Work

### 12.1 What We've Built

ObjectGraph (.og) is not just a new file format — it is a complete paradigm shift in how AI agents interact with knowledge and skill files. Starting from the fundamental observation that Markdown was designed for humans reading linearly and is deeply misaligned with agents querying intentionally, we have designed and specified:

- A rich, semantically-typed file format with 20+ purpose-built tags
- The 3-pass progressive disclosure reading model (index → dense → full)
- Solutions to all 8 identified gaps in current Markdown-based agent file systems
- A 3-stage hybrid transpiler that converts any `.md` file with verified accuracy
- A pure-Python GM Reader requiring no LLM, no database, no infrastructure
- An MCP tool wrapper for immediate integration with any agent framework
- System prompt rules enabling agents to write valid `.og` files natively
- A token savings model, plus a reproducible benchmark ([`tests/test_og_benchmark.py`](tests/test_og_benchmark.py), CI-enforced ≥80%) measuring load-one-node vs. dump-all-skills on the bundled skills

---

### 12.2 The Core Innovation

The most important insight in ObjectGraph is not any individual tag or feature — it is the architectural principle that **the document teaches the agent how to read itself**. The `::index`, `::dense`, `::traverse`, and `::assertion` blocks are not just metadata — they are instructions to the agent embedded in the file format itself. This makes ObjectGraph self-describing, zero-shot parseable, and infrastructure-free.

A second key insight is the **bounded LLM risk principle**: LLMs only generate navigational metadata (`::dense` and `::index` keywords) during conversion. They never touch actual content. This means hallucination risk is contained to the parts of the file that serve as pointers — not the parts that serve as source of truth.

---

### 12.3 Future Work

| Area | Description |
|---|---|
| **GM Schema Language** | A formal schema definition format for domain-specific `.og` files, enabling validation at write time. |
| **Multi-file Federation** | Cross-file edge resolution — nodes in one `.og` file pointing to nodes in another, enabling knowledge graphs across file systems. |
| **Semantic Diff Tool** | A CLI tool that compares two versions of a `.og` file and produces a human-readable + machine-readable diff report. |
| **GM Language Server** | VS Code language server for `.og` files: syntax highlighting, node ID autocomplete, edge validation, real-time accuracy scores. |
| **Benchmark Suite** | A standardized benchmark of 100 agent tasks against Markdown vs ObjectGraph, measuring token usage, accuracy, and task completion rate. |
| **LLM Fine-tuning Dataset** | A dataset of `.md → .og` conversion pairs for fine-tuning smaller models to produce high-quality ObjectGraph natively. |
| **Agent Self-optimization** | Agents that automatically improve their own `.og` files by promoting frequently-accessed `::full` blocks to `::dense`, and demoting rarely-accessed nodes. |

---

### 12.4 Getting Started

```bash
# 1. Install
uv add og-reader og-transpiler

# 2. Convert your first skill file
og transpile my-skill.md
# Output: my-skill.og (reports a per-file conversion accuracy score)

# 3. Query it
python -c "
from gm_reader import GMReader
reader = GMReader()
results = reader.query('my-skill.og', 'how do I install?')
print(results[0].dense)   # 12 tokens
print(results[0].full)    # full content when needed
"

# 4. Add to your agent system prompt
# SYSTEM: You have access to the og_query tool.
# ALWAYS use og_query instead of reading .og files directly.
# Never read a .og file with read_file — always use og_query.

# 5. Measure your savings on your own files
og benchmark --before my-skill.md --after my-skill.og --queries queries.txt
# Reports token reduction and conversion accuracy for your files
```

---

> **ObjectGraph is open for collaboration. The format specification, transpiler, and GM Reader are designed to be community-owned standards — not proprietary tools.**
>
> *The goal is simple: agents should spend tokens thinking, not reading.*

---

*ObjectGraph v1.0 — Initial Specification*
*© 2025 ObjectGraph Project — Open Specification*
