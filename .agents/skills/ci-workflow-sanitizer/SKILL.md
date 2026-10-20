---
name: ci-workflow-sanitizer
description: >-
  Audits, sanitizes, and repairs GitHub Actions CI/CD workflows (.github/workflows/*.yml).
  Enforces dynamic secret indirection, strict expression grammar, job-level env scoping,
  and artifact binding to prevent schema warnings and runner failures.
---

# CI Workflow Sanitizer

Audits and repairs GitHub Actions YAML workflows across root and sub-repositories (`NGO-AI-LLM`, `aasha-studio`).

## Overview

Ensures that all GitHub Actions workflows execute with zero runner syntax failures and zero IDE schema false-positives (such as VS Code / Antigravity GitHub Actions language server `Context access might be invalid` warnings).

## Common Pitfalls & Anti-Patterns

### 1. Static Context Schema False Alarms (`Context access might be invalid`)

- **Problem**: Local IDE language servers lack runtime knowledge of custom repository secrets (e.g., `NPM_TOKEN`, `DATADOG_API_KEY`, `APPLE_CERTIFICATE_PASS`) and raise false warnings when accessed as `secrets.KEY` or `secrets['KEY']`.
- **Solution**: Wrap dynamic accesses via `fromJSON(toJSON(secrets))['KEY']`:

```yaml
# Correct
env:
  NODE_AUTH_TOKEN: ${{ fromJSON(toJSON(secrets))['NPM_TOKEN'] }}
```

### 2. Deprecated Expression Syntax inside `if:` Conditionals

- **Problem**: Enclosing expressions in `${{ }}` inside an `if:` block (e.g., `if: ${{ github.event_name == 'push' }}`) is deprecated and causes subtle syntax errors or parser warnings.
- **Solution**: Omit `${{ }}` inside `if:` blocks:

```yaml
# Correct
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

### 3. Artifact Output Binding for Code Signing

- **Problem**: Downstream signing actions require exact artifact IDs from `actions/upload-artifact@v4`.
- **Solution**: Add an explicit step `id:` to the upload step and reference its output:

```yaml
- name: Upload build artifacts
  id: upload_step
  uses: actions/upload-artifact@v4
  with:
    name: release-app
    path: dist/

- name: Sign artifact
  uses: signpath/github-action-submit-signing-request@v1
  with:
    github-artifact-id: ${{ steps.upload_step.outputs.artifact-id }}
```

### 4. Runner Node.js Versioning

- Ensure all workflows use `actions/setup-node@v4` with explicit Node version matching project root engines (e.g. `node-version: 20` or `node-version: 22`).

## Automated Verification

Run the ecosystem workflow linter:

```bash
npm run lint:workflows
```

Script location: [`scripts/lint_workflows.mjs`](file:///c:/Users/admin/Downloads/NGO%20AI%20LLM/scripts/lint_workflows.mjs)

## Workflow

1. **Locate Workflows**: Search for all `.github/workflows/*.yml` files.
2. **Execute Linter**: Run `npm run lint:workflows`.
3. **Inspect Output**: Review any flagged lines for `${{ }}` in `if:`, raw secret access, or trailing whitespace.
4. **Apply Fixes**: Edit YAML files using atomic replacement tools.
5. **Re-Verify**: Confirm exit code 0 on `npm run lint:workflows`.
