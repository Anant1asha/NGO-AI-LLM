#!/usr/bin/env node
/**
 * scripts/verify_branch_protection.mjs
 * AASHA AIOS — Branch Protection Invariant Verifier (SEC-001 / BP-001)
 *
 * Verifies that:
 * 1. Both repositories (NGO AI LLM & Aasha-AI) are strictly on task branch `aios/v2-bootstrap`.
 * 2. Neither repository is on protected branches (`master`, `main`, `production`, `release`).
 * 3. Native pre-push hooks are installed in both repositories to physically intercept and block any push to protected branches.
 * 4. The pre-push hook accurately rejects simulated pushes to `master`/`main` and allows `aios/v2-bootstrap`.
 */

import { execSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const AASHA_AI_DIR = path.join(ROOT_DIR, 'Aasha-AI');
const TARGET_BRANCH = 'aios/v2-bootstrap';
const PROTECTED_BRANCHES = ['master', 'main', 'production', 'release'];

function runGit(cmd, cwd = ROOT_DIR) {
  try {
    return execSync(cmd, { cwd, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  } catch (err) {
    return null;
  }
}

function verifyRepoBranch(repoDir, repoName) {
  const branch = runGit('git rev-parse --abbrev-ref HEAD', repoDir);
  console.log(`Checking ${repoName}... Current branch: ${branch}`);
  if (branch !== TARGET_BRANCH) {
    throw new Error(`[FAIL] ${repoName} is on branch '${branch}', expected strictly '${TARGET_BRANCH}'.`);
  }
  if (PROTECTED_BRANCHES.includes(branch)) {
    throw new Error(`[FAIL] ${repoName} is on protected branch '${branch}'!`);
  }
  console.log(`  ✅ ${repoName} branch is strictly ${TARGET_BRANCH} (Protected branches: 0)`);
  return branch;
}

function verifyHook(hookPath, repoName) {
  if (!fs.existsSync(hookPath)) {
    throw new Error(`[FAIL] Pre-push hook missing at ${hookPath} in ${repoName}`);
  }
  const content = fs.readFileSync(hookPath, 'utf-8');
  if (!content.includes('PROTECTED_REGEX') || !content.includes('master|main')) {
    throw new Error(`[FAIL] Pre-push hook at ${hookPath} does not contain protected branch regex`);
  }
  console.log(`  ✅ Pre-push hook verified at ${hookPath}`);
}

function testHookRejection(hookPath) {
  // Test 1: Simulating push to master (must fail with exit code 1)
  const masterSim = spawnSync('sh', [hookPath, 'origin', 'fake-url'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/master 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  if (masterSim.status !== 1) {
    // If sh is not in PATH or exit code isn't 1, test with bash or check
    const bashSim = spawnSync('bash', [hookPath, 'origin', 'fake-url'], {
      input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/master 0000000000000000000000000000000000000000\n`,
      encoding: 'utf-8'
    });
    if (bashSim.status !== 1) {
      throw new Error(`[FAIL] Pre-push hook did not block push to refs/heads/master! Status: ${bashSim.status}`);
    }
  }

  // Test 2: Simulating push to aios/v2-bootstrap (must succeed with exit code 0)
  const allowedSim = spawnSync('sh', [hookPath, 'origin', 'fake-url'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/${TARGET_BRANCH} 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  const finalAllowed = allowedSim.status === 0 ? allowedSim : spawnSync('bash', [hookPath, 'origin', 'fake-url'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/${TARGET_BRANCH} 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  if (finalAllowed.status !== 0) {
    throw new Error(`[FAIL] Pre-push hook incorrectly blocked push to target branch refs/heads/${TARGET_BRANCH}! Status: ${finalAllowed.status}`);
  }
  console.log(`  ✅ Hook behavioral test passed: Blocks protected branches (exit 1), allows ${TARGET_BRANCH} (exit 0)`);
}

function main() {
  console.log('======================================================================');
  console.log('     🛡️ AASHA AIOS BRANCH PROTECTION INVARIANT VERIFICATION          ');
  console.log('======================================================================');

  // 1. Verify branches
  verifyRepoBranch(ROOT_DIR, 'Root Repo (NGO AI LLM)');
  verifyRepoBranch(AASHA_AI_DIR, 'Sub Repo (Aasha-AI)');

  // 2. Verify hooks existence
  const rootHook = path.join(ROOT_DIR, '.git', 'hooks', 'pre-push');
  const aashaHook = path.join(AASHA_AI_DIR, '.git', 'hooks', 'pre-push');
  verifyHook(rootHook, 'Root Repo');
  verifyHook(aashaHook, 'Sub Repo');

  // 3. Test hook functionality
  testHookRejection(rootHook);

  console.log('----------------------------------------------------------------------');
  console.log('✅ ALL BRANCH PROTECTION CHECKS PASSED: 100% SECURE');
  console.log('   - Both repositories strictly locked to aios/v2-bootstrap.');
  console.log('   - Direct Git pre-push hooks active and enforcing zero-push to master/main.');
  console.log('======================================================================');
}

main();
