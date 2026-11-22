# Claude Code hooks — Hachi's mechanical floor

These hooks are the **enforced** layer of the guardrails (CLAUDE.md is the advisory
layer). They run whether the model "wants" them to or not. Wired in
[`.claude/settings.json`](../settings.json); committed so they ship to every session
and every subagent.

All hooks are **stdlib-only Python** invoked via the portable exec form
(`python ${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py`) so they behave identically
under PowerShell, Git Bash, Linux, and macOS. Shared helpers live in `_common.py`.

| Hook | Event | What it does | Block? |
|------|-------|--------------|--------|
| `session_start.py` | `SessionStart` | Injects the gate command, current branch, and the top bug-bank **Avoid:** rules into context, so a fresh agent never starts cold. | no (additive context) |
| `bash_guard.py` | `PreToolUse(Bash\|PowerShell)` | (1) blocks `git push` to main/master without an approval sentinel; (2) blocks `git commit` that stages a `.env` or a high-confidence secret; (3) blocks forging the sentinel via Bash. | **yes** (exit 2) |
| `auto_format.py` | `PostToolUse(Write\|Edit\|MultiEdit)` | `ruff format`s the single touched `.py` file. Keeps diffs clean; never a repo-wide reflow. | no (best-effort) |
| `stop_guard.py` | `Stop` | Refuses to let the agent finish while `ruff check src tests` is red. | **yes** (exit 2) |

## Approving a push to main

The push-lock is deliberate. To grant a **one-shot** push to `main`/`master`:

1. The agent runs `uv run python scripts/preflight.py` and shows it green.
2. You give explicit OK in the conversation.
3. **You** (not the agent) create the sentinel from your own terminal:
   ```bash
   # from the repo root
   echo > .claude/.push-approved        # bash
   ```
   ```powershell
   New-Item .claude/.push-approved -ItemType File -Force   # PowerShell
   ```
4. The next `git push … main` succeeds and the sentinel is consumed (deleted). A
   second push needs a fresh sentinel. `bash_guard.py` refuses to create it via Bash.

## Testing the hooks

Hooks activate at session start (Claude Code asks you to review new hooks first). To
verify the **logic** without a restart, pipe a mock event into a script and check the
exit code:

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | python .claude/hooks/bash_guard.py ; echo "exit=$?"   # -> exit=2
echo '{"tool_input":{"command":"git push origin feature/x"}}' | python .claude/hooks/bash_guard.py ; echo "exit=$?" # -> exit=0
echo '{"stop_hook_active":false}' | python .claude/hooks/stop_guard.py ; echo "exit=$?"                            # -> exit=0 when ruff is green
echo '{}' | python .claude/hooks/session_start.py                                                                 # -> prints additionalContext JSON
```

## Disabling temporarily

Comment out (or remove) the relevant block in `.claude/settings.json`, or override it
in your gitignored `.claude/settings.local.json`. Prefer fixing the underlying issue —
a hook you route around is a guardrail you no longer have.
