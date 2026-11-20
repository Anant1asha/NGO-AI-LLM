# Superbrain Rule: Windows & Colab Safe Git Staging Policy

- Always enforce `git config core.longpaths true` and clean `.git/**/desktop.ini` before bundle sync or push.
- Never pass large file lists as CLI arguments to `git add`; use native directory pathspecs (`git add -A`, `git add dir/`) or `scripts/safe_git_add_and_commit.sh` (`--pathspec-from-file=-`).
- Keep `.venv/`, `.serena_venv/`, `.pytest_cache/`, `Aasha-AI/server/aasha_local.db`, and `*.bundle` ignored in `.gitignore` so IDE Source Control panels never attempt to stage 20,000+ transient files.
- Always run `node scripts/lint_staged_secrets.mjs` prior to commit.
