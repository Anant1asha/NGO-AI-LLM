---
name: git-multiplane-sync
description: >-
  Actionable multi-plane Git synchronization runbook for Plane 1 (Google Drive), Plane 2 (Google Colab), and Plane 3 (Local PC).
  Covers safe GitHub pushes, offline bundle creation, divergence remediation, pre-push verification, and secret scanning.
---

# Git Multi-Plane Synchronization Runbook

## Overview

Synchronizes the 3-plane AASHA AIOS architecture without data loss, lease conflicts, or remote misconfiguration:

- **Plane 1**: Google Drive cloud storage mirror (`aasha_aios_v2_bootstrap_full.bundle`).
- **Plane 2**: Google Colab GPU compute environment.
- **Plane 3**: Local PC workstation (authoritative working copy).
- **Upstream**: GitHub authoritative repository (`https://github.com/Anant1asha/NGO-AI-LLM.git`).

## Dependencies

- Pre-commit secret linter: `node scripts/lint_staged_secrets.mjs`
- Branch protection verifier: `node scripts/verify_branch_protection.mjs`
- Git pre-push hook: `.git/hooks/pre-push`

## Quick Start / Routine Sync Workflow

1. **Verify Branch & Remote State**:

   ```powershell
   node scripts/verify_branch_protection.mjs
   ```

2. **Stage Changes Safely (Pathspec Only)**:

   ```powershell
   git add -A
   node scripts/lint_staged_secrets.mjs
   ```

3. **Commit Clean Milestone**:

   ```powershell
   git commit -m "feat(<scope>): <description>"
   ```

4. **Push to GitHub Upstream**:

   ```powershell
   git push origin aios/v2-bootstrap
   ```

5. **Export Verified Offline Bundle**:

   ```powershell
   git bundle create "aasha_aios_v2_bootstrap_full.bundle" aios/v2-bootstrap
   git bundle verify "aasha_aios_v2_bootstrap_full.bundle"
   ```

## Handling Branch Divergence (Squash Reconciliation)

If local and remote branches diverge due to repetitive automated loop syncs:

1. **Archive Remote History**:

   ```powershell
   git push origin origin/aios/v2-bootstrap:refs/heads/archive/aios-v2-bootstrap-loop-history
   ```

2. **Reconcile with Force-With-Lease**:

   ```powershell
   git push --force-with-lease origin aios/v2-bootstrap
   ```

## Common Mistakes

- **Pushing to bundle**: Pushing to `.bundle` fails with `failed to push some refs`. Always push to `origin` and export with `git bundle create`.
- **Expanding file lists**: Running `git add $(git status -s)` with hundreds of files fails on Windows with "filename too long". Use `git add -A`.
- **Bypassing secret scanner**: Always run `lint_staged_secrets.mjs` before commit.
