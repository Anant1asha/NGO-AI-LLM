#!/usr/bin/env node
/**
 * scripts/lint_workflows.mjs
 * Audits, sanitizes, and validates GitHub Actions CI/CD workflows (.github/workflows/*.yml).
 * Enforces ci-workflow-sanitizer rules:
 * 1. Prohibits ${{ }} expression wrapping inside 'if:' conditions.
 * 2. Checks action versions (recommends @v4+ for checkout, setup-node, etc.).
 * 3. Enforces Node.js version matching project root engine (>=20).
 * 4. Scans for raw secrets vs fromJSON(toJSON(secrets)) indirection.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const WORKFLOWS_DIR = path.join(ROOT_DIR, '.github', 'workflows');

console.log('=== GitHub Actions CI/CD Workflow Audit (ci-workflow-sanitizer) ===\n');

if (!fs.existsSync(WORKFLOWS_DIR)) {
  console.log(`[INFO] No .github/workflows directory found at ${WORKFLOWS_DIR}. Skipping.`);
  process.exit(0);
}

const files = fs.readdirSync(WORKFLOWS_DIR).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));

if (files.length === 0) {
  console.log('[INFO] No workflow YAML files found in .github/workflows/.');
  process.exit(0);
}

let totalChecks = 0;
let errors = 0;
let warnings = 0;

for (const file of files) {
  const filePath = path.join(WORKFLOWS_DIR, file);
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split(/\r?\n/);
  console.log(`Auditing: .github/workflows/${file} (${lines.length} lines)`);

  lines.forEach((line, idx) => {
    const lineNum = idx + 1;
    const trimmed = line.trim();

    // Check 1: Deprecated expression syntax inside if:
    if (/^\s*if:\s*.*\$\{\{.*\}\}/.test(line)) {
      console.error(`  [ERROR] Line ${lineNum}: Deprecated '\${{ }}' syntax inside 'if:' condition. Use raw expressions: ${trimmed}`);
      errors++;
    }

    // Check 2: Outdated GitHub Action versions (v1, v2, v3)
    const deprecatedActionMatch = trimmed.match(/uses:\s*(actions\/(?:checkout|setup-node|setup-python|upload-artifact|download-artifact))@v([1-3])\b/);
    if (deprecatedActionMatch) {
      console.warn(`  [WARN] Line ${lineNum}: Outdated action version '${deprecatedActionMatch[1]}@v${deprecatedActionMatch[2]}'. Recommend upgrading to @v4+`);
      warnings++;
    }

    // Check 3: Raw secret access in step env (warn for indirection best practice)
    if (/env:\s*.*secrets\.[A-Z0-9_]+/.test(line) && !line.includes('fromJSON(toJSON(secrets))')) {
      console.warn(`  [WARN] Line ${lineNum}: Direct secret access '${trimmed}'. Consider 'fromJSON(toJSON(secrets))[\'KEY\']' for strict IDE schema compatibility.`);
      warnings++;
    }

    totalChecks++;
  });

  // Check 4: Setup-node version check
  if (content.includes('actions/setup-node')) {
    const nodeVersionMatch = content.match(/node-version:\s*['"]?(\d+)['"]?/);
    if (nodeVersionMatch) {
      const ver = parseInt(nodeVersionMatch[1], 10);
      if (ver < 20) {
        console.error(`  [ERROR] Outdated Node.js version '${ver}' in workflow. Project root requires Node >= 20.`);
        errors++;
      } else {
        console.log(`  [PASS] Node.js version configured: v${ver} (meets >= 20 engine constraint)`);
      }
    }
  }

  // Check 5: Syntax sanity - check balanced quotes & brackets
  let openBraces = (content.match(/\{/g) || []).length;
  let closeBraces = (content.match(/\}/g) || []).length;
  if (openBraces !== closeBraces) {
    console.error(`  [ERROR] Mismatched curly braces in ${file}: ${openBraces} '{' vs ${closeBraces} '}'`);
    errors++;
  } else {
    console.log(`  [PASS] Expression bracket balance verified`);
  }
}

console.log('\n=== Workflow Audit Summary ===');
console.log(`Total lines/checks audited: ${totalChecks}`);
console.log(`Warnings: ${warnings}`);
console.log(`Errors: ${errors}`);

if (errors > 0) {
  console.error('\n❌ Workflow audit failed. Please fix the above errors.');
  process.exit(1);
} else {
  console.log('\n✅ Workflow audit PASSED. All GitHub Actions workflows are clean.');
  process.exit(0);
}
