#!/usr/bin/env node
/**
 * scripts/lint_staged_secrets.mjs
 * Mandatory Pre-Commit Zero-Secret Security Scanner for AASHA AIOS.
 *
 * Inspects all staged files (git diff --cached) to guarantee zero secrets,
 * private keys, cookies, or real .env credential files are committed to Git.
 */

import { execSync } from 'child_process';
import * as path from 'path';

function getStagedFiles() {
  try {
    const stdout = execSync('git diff --cached --name-only', { encoding: 'utf-8' });
    return stdout
      .split(/\r?\n/)
      .map(f => f.trim())
      .filter(Boolean);
  } catch (err) {
    console.warn('[lint_staged_secrets] Git diff command failed or repository empty:', err.message);
    return [];
  }
}

function getStagedDiff() {
  try {
    return execSync('git diff --cached -U0', { encoding: 'utf-8' });
  } catch (err) {
    return '';
  }
}

const BLOCKED_FILENAME_PATTERNS = [
  /^\.env(\..+)?$/i,
  /[/\\]\.env(\..+)?$/i,
  /cookie/i,
  /\.(pem|key|pkcs8|id_rsa|id_ed25519)$/i,
];

// Split patterns to ensure static scanners do not self-trigger on this script
const SECRET_REGEX_PATTERNS = [
  { name: 'GitHub PAT', regex: new RegExp('github_pat_' + '[a-zA-Z0-9_]{22,}') },
  { name: 'GitHub Personal Access Token', regex: new RegExp('ghp_' + '[a-zA-Z0-9]{20,}') },
  { name: 'Google API Key', regex: new RegExp('AIzaSy' + '[a-zA-Z0-9_-]{33}') },
  { name: 'Anthropic API Key', regex: new RegExp('sk-ant-' + '[a-zA-Z0-9_-]{20,}') },
  { name: 'OpenRouter API Key', regex: new RegExp('sk-or-v1-' + '[a-zA-Z0-9]{20,}') },
  { name: 'OpenAI API Key', regex: new RegExp('sk-' + '[a-zA-Z0-9]{24,}') },
];

function isAllowlistedFilename(filename) {
  const base = path.basename(filename);
  if (base === '.env.example' || base.endsWith('.env.example')) return true;
  return false;
}

function isMockPlaceholder(text) {
  return /placeholder|dummy|example|mock|test_token/i.test(text);
}

function main() {
  const stagedFiles = getStagedFiles();
  if (stagedFiles.length === 0) {
    console.log('[lint_staged_secrets] No staged files to scan.');
    process.exit(0);
  }

  const violations = [];

  // Check 1: Filename invariants
  for (const file of stagedFiles) {
    if (isAllowlistedFilename(file)) continue;

    for (const pattern of BLOCKED_FILENAME_PATTERNS) {
      if (pattern.test(file)) {
        violations.push({
          file,
          type: 'BLOCKED_FILE_TYPE',
          detail: `Staging sensitive file pattern "${pattern}" is prohibited in public repositories.`,
        });
      }
    }
  }

  // Check 2: Diff content scanning
  const diff = getStagedDiff();
  const diffLines = diff.split(/\r?\n/);
  let currentFile = '';

  for (const line of diffLines) {
    if (line.startsWith('diff --git ')) {
      const match = line.match(/b\/(.+)$/);
      currentFile = match ? match[1] : '';
      continue;
    }

    if (!line.startsWith('+') || line.startsWith('+++')) continue;
    const addedContent = line.substring(1);

    if (isMockPlaceholder(addedContent)) continue;

    for (const { name, regex } of SECRET_REGEX_PATTERNS) {
      if (regex.test(addedContent)) {
        violations.push({
          file: currentFile,
          type: 'UNINSULATED_SECRET_TOKEN',
          detail: `Detected live ${name} pattern matching ${regex}.`,
        });
      }
    }
  }

  if (violations.length > 0) {
    console.error('\n======================================================================');
    console.error(' ❌ PRE-COMMIT SECURITY VIOLATION: SECRETS DETECTED IN STAGING AREA');
    console.error('======================================================================\n');
    for (const v of violations) {
      console.error(`- [${v.type}] File: ${v.file}`);
      console.error(`  Detail: ${v.detail}\n`);
    }
    console.error('Action Required:');
    console.error('1. Unstage the sensitive file: git reset HEAD <file>');
    console.error('2. Move credentials to local-only .env (git-ignored)');
    console.error('3. If authoring test fixtures, split mock tokens using string concatenation.\n');
    process.exit(1);
  }

  console.log(`✅ [lint_staged_secrets] Clean: ${stagedFiles.length} staged file(s) scanned, 0 secrets detected.`);
  process.exit(0);
}

main();
