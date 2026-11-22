# ObjectGraph (.og) Format Specification

```
version: 1.0.0
status: published
date: 2026-06-13
```

---

## File Structure

An `.og` file is a plain-text document divided into two zones:

1. **Preamble** — file-level blocks that appear before any `::node`. Contains `::meta`, `::index`, and optionally `::schema` and `::changelog`.
2. **Node zone** — one or more `::node[id]` blocks, each containing metadata edges and content tags.

Block boundaries are delimited by `::tag` lines at column 0. A block ends when the next `::tag` (or `::node`) is encountered, or at end-of-file. An optional `::end` line may close a block explicitly (stripped by parsers).

```
::meta
  title: Example Skill
  version: 1.0.0

::index
  # node-id | type | scope | conf | keywords
  greet     | skill | all  | 1.0  | greet, hello

::node[greet]
->[:role=skill]
->[:scope=all]
->[:keywords=greet, hello]
::dense
greet|hello|welcome
::full
Greets the user by name.
```

---

## Metadata Tags

The `::meta` block uses `key: value` or `key=value` pairs (one per line). All fields are optional; omitted fields default to empty string unless noted.

| Field               | Description                                                                 |
|---------------------|-----------------------------------------------------------------------------|
| `title`             | Human-readable file title.                                                  |
| `version`           | Semantic version string (e.g., `1.0.0`).                                   |
| `author`            | Author or team identifier.                                                  |
| `domain`            | Pipe-separated domain tags (e.g., `productivity\|messaging`).              |
| `scope`             | Default access scope for the file. Defaults to `all`.                       |
| `min_agent_version` | Minimum OG reader version required to parse this file correctly.            |

---

## Index

The `::index` block is a pipe-delimited routing table consumed in **Pass 1** (~30 tokens). Lines beginning with `#` are comments and are ignored.

**Column format:**

```
# node-id | type | scope | conf | keywords
```

| Column     | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| `node-id`  | Must match a `::node[id]` declared later in the file.                      |
| `type`     | Content type: `skill`, `concept`, `warning`, `example`, `step`, etc.       |
| `scope`    | Access scope (see Scope Levels).                                             |
| `conf`     | Confidence score: `1.0` = verified, `0.5` = experimental, `<0.3` = deprecated. |
| `keywords` | Comma-separated searchable keywords for O(1) query routing.                 |

---

## Node Tags

Each `::node[id]` block may contain the following content tags. All are optional unless noted.

| Tag                 | Description                                                                   |
|---------------------|-------------------------------------------------------------------------------|
| `::dense`           | Compressed keyword summary, ~10–15 tokens. Used in **Pass 2**.               |
| `::full`            | Complete human-readable prose. Loaded in **Pass 3** only.                    |
| `::steps`           | Ordered sequential instructions. Numbered prefix (`1.`) is stripped by parsers. |
| `::code[lang]`      | Executable code block. `lang` is the language identifier (e.g., `bash`, `python`). |
| `::warning`         | Critical callout. Always read, even in dense-only passes.                    |
| `::note`            | Informational aside. Lower priority than `::warning`.                        |
| `::example`         | Concrete illustration. Skippable when the agent already knows the concept.   |
| `::assertion`       | Executable validation conditions. One condition per line, format: `key: description`. |
| `::edges`           | Typed relationship declarations (see Edge Syntax).                           |
| `::traverse`        | Traversal hints: `entry`, `depth`, `priority` key-value pairs.               |
| `::config`          | Key-value configuration for integration nodes.                               |
| `::tool`            | Tool definition block for LLM registration.                                  |
| `::api[name]`       | REST API definition for the Universal REST Adapter. Requires `endpoint` and `method` fields; `schema` and `headers` must be valid JSON when present. |

---

## Edge Syntax

Metadata edges appear at the top of a `::node` body and use the format:

```
->[:key=value]
```

Standard edge keys parsed by the reference implementation:

| Key             | Description                                                         |
|-----------------|---------------------------------------------------------------------|
| `role`          | Functional role: `skill`, `rule`, `integration`, `env`, etc.       |
| `scope`         | Access scope for this node (overrides file default).                |
| `keywords`      | Comma-separated search keywords for this node.                      |
| `requires`      | Comma-separated names of nodes this node depends on.                |
| `requires_auth` | Comma-separated auth token names required at runtime.               |

Edge declarations with unrecognised keys MUST be silently ignored by conforming parsers.

`::edges` blocks (node-level) declare typed graph relationships in the same arrow syntax:

```
->[:requires] run_tests
->[:calls] external-api
```

---

## Scope Levels

Scope controls which agent roles may read a node. The reference parser enforces scope in `filter_by_scope()`.

| Scope          | Visible to                                       |
|----------------|--------------------------------------------------|
| `all`          | Every agent role (default).                      |
| `orchestrator` | Only agents with role `orchestrator`.            |
| `worker`       | Only agents with role `worker`.                  |
| `agent`        | Only agents with role `agent`.                   |

A node with `scope=all` is always included regardless of the requesting role. A node with any other scope is excluded unless the requesting role matches exactly.

---

## 3-Pass Reading Model

The 3-pass model trades completeness for token efficiency:

**Pass 1 — Index** (~30 tokens total)
- The agent reads only the `::index` block.
- Sufficient for O(1) routing: determine which nodes are relevant to a query.
- Implementation: `OGFile.get_index_prompt()`.

**Pass 2 — Dense** (~10 tokens per selected node)
- For each node selected in Pass 1, the agent reads only `::dense` (and `::warning` if present).
- Sufficient for disambiguation and parameter extraction without loading full content.

**Pass 3 — Full** (variable; only when needed)
- The agent loads `::full`, `::steps`, `::code[*]`, `::example`, and other heavy blocks.
- Called only for the node(s) that will actually be executed.
- Implementation: `SkillEngine.resolve_node(name, blocks=["all"])`.

Parsers MUST make all three passes available independently. An agent that always performs Pass 3 is non-conforming.
