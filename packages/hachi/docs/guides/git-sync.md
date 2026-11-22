# Git-Sync Guide for Hachi Memory

This guide explains how to keep your Hachi memory graph in sync across devices using
plain `git`.

## Why .og files are naturally git-syncable

Hachi stores all long-lived memory in `.og` (ObjectGraph) files — plain UTF-8 text with
no binary blobs, no embedded timestamps in every line, and no auto-generated IDs that change
on read. A fresh `git diff` on a memory file shows only lines you actually changed. This
makes `.og` files far easier to merge than JSON or SQLite databases.

## Per-device journal shards prevent merge conflicts

The main source of git conflicts in a shared memory graph is a journal file that two devices
write to simultaneously. Hachi solves this by giving each device its own shard:

```
memory/journal-workstation.og
memory/journal-my-laptop.og
memory/journal-server-01.og
```

Each shard is named after the machine's hostname (sanitised to `[a-zA-Z0-9_-]`, max 32 chars).
Only the local device ever writes to its own shard, so merges are conflict-free by design.
All shards are read by every device, so the full journal is always visible.

Use `get_hachi_paths().journal_shard_path()` in code to obtain the current device's
shard path.

## Conflict policy for shared memory files

Files other than journal shards (e.g. `profile.og`, `agent.og`, project nodes) are
typically written by one device at a time. When a true conflict does occur, apply the
**additive wins** rule:

- **Never delete** existing nodes — only append new ones.
- **Never overwrite** a conflicting node — keep both versions.
- Mark a genuine conflict by adding a `->[:conflict]` edge from the newer node to the
  older one so the agent can surface the ambiguity at next boot:

```
::node[my_goal_v2]
->[:conflict] my_goal
->[:role=fact]
...
```

The agent will surface conflicting nodes during its next memory consolidation pass and ask
you to resolve them.

## Recommended .gitignore additions

SQLite indexes are **derived** from the `.og` files and rebuild automatically — do **not**
commit them:

```
# Hachi — derived / machine-local state
*.db
*.db-wal
*.db-shm
```

## One-liner git setup

Run this once in your Hachi data directory to initialise a memory repository:

```bash
git init && echo "*.db\n*.db-shm\n*.db-wal" >> .gitignore && git add memory/ && git commit -m "init memory"
```

Then push to a private remote (GitHub, Gitea, self-hosted) and clone on each device.
Pull before each session, push after — or automate with a post-session hook.
