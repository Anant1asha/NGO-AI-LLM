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
