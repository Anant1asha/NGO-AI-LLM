---
description: Mandatory zero-secret leakage and privacy guardrails for public GitHub repositories.
globs: ["**/*", ".git/**"]
---

# Public Repository Privacy & Zero-Secret Security Invariant

All repositories in the AASHA ecosystem (`NGO-AI-LLM`, `Aasha-AI`, `aasha-studio`, `NGOweb`, `web`) are **PUBLIC**. Every agent, subagent, and human contributor must strictly follow these non-negotiable security invariants.

## 1. Absolute Prohibition of Secrets & Private Information
Never stage, commit, or push any of the following to Git:
1. **API Keys & Tokens**:
   - OpenAI (`sk-...`), OpenRouter (`sk-or-v1-...`), Google Gemini (`AIzaSy...`), Anthropic (`sk-ant-...`), Hugging Face (`hf_...`).
   - Local AI proxy keys (e.g., 9Router dashboard keys `sk-...` from `http://localhost:20128`). Even though local, they must reside exclusively in `.env` and never be committed as code fallbacks to avoid tripping push protection and secret scanners.
   - GitHub Personal Access Tokens (`github_pat_...`, `ghp_...`).
2. **Cryptographic Keys & Certificates**:
   - Private keys (`*.pem`, `*.key`, `*.pkcs8`, `id_rsa`, `id_ed25519`).
3. **Session Artifacts & Cookies**:
   - Browser dumps, cookie exports (`cookie.json`, `Cookies_copy`, `*cookie*`).
4. **Environment Files**:
   - Real `.env`, `.env.local`, `.env.production`. Only `.env.example` with empty placeholder values is permissible.
5. **Personal Identifiable Information (PII)**:
   - Private phone numbers, personal email credentials, student personal data, internal server IP addresses.

## 2. Mandatory Pre-Commit Scrubbing Protocol
Before running any `git commit` or `git push`:
1. Verify `.gitignore` presence and ensure it contains:
   `node_modules/`, `scratch/`, `**/.scratch/`, `*cookie*`, `*.cookie`, `*.zip`, `.env`, `secrets/`.
2. Inspect `git status` for untracked configuration or secret files. Never use `git add .` or `git add -A` blindly when sensitive scratch files exist.
3. If an API key or token is accidentally exposed in working tree files, sanitize it immediately before staging.

## 3. Mock Tokens & Sanitizer Test Fixtures
When authoring unit tests or fixtures to validate secret sanitizers, evidence scrubbers, or regex redaction engines:
1. **Zero Literal Mock Secrets**: Never write intact mock tokens or fake API keys matching actual provider patterns (`github_pat_...`, `sk-...`, `AIzaSy...`, `ghp_...`). Static secret scanners and GitHub push protection inspect raw commit blobs and cannot distinguish test mocks from real credentials.
2. **String Concatenation Insulation**: Always split mock token patterns using string concatenation (e.g., `'github_pat_' + 'dummy_test_token_for_sanitizer_validation_only'`). At runtime, string concatenation yields the complete token so test assertions and regex engines are 100% exercised, while static scanners examining source code and commit blobs are not tripped.

## 4. Unpushed Commit History Sanitization
If an unpushed local commit accidentally introduces a static-scanner pattern or uninsulated mock token:
1. **Rewrite Before Pushing**: Verify with `git merge-base origin/<branch> <branch>` that the commit has not reached remote origin. Never leave scanner-triggering patterns in commit history.
2. **Interactive Rebase & Amend**: Rebase on the parent commit (`git rebase -i <parent_sha>`), mark the target commit as `edit`, apply string concatenation to the test fixture, amend with `git commit --amend --no-edit`, and continue (`git rebase --continue`).
3. **Verify Zero Blob Matches**: Confirm zero matches across history (`git log -S "<pattern>"`) and verify tests pass before pushing.
