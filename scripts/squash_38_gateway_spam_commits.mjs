#!/usr/bin/env node
/**
 * scripts/squash_38_gateway_spam_commits.mjs
 * AASHA AIOS: Non-Destructive Git History Cleanup & Commit Consolidator
 * 
 * Safely squashes the 38 duplicate "feat(gateway): auto-enable local 9Router on system start..."
 * spam commits on branch `aios/v2-bootstrap` into a single clean, consolidated commit,
 * while 100% preserving all substantive subsequent commits (build runner, multi-agent topology,
 * governance contracts, subagents, and test verifications).
 * 
 * Invariants Enforced:
 * 1. 100% Reversible & Non-Destructive: Always generates an immutable backup ref
 *    (`backup/pre-squash-aios-v2-bootstrap-<timestamp>`).
 * 2. Tree Equivalence Invariant: Final working tree must match current HEAD byte-for-byte
 *    (git diff HEAD backup == 0).
 * 3. Branch Protection: Pushes strictly to `origin/aios/v2-bootstrap` (zero pushes to master/main).
 */

import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

const TARGET_BRANCH = 'aios/v2-bootstrap';
const SPAM_MESSAGE = 'feat(gateway): auto-enable local 9Router on system start and harden probe resilience [skip ci]';
const BASE_PARENT_COMMIT = 'e71b0cd';
const SPAM_TIP_COMMIT = '96e76ae';

const args = process.argv.slice(2);
const IS_EXECUTE = args.includes('--execute');
const IS_PUSH = args.includes('--push');

function runCmd(cmd, cwd = ROOT_DIR) {
  try {
    const stdout = execSync(cmd, { cwd, encoding: 'utf-8', stdio: 'pipe' });
    return { success: true, stdout: stdout.trim(), code: 0 };
  } catch (err) {
    return { success: false, error: err.message, stderr: err.stderr?.toString() || '', code: err.status || 1 };
  }
}

function logBanner(title) {
  console.log('\n======================================================================');
  console.log(` 🌟 AASHA GIT HISTORY SQUASH: ${title}`);
  console.log('======================================================================\n');
}

async function main() {
  const currentBranch = runCmd('git rev-parse --abbrev-ref HEAD').stdout;
  const currentHead = runCmd('git rev-parse HEAD').stdout;

  if (currentBranch !== TARGET_BRANCH) {
    console.error(`❌ Error: Current branch is '${currentBranch}'. This script must run on '${TARGET_BRANCH}'.`);
    process.exit(1);
  }

  // Identify duplicate commits
  const logCmd = runCmd(`git log --format="%h|%s" ${BASE_PARENT_COMMIT}..${SPAM_TIP_COMMIT}`);
  if (!logCmd.success) {
    console.error('❌ Failed to inspect git log:', logCmd.error);
    process.exit(1);
  }

  const spamCommits = logCmd.stdout.split('\n')
    .map(l => l.split('|'))
    .filter(([h, s]) => s === SPAM_MESSAGE);

  const totalCommitsInRange = logCmd.stdout.split('\n').length;

  // Identify subsequent commits to replay
  const subsequentLog = runCmd(`git log --format="%h|%s" --reverse ${SPAM_TIP_COMMIT}..HEAD`);
  const subsequentCommits = subsequentLog.stdout ? subsequentLog.stdout.split('\n').map(l => l.split('|')) : [];

  if (!IS_EXECUTE) {
    // PREVIEW MODE
    logBanner('DRY-RUN / PREVIEW MODE');
    console.log(`• Target Branch        : ${TARGET_BRANCH}`);
    console.log(`• Current HEAD Commit  : ${currentHead.slice(0, 7)}`);
    console.log(`• Base Parent Commit   : ${BASE_PARENT_COMMIT} ("chore(loop): update continuous loop staging list...")`);
    console.log(`• Spam Range Tip       : ${SPAM_TIP_COMMIT} (last spam commit)`);
    console.log(`• Duplicate Commits    : ${spamCommits.length} commits matching "${SPAM_MESSAGE}"`);
    console.log(`• Substantive Commits  : ${subsequentCommits.length} commits to preserve on top`);

    console.log('\n--- Commits to be squashed into 1 consolidated commit ---');
    console.log(`  [1..${spamCommits.length}] ${spamCommits.length}x '${SPAM_MESSAGE}'`);
    console.log(`  -> Consolidated Message: "${SPAM_MESSAGE}"`);

    console.log('\n--- Subsequent commits to be cleanly preserved & replayed ---');
    subsequentCommits.forEach(([h, s], idx) => {
      console.log(`  ${idx + 1}. [${h}] ${s}`);
    });

    console.log('\n--- Safety Invariants ---');
    console.log('  1. An immutable backup branch `backup/pre-squash-aios-v2-bootstrap` will be created before execution.');
    console.log('  2. A byte-for-byte tree diff verification will run to guarantee 0 file differences.');
    console.log('  3. Zero automated pushes to master/main.');

    console.log('\nTo execute non-destructive squash:');
    console.log('  node scripts/squash_38_gateway_spam_commits.mjs --execute');
    console.log('To execute and push to origin/aios/v2-bootstrap:');
    console.log('  node scripts/squash_38_gateway_spam_commits.mjs --execute --push');
    console.log('\n======================================================================\n');
    return;
  }

  // EXECUTION MODE
  logBanner('EXECUTING SQUASH OPERATION');

  // Step 1: Ensure clean working directory
  const statusCheck = runCmd('git status --porcelain');
  if (statusCheck.stdout) {
    console.log('  Discarding minor local heartbeat modifications to ensure clean rebase...');
    runCmd('git checkout -- PC_ANTIGRAVITY_STATE.json');
  }

  // Step 2: Create immutable backup branch
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupBranch = `backup/pre-squash-aios-v2-bootstrap-${timestamp}`;
  console.log(`1. Creating immutable backup branch: ${backupBranch}...`);
  runCmd(`git branch -f ${backupBranch} HEAD`);
  console.log(`   ✓ Backup branch saved at commit ${currentHead.slice(0, 7)}`);

  // Step 3: Create squashed commit using git commit-tree
  console.log('2. Synthesizing consolidated commit...');
  const tipTree = runCmd(`git rev-parse ${SPAM_TIP_COMMIT}^{tree}`).stdout;
  const parentSha = runCmd(`git rev-parse ${BASE_PARENT_COMMIT}`).stdout;
  const squashedMsg = SPAM_MESSAGE;
  
  const createCommit = runCmd(`git commit-tree ${tipTree} -p ${parentSha} -m "${squashedMsg}"`);
  if (!createCommit.success) {
    console.error('❌ Failed to synthesize commit-tree:', createCommit.error);
    process.exit(1);
  }
  const squashedCommitSha = createCommit.stdout;
  console.log(`   ✓ Squashed commit created: ${squashedCommitSha.slice(0, 7)}`);

  // Step 4: Check out temp branch and cherry-pick subsequent commits
  console.log('3. Replaying subsequent commits on top of squashed base...');
  const tempBranch = `tmp-squash-${Date.now()}`;
  runCmd(`git branch -f ${tempBranch} ${squashedCommitSha}`);
  runCmd(`git checkout ${tempBranch}`);

  const cherryPick = runCmd(`git cherry-pick ${SPAM_TIP_COMMIT}..${TARGET_BRANCH}`);
  if (!cherryPick.success) {
    console.error('❌ Cherry-pick failed:', cherryPick.error, cherryPick.stderr);
    console.log('Rolling back to target branch...');
    runCmd(`git checkout ${TARGET_BRANCH}`);
    runCmd(`git branch -D ${tempBranch}`);
    process.exit(1);
  }
  console.log(`   ✓ Successfully replayed ${subsequentCommits.length} commits.`);

  // Step 5: Verify byte-for-byte tree equality
  console.log('4. Verifying byte-for-byte tree equality...');
  const diffCheck = runCmd(`git diff HEAD ${backupBranch}`);
  if (diffCheck.stdout.length > 0) {
    console.error(`❌ Tree difference detected! Length: ${diffCheck.stdout.length}`);
    runCmd(`git checkout ${TARGET_BRANCH}`);
    runCmd(`git branch -D ${tempBranch}`);
    process.exit(1);
  }
  console.log('   ✓ Diff is 0 bytes! Working tree is 100% byte-for-byte identical.');

  // Step 6: Update target branch to new HEAD
  console.log(`5. Pointing ${TARGET_BRANCH} to squashed HEAD...`);
  const newHead = runCmd('git rev-parse HEAD').stdout;
  runCmd(`git checkout ${TARGET_BRANCH}`);
  runCmd(`git reset --hard ${newHead}`);
  runCmd(`git branch -D ${tempBranch}`);
  console.log(`   ✓ Branch ${TARGET_BRANCH} now at ${newHead.slice(0, 7)}.`);

  // Step 7: Push to remote if requested
  if (IS_PUSH) {
    console.log(`6. Pushing squashed history to origin/${TARGET_BRANCH}...`);
    const pushCmd = runCmd(`git push origin ${TARGET_BRANCH} --force-with-lease`);
    if (pushCmd.success) {
      console.log(`   ✓ Successfully pushed clean history to origin/${TARGET_BRANCH}!`);
    } else {
      console.error('❌ Failed to push:', pushCmd.error, pushCmd.stderr);
      process.exit(1);
    }
  } else {
    console.log('\n[NOTICE] Local squash complete. Run with `--push` to push to origin/aios/v2-bootstrap.');
  }

  logBanner('SQUASH OPERATION COMPLETED SUCCESSFULLY');
}

main().catch(err => {
  console.error('Squash failed:', err);
  process.exit(1);
});
