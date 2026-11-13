#!/usr/bin/env node
/**
 * scripts/verify-gate.mjs
 * Deterministic post-subtask verification gate for the Argon autonomous builder loop.
 *
 * Exit 0 -> gate passed, state/cursor.json atomically advanced (subtask_index += 1).
 * Exit 1 -> gate failed, retry_count incremented, status set to RETRY_NEEDED or
 *           HIBERNATE_REQUIRED once max_retries is reached.
 * Exit 2 -> harness error (missing/unparseable cursor, size ceiling from source truth).
 *
 * Design notes:
 * - Max traversal depth is flattened parent-dir -> size subtotal, so computing the
 *   ceiling on a per-chapter file and on a whole artifact tree does not double count.
 * - The 20 MiB ceiling is a per-ARTIFACT contract (SUPERBRAIN.md 45), so it is tested
 *   per file, never against the summed size of an unrelated output directory.
 * - External URLs are allowed only when the cursor opts in via constraints.allow_external_network.
 * - localhost / 127.0.0.1 / [::1] endpoints are treated as local, not external.
 */

import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = process.cwd();
const CURSOR_PATH = path.join(ROOT, 'state', 'cursor.json');

// Chapter bundles land here; dist/chapters is the observed build output.
const DIST_DIR = process.env.AASHA_VERIFY_DIST_DIR
  ? path.resolve(ROOT, process.env.AASHA_VERIFY_DIST_DIR)
  : path.join(ROOT, 'dist');

const FORBIDDEN_NETWORK_PATTERNS = [
  /\bhttps?:\/\//i,
  /\bfetch\s*\(/,
  /\bXMLHttpRequest\b/,
  /\bnavigator\.sendBeacon\b/,
  /\bWebSocket\s*\(/
];

// A URL is local when its host is loopback; anything else leaves the device.
const LOCAL_HOST = /^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i;
const GROUPED_URL = /\bhttps?:\/\/([^\s"'`<>()\[\]{}\\]+)/gi;

const SCANNED_EXTENSIONS = /\.(html|htm|js|mjs|cjs|css|json|svg|webmanifest)$/i;
const SKIPPED_DIRS = new Set(['node_modules', '.git']);

export function getDirSizeBytes(dirPath) {
  if (!fs.existsSync(dirPath)) return 0;
  let total = 0;
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    const fullPath = path.join(dirPath, entry.name);
    total += entry.isDirectory() ? getDirSizeBytes(fullPath) : fs.statSync(fullPath).size;
  }
  return total;
}

// Per-path subtotals: a directory reports the sum of the files beneath it, a file
// reports its own size. Every path in the tree is a key exactly once, so summing the
// map's values would multi-count nested entries against the tree total — callers must
// filter per entry, never total.
export function getSizeSizes(dirPath, acc = new Map()) {
  if (!fs.existsSync(dirPath)) return acc;
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    if (SKIPPED_DIRS.has(entry.name)) continue;
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      acc.set(fullPath, getDirSizeBytes(fullPath));
      getSizeSizes(fullPath, acc);
    } else {
      acc.set(fullPath, fs.statSync(fullPath).size);
    }
  }
  return acc;
}

export function findExternalUrls(content) {
  const found = new Set();
  for (const match of content.matchAll(GROUPED_URL)) {
    const hostAndPath = match[1];
    if (LOCAL_HOST.test(hostAndPath)) continue;
    if (/^www\.w3\.org\//i.test(hostAndPath)) continue; // XML/SVG namespace identifiers
    found.add(match[0]);
  }
  return [...found];
}

export function scanForNetworkCalls(dirPath, allowExternal, acc = []) {
  if (!fs.existsSync(dirPath)) return acc;
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    if (SKIPPED_DIRS.has(entry.name)) continue;
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      scanForNetworkCalls(fullPath, allowExternal, acc);
      continue;
    }
    if (!SCANNED_EXTENSIONS.test(entry.name)) continue;

    const content = fs.readFileSync(fullPath, 'utf8');
    const relFile = path.relative(ROOT, fullPath);

    if (!allowExternal) {
      for (const url of findExternalUrls(content)) {
        acc.push({ file: relFile, rule: 'EXTERNAL_URL', match: url });
      }
    }
    // Index 0 is the literal-URL regex, already handled by findExternalUrls when external
    // I/O is forbidden. The remaining patterns are runtime network primitives: they name
    // no host, so they are a violation whenever the bundle is meant to stay offline.
    for (let i = 1; i < FORBIDDEN_NETWORK_PATTERNS.length; i += 1) {
      const pattern = FORBIDDEN_NETWORK_PATTERNS[i];
      if (pattern.test(content)) acc.push({ file: relFile, rule: pattern.toString() });
    }
  }
  return acc;
}

function readCursor() {
  if (!fs.existsSync(CURSOR_PATH)) {
    console.error(`[GATE ERROR] Cursor not found at ${CURSOR_PATH}`);
    process.exit(2);
  }
  try {
    return JSON.parse(fs.readFileSync(CURSOR_PATH, 'utf8'));
  } catch (err) {
    console.error(`[GATE ERROR] Cursor is not valid JSON: ${err.message}`);
    process.exit(2);
  }
}

// Replace via a sibling temp file, then rename over the cursor. fs.renameSync is atomic
// over an existing file on POSIX but is not guaranteed to be on every Windows filesystem,
// so a rename failure falls back to an in-place write rather than aborting mid-gate.
function writeCursorAtomic(cursor) {
  const tmpPath = `${CURSOR_PATH}.${process.pid}.tmp`;
  const payload = `${JSON.stringify(cursor, null, 2)}\n`;
  fs.writeFileSync(tmpPath, payload, 'utf8');
  try {
    fs.renameSync(tmpPath, CURSOR_PATH);
  } catch {
    fs.writeFileSync(CURSOR_PATH, payload, 'utf8');
    fs.rmSync(tmpPath, { force: true });
  }
}

function recordFailure(cursor, reason, detail) {
  cursor.retry_count = (cursor.retry_count ?? 0) + 1;
  const maxRetries = cursor.max_retries ?? 3;
  cursor.status = cursor.retry_count >= maxRetries ? 'HIBERNATE_REQUIRED' : 'RETRY_NEEDED';
  cursor.last_failure_reason = reason;
  cursor.last_failure_detail = detail;
  writeCursorAtomic(cursor);
  console.error(
    `[GATE FAIL] ${reason}: ${detail} — retry ${cursor.retry_count}/${maxRetries} -> ${cursor.status}`
  );
  process.exit(1);
}

function runGate() {
  const cursor = readCursor();
  const maxBytes = cursor.constraints?.max_bundle_bytes ?? 20971520;
  // Opt-in, not opt-out: an omitted key must fail closed, as the header documents.
  const allowExternal = cursor.constraints?.allow_external_network === true;

  // "No build output" and "build output under the ceiling" cannot be the same verdict:
  // a size gate with nothing to measure has not been satisfied.
  if (!fs.existsSync(DIST_DIR)) {
    recordFailure(
      cursor,
      'BUILD_OUTPUT_ABSENT',
      `${path.relative(ROOT, DIST_DIR)} does not exist; the bundle ceiling was never measured`
    );
    return;
  }

  // 1. Per-artifact ceiling — no single child bundle may exceed the byte limit.
  const sizes = getSizeSizes(DIST_DIR);
  const oversize = [...sizes.entries()]
    .filter(([, bytes]) => bytes > maxBytes)
    .map(([file, bytes]) => `${path.relative(ROOT, file)}=${bytes}B`);
  if (oversize.length > 0) {
    recordFailure(cursor, 'BUNDLE_SIZE_EXCEEDED', oversize.slice(0, 5).join(', '));
  }

  // 2. Offline-first constraint — no external URL or network primitive in the bundle.
  if (!allowExternal) {
    const violations = scanForNetworkCalls(DIST_DIR, allowExternal);
    if (violations.length > 0) {
      recordFailure(
        cursor,
        'OFFLINE_NETWORK_VIOLATION',
        JSON.stringify(violations.slice(0, 5))
      );
    }
  }

  // 3. Committed state — advance only over a clean tracked tree. A dirty tree at a
  //    RETRY_NEEDED/HIBERNATE_REQUIRED cursor is already-broken work, not new work for
  //    this subtask: keep the original failure reachable instead of masking it.
  const alreadyFailing = cursor.status === 'RETRY_NEEDED' || cursor.status === 'HIBERNATE_REQUIRED';
  let commitHash = null;
  let dirtyTracked = [];
  try {
    commitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf8', cwd: ROOT }).trim();
    dirtyTracked = execSync('git status --porcelain --untracked-files=no', {
      encoding: 'utf8',
      cwd: ROOT
    })
      .split('\n')
      .filter(Boolean);
  } catch {
    recordFailure(cursor, 'GIT_STATE_UNAVAILABLE', 'git rev-parse failed; cannot bind a commit to this gate pass');
  }
  if (dirtyTracked.length > 0 && !alreadyFailing) {
    recordFailure(
      cursor,
      'UNCOMMITTED_STATE',
      `${dirtyTracked.length} tracked file(s) modified: ${dirtyTracked.slice(0, 5).join(' | ')}`
    );
  }

  // A cursor that is already failing must not advance: falling through to step 4 would
  // increment subtask_index, zero retry_count and delete the failure recorded above.
  // The subtask is only satisfied once work has landed on a commit the cursor has not seen.
  if (cursor.last_verified_commit && commitHash === cursor.last_verified_commit) {
    recordFailure(
      cursor,
      'NO_NEW_COMMIT',
      `HEAD is still ${commitHash}, the commit this cursor already verified; nothing new to advance over`
    );
  }

  // 4. Gate passed -> advance the cursor atomically.
  cursor.last_verified_commit = commitHash;
  cursor.subtask_index = (cursor.subtask_index ?? 0) + 1;
  cursor.retry_count = 0;
  cursor.status = 'READY';
  delete cursor.last_failure_reason;
  delete cursor.last_failure_detail;
  writeCursorAtomic(cursor);

  const bundleBytes = getDirSizeBytes(DIST_DIR);
  console.log(
    `[GATE PASS] Phase=${cursor.current_phase} Subtask=${cursor.subtask_index} ` +
      `Commit=${commitHash} Artifacts=${sizes.size} TotalBytes=${bundleBytes}`
  );
}

// Execute only when invoked directly. Importing this module for tests must not read the
// cursor, mutate state/cursor.json, or call process.exit.
const invokedDirectly =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) runGate();
