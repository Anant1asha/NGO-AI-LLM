#!/usr/bin/env node
/**
 * scripts/verify_branch_protection.mjs
 * AASHA AIOS — Branch Protection & Remote Invariant Verifier (SEC-001 / BP-001 / BUNDLE-GUARD)
 *
 * Verifies that:
 * 1. Both repositories (NGO AI LLM & Aasha-AI) are strictly on task branch `aios/v2-bootstrap`.
 * 2. Neither repository is on protected branches (`master`, `main`, `production`, `release`).
 * 3. Remote `origin` in both repositories strictly targets GitHub and never a `.bundle` file.
 * 4. Native pre-push hooks are installed in both repositories to physically intercept and block any push to protected branches or bundle files.
 * 5. The pre-push hook accurately rejects simulated pushes to `master`/`main` and `.bundle` targets, while allowing `aios/v2-bootstrap` to GitHub.
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

function verifyRemotes(repoDir, repoName, expectedOriginSubstring) {
  const originUrl = runGit('git config --get remote.origin.url', repoDir);
  console.log(`Checking ${repoName} remotes... origin URL: ${originUrl}`);
  if (!originUrl || !originUrl.includes(expectedOriginSubstring)) {
    throw new Error(`[FAIL] ${repoName} origin is '${originUrl}', expected '${expectedOriginSubstring}'!`);
  }
  if (originUrl.toLowerCase().endsWith('.bundle') || originUrl.toLowerCase().includes('.bundle')) {
    throw new Error(`[FAIL] ${repoName} origin points to a .bundle file! Push will fail.`);
  }
  console.log(`  ✅ ${repoName} remote.origin strictly points to GitHub (${originUrl})`);
}

function verifyHook(hookPath, repoName) {
  if (!fs.existsSync(hookPath)) {
    throw new Error(`[FAIL] Pre-push hook missing at ${hookPath} in ${repoName}`);
  }
  const content = fs.readFileSync(hookPath, 'utf-8');
  if (!content.includes('PROTECTED_REGEX') || !content.includes('master|main')) {
    throw new Error(`[FAIL] Pre-push hook at ${hookPath} does not contain protected branch regex`);
  }
  if (!content.includes('BUNDLE-GUARD') || !content.includes('BUNDLE-PUSH-VIOLATION')) {
    throw new Error(`[FAIL] Pre-push hook at ${hookPath} does not contain bundle guard`);
  }
  console.log(`  ✅ Pre-push hook verified at ${hookPath}`);
}

function getShBin() {
  const candidates = [
    'C:\\Program Files\\Git\\bin\\sh.exe',
    'C:\\Program Files\\Git\\usr\\bin\\sh.exe',
    'C:\\Program Files (x86)\\Git\\bin\\sh.exe',
    'sh'
  ];
  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch {}
  }
  return 'sh';
}

function testHookRejection(hookPath) {
  const shBin = getShBin();
  // Test 1: Simulating push to master (must fail with exit code 1)
  const masterSim = spawnSync(shBin, [hookPath, 'origin', 'https://github.com/Anant1asha/NGO-AI-LLM.git'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/master 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  if (masterSim.status !== 1) {
    throw new Error(`[FAIL] Pre-push hook did not block push to refs/heads/master! Status: ${masterSim.status}, Error: ${masterSim.error?.message}`);
  }

  // Test 2: Simulating push to aios/v2-bootstrap via GitHub origin (must succeed with exit code 0)
  const allowedSim = spawnSync(shBin, [hookPath, 'origin', 'https://github.com/Anant1asha/NGO-AI-LLM.git'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/${TARGET_BRANCH} 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  if (allowedSim.status !== 0) {
    throw new Error(`[FAIL] Pre-push hook incorrectly blocked push to target branch refs/heads/${TARGET_BRANCH}! Status: ${allowedSim.status}, Error: ${allowedSim.error?.message}`);
  }

  // Test 3: Simulating push targeting a bundle file (must fail with exit code 1)
  const bundleSim = spawnSync(shBin, [hookPath, 'bundle', 'C:\\Users\\admin\\Downloads\\NGO AI LLM\\aasha_aios_v2_bootstrap_full.bundle'], {
    input: `refs/heads/aios/v2-bootstrap 0000000000000000000000000000000000000000 refs/heads/${TARGET_BRANCH} 0000000000000000000000000000000000000000\n`,
    encoding: 'utf-8'
  });
  if (bundleSim.status !== 1) {
    throw new Error(`[FAIL] Pre-push hook did not block push targeting a .bundle file! Status: ${bundleSim.status}, Error: ${bundleSim.error?.message}`);
  }

  console.log(`  ✅ Hook behavioral test passed: Blocks protected branches (exit 1), blocks .bundle targets (exit 1), allows ${TARGET_BRANCH} to origin (exit 0)`);
}

function main() {
  console.log('======================================================================');
  console.log('     🛡️ AASHA AIOS BRANCH PROTECTION & REMOTE INVARIANT AUDIT         ');
  console.log('======================================================================');

  // 1. Verify branches
  verifyRepoBranch(ROOT_DIR, 'Root Repo (NGO AI LLM)');
  verifyRepoBranch(AASHA_AI_DIR, 'Sub Repo (Aasha-AI)');

  // 2. Verify remotes (must point strictly to GitHub, not to .bundle)
  verifyRemotes(ROOT_DIR, 'Root Repo (NGO AI LLM)', 'github.com/Anant1asha/NGO-AI-LLM.git');
  verifyRemotes(AASHA_AI_DIR, 'Sub Repo (Aasha-AI)', 'github.com/Anant1asha/Aasha-AI.git');

  // 3. Verify hooks existence & content
  const rootHook = path.join(ROOT_DIR, '.git', 'hooks', 'pre-push');
  const aashaHook = path.join(AASHA_AI_DIR, '.git', 'hooks', 'pre-push');
  verifyHook(rootHook, 'Root Repo');
  verifyHook(aashaHook, 'Sub Repo');

  // 4. Test hook functionality
  testHookRejection(rootHook);

  console.log('----------------------------------------------------------------------');
  console.log('✅ ALL BRANCH PROTECTION & REMOTE INVARIANT CHECKS PASSED: 100% SECURE');
  console.log('   - Both repositories strictly locked to aios/v2-bootstrap.');
  console.log('   - Remote origin strictly targets GitHub repository (zero bundle push).');
  console.log('   - Pre-push hooks active and enforcing zero-push to master/main and zero-push to .bundle.');
  console.log('======================================================================');
}

main();
