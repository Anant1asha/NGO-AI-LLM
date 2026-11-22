#!/usr/bin/env node
/**
 * scripts/safe_commit_and_push.mjs
 * Cross-platform atomic safe Git staging, commit, and push engine.
 * Solves Win32 CreateProcess 32k buffer limit ("The filename or extension is too long")
 * by using native pathspecs (git add -u) and Stdin streams across Windows, Linux & Colab.
 */

import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

function run(cmd, options = {}) {
  try {
    return execSync(cmd, { stdio: 'inherit', ...options });
  } catch (err) {
    if (options.allowFailure) return null;
    console.error(`❌ Command failed: ${cmd}`);
    process.exit(1);
  }
}

const args = process.argv.slice(2);
const shouldPush = args.includes('--push');
const filteredArgs = args.filter(a => a !== '--push');
const commitMsg = filteredArgs[0] || 'chore(aios): atomic safe commit';
const specificPaths = filteredArgs.slice(1);

console.log('🛡️ [safe_commit_and_push] Running Windows & Colab safe git workflow...');

// 1. Enforce core.longpaths
run('git config core.longpaths true');

// 2. Disable ignored file warnings
run('git config advice.addIgnoredFile false');

// 3. Purge desktop.ini lock artifacts
if (process.platform === 'win32') {
  run('powershell -NoProfile -Command "Get-ChildItem -Path .git -Filter desktop.ini -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue"', { allowFailure: true });
} else {
  run('find .git -iname "desktop.ini" -delete 2>/dev/null || true', { allowFailure: true });
}

// 4. Safe pathspec staging
console.log('📦 Staging tracked changes via native pathspec...');
run('git add -u');

// 5. Stage specific requested paths if provided
for (const p of specificPaths) {
  console.log(`📦 Staging pathspec: ${p}`);
  run(`git add "${p}"`);
}

// 6. Pre-commit secret scanning
const secretScanner = resolve('scripts/lint_staged_secrets.mjs');
if (existsSync(secretScanner)) {
  console.log('🔍 Running pre-commit secret scan...');
  run(`node "${secretScanner}"`);
}

// 7. Atomic commit
console.log(`📝 Committing: "${commitMsg}"...`);
try {
  run(`git commit -m "${commitMsg.replace(/"/g, '\\"')}"`);
} catch {
  console.log('ℹ️ No staged changes to commit or working tree clean.');
}

// 8. Push if requested
if (shouldPush) {
  const currentBranch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf-8' }).trim();
  console.log(`🚀 Pushing branch '${currentBranch}' strictly to origin...`);
  run(`git push origin "${currentBranch}"`);
}

console.log('✅ [safe_commit_and_push] Completed successfully.');
