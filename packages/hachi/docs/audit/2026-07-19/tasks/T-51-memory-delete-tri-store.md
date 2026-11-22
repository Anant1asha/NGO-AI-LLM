# T-51 · Make "forget" actually forget: tri-store delete with an `.og` tombstone

|  |  |
|---|---|
| **Source finding** | CF-12 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** — deleted facts come back |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-48](T-48-memory-package-boundary.md) — land this before the package move |
| **Effort** | ~3 days |
| **Difficulty** | High — read §5 before writing anything; the identifier problem is the whole task |
| **Files you will touch** | `src/hachi/core/memory_vault.py`, `src/hachi/core/memory_writer.py`, `src/hachi/core/memory_graph.py`, `src/hachi/tools/memory_tools.py`, `tests/test_memory_forget_is_durable.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Facts are written to **two** stores — `.og` files and ChromaDB. Deletes touch **one**
(Chroma), believe they touched two, and cannot touch the third-order effect at all. The
`.og` node survives on disk, and the per-turn graph-recall pass reads `.og` files
straight off the filesystem — so a fact the user asked the agent to forget is
re-injected into the very next turn's context.

Worse than the audit states: the FTS5 half of the delete is **also** a permanent no-op
(the identifier format can never match), and `delete_user_fact` / `delete_agent_fact`
do not even attempt it. Meanwhile the tool docstring the LLM reads says the fact was
*"removed from all backends"*.

When you are done, deleting a fact removes it from Chroma, removes it from the FTS5
index, and writes a tombstone into the `.og` graph that suppresses the node on every
read path — and a test proves the fact does not come back through graph recall.

## 2. Why this matters

"Forget that" is the single most trust-critical operation a memory product supports.
Everything else it gets wrong is recoverable by the user; this one is not, because the
user has no way to observe the failure. The CLI actively conceals it: `hachi memory
forget <id>` followed by `hachi memory search <text>` reports the fact **gone**,
because the CLI builds a bare `MemoryVault()` with no graph index attached
(`cli/commands/memory.py:30`) and therefore only ever shows the Chroma view. The fact is
still on disk, still indexed, and still being injected into live turns.

This is not a hygiene issue. A user who says "forget my old employer's name" and is
told it is forgotten, while it continues to be fed into every prompt, has been given a
false assurance by a product that sells governance.

If the fix you are about to write does not end with "a deleted fact no longer appears
in `build_graph_recall_section`", stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Facts DUAL-write — `core/memory.py:351` then `:354-365`

Inside `extract_facts`, the typed path:

```python
        written = memory_writer.write_nodes(nodes, session_id=session_id)
        logger.debug("extract_facts (typed): wrote %d nodes", written)

        # Parallel write to Chroma so existing semantic search continues to work
        for node in nodes:
            try:
                if node.role == "preference":
                    vault.upsert_user_fact(node.dense)
                elif node.role == "rule":
                    vault.upsert_agent_fact(node.dense)
                else:
                    vault.upsert_fact(node.dense, category=node.role)
            except Exception:
                logger.debug("extract_facts (typed): Chroma parallel-write failed", exc_info=True)
```

Note the three-way split: `preference` → `user_collection` **and** `profile.og`;
`rule` → `agent_profile` **and** `agent.og`; everything else → `core_memory` **and**
`projects/<slug>.og` or `core_memory.og` (`memory_writer.py:102-118`).

### 3.2 Deletes touch Chroma only — `core/memory_vault.py:1075-1105`

```python
    def delete_fact(self, fact_id: str) -> bool:
        """Remove a fact from ALL backends: Chroma core_memory + FTS5 index.
        ...
        """
        chroma_ok = True
        try:
            with self._vault_lock:
                self._assert_open()
                self._get_collection("collection").delete(ids=[fact_id])
        except Exception as exc:
            logger.warning("delete_fact: Chroma deletion failed for %s: %s", fact_id, exc)
            chroma_ok = False

        # FTS5 graph index: remove matching nodes so "forgotten" facts do not
        # resurface via BM25 keyword search (UC-MEM-004).
        # We delete by node_id (which equals the Chroma SHA-256 fact_id for facts
        # written through this vault) from both mem_fts and mem_nodes tables.
        # If the graph index is not attached or the id is absent, this is a no-op.
        if self._graph_index is not None:
            self._delete_from_fts5(fact_id)

        return chroma_ok
```

- Chroma delete: `:1090-1092`.
- FTS5 guard: `:1102`. FTS5 call: `:1103`.
  *(The audit cites `:1103-1104` for the pair; verified, the guard is `:1102`.)*
- **No `.og` write anywhere.** The docstring's "ALL backends" claim is false on two
  counts — see §3.4 and §3.5.

**The other two delete methods do not even try:**

- `delete_user_fact` — `core/memory_vault.py:1337-1352`. Chroma `user_collection` only.
  No FTS5, no `.og`. But `preference` nodes live in `memory/profile.og`.
- `delete_agent_fact` — `core/memory_vault.py:1469-1477`. Chroma `agent_profile` only.
  No FTS5, no `.og`. But `rule` nodes live in `memory/agent.og`.

### 3.3 The complete caller list

`rg -n "delete_fact" src/` — every production caller of the core delete:

| Caller | Anchor | Surface |
|---|---|---|
| `delete_memory` agent tool | `src/hachi/tools/memory_tools.py:216` | the LLM's own "forget" tool |
| `_smart_upsert` consolidation | `src/hachi/tools/memory_tools.py:146` | supersede-on-write (`for did in data.get("delete_ids", [])`) |
| `hachi memory forget` | `src/hachi/cli/commands/memory.py:165` | CLI (`--from core`) |
| gateway control plane | `src/hachi/cli/main.py:2314` | sweeps all three collections by name |
| `ChromaMemoryProvider.delete` | `src/hachi/core/memory_provider.py:158` | ABC delegate — **has no callers**, see [T-49](T-49-memory-provider-seam-decision.md) |
| TUI cockpit | `src/hachi/tui/cockpit/data.py:427` | REST client method, not a direct vault call |

`cli/main.py:2314` is worth reading — it loops
`for fn_name in ("delete_fact", "delete_user_fact", "delete_agent_fact")`, so the
gateway's forget hits all three Chroma collections and none of the `.og` files.

### 3.4 There is no `.og` deletion path anywhere in the repo

```bash
rg -n "def (delete|remove|unlink|tombstone)" src/hachi/core/memory_writer.py
# (no output)
```

The complete public/private surface of `memory_writer.py` is:
`_slugify` (`:57`), `_ts` (`:64`), `_node_block` (`:68`), `_route` (`:102`),
`MemoryWriter.__init__` (`:136`), `write_fact` (`:140`), `write_nodes` (`:164`),
`write_episode` (`:233`), `_read_node_ids` (`:254`), `_append_blocks` (`:262`),
`_update_dense` (`:276`).

Append and update. Never remove.

### 3.5 The FTS5 delete is a permanent no-op — the audit missed this

`_delete_from_fts5` — `core/memory_vault.py:703-728`:

```python
        db_path = getattr(self._graph_index, "_db_path", None)
        if db_path is None:
            return
        try:
            conn = sqlite3.connect(str(db_path), timeout=5, check_same_thread=False)
            try:
                with conn:
                    conn.execute("DELETE FROM mem_fts WHERE node_id = ?", (fact_id,))
                    conn.execute("DELETE FROM mem_nodes WHERE node_id = ?", (fact_id,))
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("_delete_from_fts5: could not remove %s: %s", fact_id, exc)
```

`fact_id` is a bare SHA-256 of the content (`MemoryVault._generate_id`,
`memory_vault.py:734-737`). But `MemoryIndex` writes a **composite** id —
`core/memory_index.py:118`:

```python
                node_id = f"{rel.with_suffix('')}:{node.name}"
```

e.g. `"core_memory:deploy-target"`, or `"projects/hachi:api-base-url"`. **A bare
SHA-256 can never equal that.** Both `DELETE` statements match zero rows, every time.
The comment at `:1099-1100` claiming the ids are equal is simply wrong.

And even if the ids matched, `MemoryIndex.refresh()` (`memory_index.py:92`) rebuilds
the whole index from `.og` files — `:135-136`:

```python
            conn.execute("DELETE FROM mem_fts")
            conn.execute("DELETE FROM mem_nodes")
```

— then re-inserts every parsed node. `MemoryWriter.write_nodes` triggers a refresh
after every write (`memory_writer.py:224-228`), so any hypothetical successful row
delete is undone by the next fact written.

**Net: `delete_fact` is a ONE-store delete. Not two.**

### 3.6 Bonus defect — `_delete_from_fts5` bypasses the index's own connection

Independent of the resurrection bug: `_delete_from_fts5` opens its **own**
`sqlite3.connect` (`:720`) against `MemoryIndex._db_path`, reached by
`getattr(self._graph_index, "_db_path", None)` (`:716`) — a private attribute, from
another module, behind a `getattr`. `MemoryIndex` serialises its own access through
`_conn()` (`memory_index.py:71-82`). Two writers on `mem_fts`/`mem_nodes` with no
shared lock is a latent write-race against `MemoryWriter`-triggered `refresh()`.

The docstring is candid about why (`:706-707`): *"so we do not need to add a new public
API to MemoryIndex (which is outside our edit scope)"*. It is inside yours.

### 3.7 The read path that resurrects deleted facts

Per turn, `gateway/orchestrator.py:1663-1668`:

```python
        if self._graph_recall:
            try:
                from hachi.core.graph_recall import build_graph_recall_section
                from hachi.core.paths import get_hachi_paths

                _graph_section = build_graph_recall_section(
                    user_input=user_input,
                    memory_dir=getattr(self.memory, "memory_dir", None)
                    or get_hachi_paths().memory_dir,
                    existing_recall=recall_block,
                )
```

`self._graph_recall` defaults to `True` (`orchestrator.py:597`, overridden from
`memory.graph_recall` at `:3490`, which itself defaults `True` —
`core/settings.py:107`). So this is on by default.

The chain:

1. `build_graph_recall_section` — `core/graph_recall.py:135`
2. → `get_node_index(memory_dir)` — `core/graph_recall.py:73`
3. → `_cached_load(str(memory_dir), sig)` — `core/graph_recall.py:47-48`, `@lru_cache(maxsize=4)`
4. → `load_memory_dir(Path(memory_dir_str))` — `core/graph_recall.py:55`
5. → `core/memory_graph.py:129-135`:
   ```python
   def load_memory_dir(memory_dir: Path) -> dict[str, GraphNode]:
       """Load all .og files from *memory_dir* into a name→GraphNode map."""
       index: dict[str, GraphNode] = {}
       for og_file in memory_dir.rglob("*.og"):
           for node in parse_memory_file(og_file):
               index[node.name] = node
       return index
   ```

Straight off the filesystem. Chroma is not consulted.

**Two aggravating details:**

- The LRU cache key is `(memory_dir, max st_mtime_ns)` (`graph_recall.py:58-70`). A
  Chroma-only delete changes no `.og` file, so the mtime signature is unchanged and the
  cached index — still containing the deleted node — is reused indefinitely.
- `graph_recall.py:193-194`:
  ```python
      if not seeds:
          seeds = list(node_index.keys())[-5:]
  ```
  When no node matches the query, the **last five nodes are injected anyway**. A deleted
  fact can therefore resurface on a turn that has nothing to do with it.

There is a second resurrection surface when `memory.graph=true`:
`MemoryVault.semantic_search` merges FTS5 hits via RRF (`memory_vault.py:1124-1132`),
and the FTS5 index is rebuilt from the same surviving `.og` files.

### 3.8 The tool tells the LLM a falsehood — `tools/memory_tools.py:203-225`

```python
    def delete_memory(fact_id: str) -> str:
        """Delete a workspace fact by ID from ALL storage backends.

        Removes the fact from:
          - Chroma core_memory collection (primary semantic store)
          - FTS5 graph index (if attached) so forgotten facts cannot resurface
            via keyword search (UC-MEM-004)
        ...
        """
        ...
        ok = vault.delete_fact(fact_id)
        if ok:
            return (
                f"Memory fact {fact_id} has been removed from all backends "
                "(Chroma + FTS5 index). It will not appear in future searches."
            )
```

Both the docstring the model reads when choosing the tool and the result string it
reads afterwards assert something untrue. The model will confidently tell the user the
fact is gone.

### 3.9 A tombstone mechanism already exists — and its limitation

`memory_graph.py` already suppresses superseded nodes. `expand_graph`, `:165`, `:177-178`,
`:200-201`:

```python
    superseded: set[str] = set()
    ...
        # Collect nodes this one supersedes — mark them suppressed.
        for old in node.supersedes:
            superseded.add(old)
    ...
    # Filter out superseded nodes
    return [n for n in result if n.name not in superseded]
```

The edge is parsed at `memory_graph.py:110-111` from the `.og` syntax
`->[:supersedes=<node-name>]` (`_EDGE_RE`, `:65`), and `supersedes` is deliberately
**excluded** from `_TRAVERSAL_EDGES` (`:28-38`).

**The limitation that will bite you:** suppression only fires when the *superseding*
node is itself in the result set — i.e. it was seeded by token overlap or reached
within two hops. A tombstone node that nothing seeds suppresses nothing. Your design
must handle that (§5).

### 3.10 Why it survived — the CLI shows the fact as gone

`hachi memory search` builds `MemoryVault()` directly (`cli/commands/memory.py:30`)
with no graph index attached, so `semantic_search` returns Chroma-only results
(`memory_vault.py:1124-1125`). Forget-then-search from the terminal looks correct. The
resurrection only happens inside a booted session where `attach_graph_index` has run
(`orchestrator.py:3056`, `:3070`) and graph recall is live.

No test asserts that a deleted fact is absent from `build_graph_recall_section`.

## 4. Reproduce the failure

Two halves. The first is fully runnable and decisive; the second is provable by code
reading and grep, and **is not reproducible as a single command — do not pretend
otherwise.**

### 4a. The `.og` node survives and is re-injected — RUNNABLE

This writes only into a temp directory and needs no ChromaDB and no gateway:

```bash
python - <<'PY'
import tempfile, pathlib
from hachi.core.memory_writer import MemoryNode, MemoryWriter
from hachi.core.graph_recall import build_graph_recall_section

d = pathlib.Path(tempfile.mkdtemp())

# 1. The agent extracts a fact — dual-write puts it in .og AND Chroma.
MemoryWriter(memory_dir=d).write_nodes(
    [MemoryNode(name="former-employer", role="fact",
                dense="the user previously worked at Initech",
                keywords=["employer", "Initech"])],
    session_id="sess-1",
)

# 2. The user says "forget that". vault.delete_fact() removes the Chroma row.
#    NOTHING in the repo removes the .og node — see §3.4.

# 3. The very next turn calls build_graph_recall_section().
print(build_graph_recall_section(user_input="where did I work?", memory_dir=d))
PY
```

**You will see now:** a `[Related memory (graph)]` block containing *"the user
previously worked at Initech"* — the fact the user asked to forget, injected into the
next prompt.

**You should see after the fix:** empty output. (After the fix, insert your new
tombstone call between steps 1 and 3 — that is exactly what §7's regression test does.)

Note you can drop the `keywords` and change `user_input` to something unrelated and it
**still** comes back, via the no-seed fallback at `graph_recall.py:193-194`. Try it.

### 4b. The FTS5 delete can never match — CODE-READING PROOF

```bash
# The id delete_fact passes: a bare SHA-256 from MemoryVault._generate_id.
rg -n -A 3 "def _generate_id" src/hachi/core/memory_vault.py

# The id MemoryIndex actually stores: "<relative-path-without-suffix>:<node-name>".
rg -n "node_id = f" src/hachi/core/memory_index.py

# The DELETE that assumes they are the same.
rg -n "DELETE FROM mem_fts WHERE node_id" src/hachi/core/memory_vault.py

# And the rebuild that would undo it anyway.
rg -n "DELETE FROM mem_fts$|DELETE FROM mem_nodes$" src/hachi/core/memory_index.py
```

**You will see now:** `hashlib.sha256(content...).hexdigest()` versus
`f"{rel.with_suffix('')}:{node.name}"` — two formats that cannot collide; a `DELETE`
keyed on the first against a table populated with the second; and a full
`DELETE`-then-reinsert rebuild in `refresh()`.

**You should see after the fix:** the delete resolves the composite node id (or calls a
new `MemoryIndex` public method), and the `.og` tombstone means a subsequent `refresh()`
does not restore the node.

### 4c. What the terminal misleadingly shows — worth seeing once

```bash
hachi memory search "Initech"        # note the ID
hachi memory forget <that-id>
hachi memory search "Initech"        # reports gone
```

**This is the trap, not the test.** The CLI vault has no graph index attached
(`cli/commands/memory.py:30`), so it only ever shows the Chroma view. The fact is still
on disk. Do not use this sequence as your verification.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> The hard part is not writing a tombstone — it is **knowing which `.og` node a Chroma
> `fact_id` refers to.** There is no shared identifier today:
>
> - Chroma id = `sha256(content)` — `MemoryVault._generate_id`, `memory_vault.py:734-737`.
> - `.og` node name (typed path) = `_slugify(raw["name"] or raw["dense"][:40])` —
>   `core/memory.py:337`. Derived from an **LLM-supplied label**, not from content.
> - `.og` node name (`FTS5MemoryProvider.upsert` path) = `"fact-" + sha256(content)[:12]` —
>   `memory_writer.py:154`. A 12-char prefix of the Chroma id.
> - Chroma stores `node.dense` (truncated to 200 chars at `core/memory.py:342`); the
>   `.og` node stores the same `dense`. So content matches, ids do not.
>
> Pick one:
>
> **(A) Content-addressed lookup — RECOMMENDED for this task.**
> On delete, fetch the Chroma document text for `fact_id` **before** removing the row,
> then find `.og` nodes whose `dense` matches and tombstone those. One extra Chroma
> `get(ids=[fact_id])` before the `delete`.
> *For:* no schema change, no migration, works for facts already on disk today, and the
> matching key (`dense`) is exactly what both stores persist.
> *Against:* two facts with identical dense text tombstone together — which is correct
> behaviour, since they are the same fact. Truncation at 200 chars means very long
> facts match on their truncated form; acceptable, and consistent with how Chroma
> stored them.
>
> **(B) Write the Chroma id into the `.og` node at write time.**
> Add `->[:chroma_id=<sha256>]` in `_node_block` and index it. Exact, unambiguous.
> *For:* precise, and enables future cross-store reconciliation.
> *Against:* **does not help any fact already written** — every existing `.og` node
> lacks the edge, so the bug persists for all historical data until a migration runs.
> That migration is content-addressed matching, i.e. option A, done once instead of
> per-delete. Do (A) now; (B) is a reasonable follow-up for new writes.
>
> **(C) Physically rewrite the `.og` file to remove the node.**
> *For:* simplest mental model — gone means gone.
> *Against:* **violates the format's append-only governance rule.**
> `memory_gardener.py:3` states it explicitly: *"appends-only. The gardener never
> overwrites existing node content"*. The `.og` graph is the audit artefact; destroying
> history in it defeats its purpose, and a crash mid-rewrite corrupts the file. Do not
> choose this.
>
> **Recommendation: (A).** The rest of this spec assumes it. If you choose otherwise,
> say so in the commit message and adapt §6/§7.

### Target state

1. **`MemoryWriter.write_tombstone(...)`** — a new public method, the `.og` half of the
   delete:

   ```python
   def write_tombstone(self, node_name: str, *, reason: str = "forgotten") -> bool:
       """Append a tombstone node that supersedes *node_name*.

       Append-only: the original node is left on disk (the .og graph is an audit
       artefact) but every read path suppresses it via the `supersedes` edge.
       Returns True when a tombstone was written.
       """
   ```

   It writes a node carrying `->[:supersedes=<node_name>]`, plus
   `->[:role=tombstone]` and `->[:reason=<reason>]`. Route it to the **same file** as
   the node it tombstones so a per-file read sees both.

2. **`MemoryVault.delete_fact` becomes tri-store**, in this order:
   1. `get(ids=[fact_id])` on the collection to capture the document text (before the
      row disappears).
   2. Chroma delete — unchanged (`:1090-1092`).
   3. FTS5 delete — via a **new public `MemoryIndex` method** (§3.6), not a bypass
      connection, and **unconditional** on the graph index being attached is impossible
      — so instead: when `self._graph_index is None`, still write the tombstone, and
      let the next `refresh()` drop the row naturally (see item 4).
   4. `.og` tombstone for every node whose `dense` equals the captured text.

3. **The `_graph_index is not None` guard at `:1102` stops gating correctness.**
   Today, with `memory.graph=false`, FTS5 cleanup is skipped entirely — and since the
   `.og` node also survives, a later flip of `memory.graph` to `true` rebuilds the
   index *including the forgotten fact*. After the fix the tombstone is written
   regardless of the guard, so `refresh()` sees the suppression on any subsequent
   rebuild.

4. **`MemoryIndex` learns about tombstones.** `refresh()` parses `.og` and re-inserts
   everything (`memory_index.py:92-151`). It must skip nodes suppressed by a
   `supersedes` edge from a tombstone — otherwise the FTS5 row returns on the next
   write. This is the item most likely to be forgotten; it is what makes step 2.3
   permanent instead of transient.

5. **`delete_user_fact` and `delete_agent_fact` get the same treatment** — they are the
   `profile.og` and `agent.og` halves of the same bug (§3.2).

6. **`expand_graph` suppression must not depend on the tombstone being seeded** (§3.9).
   The cleanest fix is at the load boundary: have `load_memory_dir`
   (`memory_graph.py:129-135`) drop any node named by a `supersedes` edge anywhere in
   the loaded set, before `expand_graph` ever sees it. That makes suppression global
   rather than traversal-dependent, and fixes the same latent hole for genuine
   supersede-on-write.

7. **The tool strings stop lying.** `tools/memory_tools.py:203-213` and `:218-221` are
   updated to describe what actually happens — three stores plus a tombstone — or, if
   any store legitimately cannot be reached, to say so explicitly rather than claiming
   success.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `MemoryWriter.write_tombstone(...)` (`core/memory_writer.py`), plus a `tombstone`
   branch in `_route` (`:102-118`) that returns the same path as the node it
   supersedes. Add unit coverage for the emitted `.og` text.
3. Make suppression global at load: filter superseded names inside `load_memory_dir`
   (`core/memory_graph.py:129-135`). Keep the existing `expand_graph` filter
   (`:200-201`) — it is harmless and still correct for traversal-local supersedes; do
   not delete it ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
4. Add a public delete to `MemoryIndex` (e.g. `delete_node(node_id)`) that goes through
   its own `_conn()` (`memory_index.py:71-82`), and make `refresh()` skip
   tombstone-suppressed nodes.
5. Rewrite `MemoryVault._delete_from_fts5` (`:703-728`) to call that method instead of
   opening its own connection. Keep the method as the vault's seam; only its body
   changes.
6. Rewrite `MemoryVault.delete_fact` (`:1075-1105`) per §5 item 2, including the
   pre-delete `get(ids=[fact_id])`. Fix the docstring's "ALL backends" claim to state
   what is now true.
7. Apply the same to `delete_user_fact` (`:1337-1352`, → `profile.og`) and
   `delete_agent_fact` (`:1469-1477`, → `agent.og`).
8. Update `tools/memory_tools.py:203-225` — docstring and both result strings.
9. Run the regression test — it must now pass.
10. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_memory_forget_is_durable.py` (**new**)
- **Test names:** `test_forgotten_fact_does_not_resurface_via_graph_recall` (the
  headline lock), `test_tombstone_suppresses_node_even_when_unseeded`, and
  `test_fts5_delete_uses_the_real_node_id`
- **It must assert:** the real, observed behaviour — that
  `build_graph_recall_section` (the actual per-turn call site) does **not** contain the
  forgotten text after a tombstone is written. Not that a mock delete was called.
- **It must FAIL before your fix** with:
  - test 1: `AttributeError: 'MemoryWriter' object has no attribute 'write_tombstone'`,
    and once the method exists but the load filter does not,
    `AssertionError: forgotten fact resurfaced: 'Initech' in graph recall section`.
    Test 1 is the behavioural lock — keep it even if you restructure the others.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

from hachi.core.graph_recall import build_graph_recall_section, get_node_index
from hachi.core.memory_writer import MemoryNode, MemoryWriter

_SECRET = "the user previously worked at Initech"


def _write_fact(memory_dir: Path) -> None:
    MemoryWriter(memory_dir=memory_dir).write_nodes(
        [MemoryNode(name="former-employer", role="fact", dense=_SECRET,
                    keywords=["employer", "Initech"])],
        session_id="sess-1",
    )


def test_forgotten_fact_does_not_resurface_via_graph_recall(tmp_path: Path) -> None:
    """A tombstoned fact must not be injected into the next turn's context.

    Regression (T-51): facts dual-wrote to .og + Chroma but delete_fact only
    removed the Chroma row. graph_recall reads .og straight off disk, so a
    "forgotten" fact was re-injected on the very next turn.
    """
    _write_fact(tmp_path)
    # Sanity: it IS recalled before the tombstone (guards against a vacuous pass).
    assert "Initech" in build_graph_recall_section("where did I work?", tmp_path)

    MemoryWriter(memory_dir=tmp_path).write_tombstone("former-employer")
    get_node_index.cache_clear() if hasattr(get_node_index, "cache_clear") else None

    section = build_graph_recall_section("where did I work?", tmp_path)
    assert "Initech" not in section, f"forgotten fact resurfaced: {section!r}"


def test_tombstone_suppresses_node_even_when_unseeded(tmp_path: Path) -> None:
    """Suppression must not depend on the tombstone matching the query.

    graph_recall falls back to the last 5 nodes when nothing matches
    (graph_recall.py:193-194), so a query with zero overlap must still not
    resurface the forgotten fact.
    """
    _write_fact(tmp_path)
    MemoryWriter(memory_dir=tmp_path).write_tombstone("former-employer")

    section = build_graph_recall_section("what is the weather", tmp_path)
    assert "Initech" not in section


def test_fts5_delete_uses_the_real_node_id(tmp_path: Path) -> None:
    """The FTS5 delete must target the composite node_id MemoryIndex actually stores."""
    from hachi.core.memory_index import MemoryIndex

    _write_fact(tmp_path)
    index = MemoryIndex(memory_dir=tmp_path, db_path=tmp_path / "memory_index.db")
    index.refresh()
    assert index.search("Initech", top_k=5), "precondition: fact must be indexed"

    MemoryWriter(memory_dir=tmp_path).write_tombstone("former-employer")
    index.refresh()
    assert not index.search("Initech", top_k=5), "tombstoned node survived a refresh"
```

Notes:

- **`_cached_load` is an `lru_cache` keyed on `(memory_dir, max mtime_ns)`**
  (`graph_recall.py:47-48`, `:58-70`). Writing the tombstone changes an `.og` file's
  mtime, so the key changes and the cache invalidates naturally — **but mtime
  granularity on some filesystems can collapse two writes in the same instant.** If
  test 1 flakes, that is why; clear the cache explicitly rather than adding a `sleep`.
- Test 1's first assertion (the fact **is** recalled before the tombstone) is not
  decoration — without it the test would pass vacuously if `build_graph_recall_section`
  ever returned `""` for an unrelated reason.
- None of these tests touch ChromaDB. Keep it that way — see §12 (BB-3).

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_forgotten_fact_does_not_resurface_via_graph_recall` failed before the fix.
- [ ] `MemoryWriter.write_tombstone` exists and is called by all three vault delete methods (`delete_fact`, `delete_user_fact`, `delete_agent_fact`).
- [ ] `rg -n "sqlite3.connect" src/hachi/core/memory_vault.py` returns **nothing** — the bypass connection is gone (§3.6).
- [ ] `MemoryIndex.refresh()` does not re-insert tombstone-suppressed nodes (test 3 proves it).
- [ ] The tombstone is written even when `self._graph_index is None` (§5 item 3) — add a test case for `memory.graph=false`.
- [ ] `tools/memory_tools.py` no longer claims removal from backends it did not reach.
- [ ] The original `.og` node is still **on disk** — this is append-only; verify the file still contains the node text alongside the tombstone.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not start the package move.** [T-48](T-48-memory-package-boundary.md) relocates
  every file you are editing. Combining them makes this diff unreviewable, and this
  change genuinely needs review.
- **Do not physically delete nodes from `.og` files.** §5 option (C). The append-only
  rule is stated at `memory_gardener.py:3` and is the reason the graph is an audit
  artefact. Tombstone, never truncate.
- **Do not build the MemoryGardener reconciliation.** A gardener pass that reconciles
  Chroma against `.og` is the natural next thought and it is a real gap — but the
  gardener is *doubly dead* today (its output file is never written **and**
  `snapshot_gardener_diffs` at `gateway/orchestrator.py:745-760` has zero callers). That
  is [T-08](T-08-memory-gardener.md). Note it and move on.
- **Do not add a `chroma_id` edge to new writes** (§5 option B). It is a reasonable
  follow-up; it does not help the existing data and it widens this diff.
- **Do not "fix" the no-seed fallback** at `graph_recall.py:193-194`. Injecting the last
  five nodes when nothing matches is a deliberate recall behaviour, not a bug. Your job
  is to ensure a tombstoned node is not among them.
- **Do not fix the `getattr(self._graph_index, "_db_path", None)` pattern elsewhere.**
  Fix this one because you are replacing the whole function; leave the sweep to
  [T-14](T-14-ban-getattr-own-types.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** This changes what `load_memory_dir` returns,
which changes what every graph-recall consumer sees, which changes prompt content in
any test that boots a session and inspects context. `tests/test_knowledge_graph_recall.py`,
`tests/test_p3_01_memory_graph.py`, `tests/test_p2_04_memory_index.py`,
`tests/test_memory_cli_crud.py` and `tests/test_cli_memory.py` are the obvious
candidates — and they are not sufficient, because the resurrection path runs inside
gateway-booting tests too.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — "Forget" did not forget: deleted facts resurfaced through .og graph recall

- **Symptom:** After `hachi memory forget <id>` (or the agent's `delete_memory` tool),
  the fact was re-injected into the very next turn's context via the graph-recall
  block. The CLI concealed it: `hachi memory search` builds a bare `MemoryVault()` with
  no graph index attached, so it showed only the Chroma view and reported the fact
  gone. The tool's own docstring and result string told the model the fact had been
  "removed from all backends".
- **Root cause:** Facts dual-write to `.og` files and ChromaDB
  (`core/memory.py:351` + `:354-365`), but `MemoryVault.delete_fact` only removed the
  Chroma row — `core/memory_writer.py` had no delete/remove path of any kind. The
  per-turn `build_graph_recall_section` reads `.og` straight off disk via
  `load_memory_dir`'s `rglob("*.og")`. Two further defects made it worse: (a) the FTS5
  cleanup was a permanent no-op because `_delete_from_fts5` deleted
  `WHERE node_id = <chroma sha256>` while `MemoryIndex` stores
  `"<rel-path>:<node-name>"`, and `refresh()` rebuilds the table from `.og` anyway;
  (b) that cleanup was skipped entirely when `memory.graph=false`, and
  `delete_user_fact`/`delete_agent_fact` never attempted it at all.
- **Fix:** Added `MemoryWriter.write_tombstone()` which appends a node carrying
  `->[:supersedes=<name>]`; made all three vault delete methods tri-store
  (Chroma + FTS5 + `.og` tombstone), resolving the `.og` node by content match on the
  Chroma document captured before deletion; moved suppression into `load_memory_dir`
  so it is global rather than traversal-dependent; taught `MemoryIndex.refresh()` to
  skip suppressed nodes; replaced the bypass `sqlite3.connect` with a public
  `MemoryIndex` method; corrected the tool strings.
- **Avoid:** if a write goes to N stores, the delete must go to N stores — and a
  docstring claiming "all backends" is not evidence that it does. When two stores hold
  the same data under different identifiers, the delete path needs an explicit
  identifier-resolution step, and a test that reads back through the *production* read
  path, not through the store you just deleted from.
- **Locked by:** `tests/test_memory_forget_is_durable.py` — `test_forgotten_fact_does_not_resurface_via_graph_recall`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3 — read before writing any test here:** never `patch.dict(sys.modules)` over
  `chromadb`. `conftest.py` warms the chromadb PyO3 native module at import so it loads
  exactly once per process; `patch.dict` drops the compiled extension and every later
  chromadb test in the process dies with *"cannot load module more than once"*. Every
  test in §7 is deliberately Chroma-free (`MemoryWriter` + `graph_recall` + `MemoryIndex`
  only). Keep them that way — if you need vault coverage, construct `MemoryVault`
  against `tmp_path` as `tests/test_memory_vault_close.py` does.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. The vault you are
  editing is often the *process-shared* one (`shared_services.py:307` sets
  `vault.is_shared = True`); do not add per-session state to `MemoryVault`.
- **`_cached_load` is a module-level `lru_cache(maxsize=4)`** (`graph_recall.py:47`).
  It persists across tests in the same process. If a test sees stale nodes, that is
  why. Clear it explicitly; do not add a cache-busting hook to production code just for
  tests.
- **`MemoryWriter.write_nodes` triggers `MemoryIndex.refresh()`** (`memory_writer.py:224-228`).
  Writing a tombstone therefore rebuilds the FTS5 index immediately — which is what makes
  §5 item 4 (teaching `refresh()` about tombstones) mandatory rather than optional. Get
  the order right or the tombstone write itself restores the row you just deleted.
- **The three deletes hit three different Chroma collections.** `delete_fact` →
  `"collection"` (core_memory), `delete_user_fact` → `"user_collection"`,
  `delete_agent_fact` → `"agent_profile"`. They map to `core_memory.og`/`projects/*.og`,
  `profile.og`, and `agent.og` respectively (`memory_writer.py:102-118`). Do not
  cross-wire them.
- **`cli/main.py:2314` sweeps all three by name** with `getattr(vault, fn_name, None)`.
  If you rename any delete method, that loop silently stops calling it — there is no
  import to break. Grep before renaming.
- **Do not let the tombstone become a new resurrection vector.** A tombstone node has a
  `dense` field; if you put the forgotten text in it ("forgot: the user previously
  worked at Initech"), the FTS5 index and graph recall will happily surface *that*.
  Tombstones must reference the node **by name only** and carry no copy of the content.
