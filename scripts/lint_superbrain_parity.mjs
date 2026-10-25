#!/usr/bin/env node
/**
 * @file lint_superbrain_parity.mjs
 * @description Validates rule parity and schema integrity between .agents/rules/ and .superbrain/rules/,
 * enforces YAML frontmatter standards, audits SUPERBRAIN.md invariant retention, and guarantees zero secret leakage.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

console.log('=== Superbrain Instruction Architecture & Rule Parity Audit ===\n');

let errorCount = 0;
let checkCount = 0;

function reportPass(message) {
  checkCount++;
  console.log(`  [PASS] ${message}`);
}

function reportFail(message) {
  checkCount++;
  errorCount++;
  console.error(`  [FAIL] ${message}`);
}

// ---------------------------------------------------------------------------
// 1. Rule Parity (1:1 Mapping between .agents/rules and .superbrain/rules)
// ---------------------------------------------------------------------------
console.log('--- 1. Rule Parity Check (.agents/rules <-> .superbrain/rules) ---');

const agentsRulesDir = path.join(repoRoot, '.agents', 'rules');
const superbrainRulesDir = path.join(repoRoot, '.superbrain', 'rules');

if (!fs.existsSync(agentsRulesDir)) {
  reportFail(`.agents/rules directory missing at: ${agentsRulesDir}`);
} else if (!fs.existsSync(superbrainRulesDir)) {
  reportFail(`.superbrain/rules directory missing at: ${superbrainRulesDir}`);
} else {
  const agentsFiles = fs.readdirSync(agentsRulesDir).filter(f => f.endsWith('.md'));
  const superbrainFiles = fs.readdirSync(superbrainRulesDir).filter(f => f.endsWith('.md'));

  // Map snake_case to kebab-case
  for (const aFile of agentsFiles) {
    const expectedSuperbrain = aFile.replace(/_/g, '-');
    if (superbrainFiles.includes(expectedSuperbrain)) {
      reportPass(`.agents/rules/${aFile} <-> .superbrain/rules/${expectedSuperbrain}`);
    } else {
      reportFail(`Missing .superbrain/rules/${expectedSuperbrain} for .agents/rules/${aFile}`);
    }
  }

  // Reverse mapping check
  for (const sFile of superbrainFiles) {
    const expectedAgent = sFile.replace(/-/g, '_');
    if (agentsFiles.includes(expectedAgent) || agentsFiles.includes(sFile)) {
      reportPass(`.superbrain/rules/${sFile} maps to tracked agent rule`);
    } else {
      reportFail(`Unmapped .superbrain/rules/${sFile} has no counterpart in .agents/rules/`);
    }
  }
}

// ---------------------------------------------------------------------------
// 2. YAML Frontmatter Schema Validation in .superbrain/rules/*.md
// ---------------------------------------------------------------------------
console.log('\n--- 2. YAML Frontmatter Schema Validation (.superbrain/rules/*.md) ---');

if (fs.existsSync(superbrainRulesDir)) {
  const superbrainFiles = fs.readdirSync(superbrainRulesDir).filter(f => f.endsWith('.md'));

  for (const file of superbrainFiles) {
    const filePath = path.join(superbrainRulesDir, file);
    const content = fs.readFileSync(filePath, 'utf8');

    if (!content.startsWith('---')) {
      reportFail(`${file}: Missing opening YAML frontmatter delimiter (---)`);
      continue;
    }

    const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!match) {
      reportFail(`${file}: Malformed or unclosed YAML frontmatter`);
      continue;
    }

    const frontmatter = match[1];

    // Validate 'description:'
    if (!/^description:\s*.+/m.test(frontmatter)) {
      reportFail(`${file}: Frontmatter missing non-empty 'description' field`);
    } else {
      reportPass(`${file}: Valid 'description' defined`);
    }

    // Validate 'alwaysApply:' or 'globs:'
    const hasAlwaysApply = /^alwaysApply:\s*(true|false)/m.test(frontmatter);
    const hasGlobs = /^globs:\s*.+/m.test(frontmatter);

    if (!hasAlwaysApply && !hasGlobs) {
      reportFail(`${file}: Frontmatter must define either 'alwaysApply: true|false' or 'globs'`);
    } else {
      reportPass(`${file}: Execution trigger configured (${hasAlwaysApply ? 'alwaysApply' : 'globs'})`);
    }
  }
}

// ---------------------------------------------------------------------------
// 3. SUPERBRAIN.md Core Invariant Cross-Check
// ---------------------------------------------------------------------------
console.log('\n--- 3. SUPERBRAIN.md Core Invariant Audit ---');

const superbrainPath = path.join(repoRoot, 'SUPERBRAIN.md');

if (!fs.existsSync(superbrainPath)) {
  reportFail(`SUPERBRAIN.md missing at root: ${superbrainPath}`);
} else {
  const sbContent = fs.readFileSync(superbrainPath, 'utf8');

  // Invariant A: Ecosystem Identity
  if (sbContent.includes('does not build, pre-train, or fine-tune large language models') ||
      sbContent.includes('Autonomous AI Agent Ecosystem')) {
    reportPass('Ecosystem Identity Invariant preserved');
  } else {
    reportFail('SUPERBRAIN.md lacks explicit Ecosystem Identity Invariant statement');
  }

  // Invariant B: Zero-Token Bleed Routing Hierarchy
  if (sbContent.includes('Tier 1') && sbContent.includes('OpenRouter') && sbContent.includes('Tier 3') && sbContent.includes('reserve')) {
    reportPass('Zero-Token Bleed & 3-Tier cascade invariant preserved');
  } else {
    reportFail('SUPERBRAIN.md lacks complete 3-Tier Anti-Bleed routing rules');
  }

  // Invariant C: Serena Local Memory Mandate
  if (sbContent.includes('Serena MCP') && sbContent.includes('.serena/memories/')) {
    reportPass('Serena MCP Default Local Memory Mandate preserved');
  } else {
    reportFail('SUPERBRAIN.md lacks Serena MCP memory specifications');
  }

  // Invariant D: Safe File Operations
  if (sbContent.includes('Safe file operations') || sbContent.includes('forbidden from executing destructive shell commands')) {
    reportPass('Safe File Operations policy preserved');
  } else {
    reportFail('SUPERBRAIN.md lacks Safe File Operations guardrails');
  }
}

// ---------------------------------------------------------------------------
// 4. Zero-Secret Static Exposure Scan
// ---------------------------------------------------------------------------
console.log('\n--- 4. Zero-Secret Static Exposure Scan ---');

// Split literal prefixes to prevent triggering static scanners
const secretPatterns = [
  new RegExp('(?:' + 'sk-or-v1-' + '[a-zA-Z0-9]{20,})', 'i'),
  new RegExp('(?:' + 'github_pat_' + '[a-zA-Z0-9_]{20,})', 'i'),
  new RegExp('(?:' + 'ghp_' + '[a-zA-Z0-9]{20,})', 'i'),
  new RegExp('(?:' + 'AIzaSy' + '[a-zA-Z0-9_-]{20,})', 'i'),
  new RegExp('-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----', 'i')
];

const filesToScan = [
  superbrainPath,
  path.join(repoRoot, '.markdownlint-cli2.jsonc')
];

if (fs.existsSync(superbrainRulesDir)) {
  const sbRules = fs.readdirSync(superbrainRulesDir).map(f => path.join(superbrainRulesDir, f));
  filesToScan.push(...sbRules);
}

for (const fPath of filesToScan) {
  if (!fs.existsSync(fPath)) continue;
  const relName = path.relative(repoRoot, fPath).replace(/\\/g, '/');
  const fileContent = fs.readFileSync(fPath, 'utf8');

  let fileHasSecret = false;
  for (const pattern of secretPatterns) {
    if (pattern.test(fileContent)) {
      reportFail(`Potential secret or token pattern detected in: ${relName}`);
      fileHasSecret = true;
      break;
    }
  }

  if (!fileHasSecret) {
    reportPass(`Clean secret scan: ${relName}`);
  }
}

// ---------------------------------------------------------------------------
// Summary & Exit Code
// ---------------------------------------------------------------------------
console.log('\n=== Audit Summary ===');
console.log(`Total checks: ${checkCount}`);
console.log(`Passed: ${checkCount - errorCount}`);
console.log(`Failed: ${errorCount}`);

if (errorCount > 0) {
  console.error('\n❌ Superbrain parity and schema audit FAILED.');
  process.exit(1);
} else {
  console.log('\n✅ Superbrain instruction architecture & parity audit PASSED.');
  process.exit(0);
}
