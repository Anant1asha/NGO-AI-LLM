import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  CACHE_VERSION,
  CERTIFIED_CHAPTER_BUNDLES,
  LEARN_ARENA_26_BUNDLES,
  PRECACHE_ASSETS
} from '../Aasha-AI/aasha-student-pwa/sw.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

function sha256File(fp) {
  return crypto.createHash('sha256').update(fs.readFileSync(fp)).digest('hex');
}

// 1. Verify Service Worker exports & precache list
assert.equal(CACHE_VERSION, 'aasha-student-pwa-v2.2');
assert.equal(CERTIFIED_CHAPTER_BUNDLES.length, 26);
assert.equal(LEARN_ARENA_26_BUNDLES.length, 26);
assert.ok(PRECACHE_ASSETS.includes('/teas_content.db.gz'));
assert.ok(PRECACHE_ASSETS.includes('/api/catalogue/learn-arena-modules'));
for (const url of LEARN_ARENA_26_BUNDLES) {
  assert.ok(PRECACHE_ASSETS.includes(url), `Missing ${url} in PRECACHE_ASSETS`);
}

// 2. Verify public/teas_content.db.gz matches pipeline teas_content.db.gz byte-for-byte
const pipelineGz = path.join(repoRoot, 'Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/teas_content.db.gz');
const publicGz = path.join(repoRoot, 'Aasha-AI/aasha-student-pwa/public/teas_content.db.gz');
assert.equal(sha256File(publicGz), sha256File(pipelineGz), 'public/teas_content.db.gz must match pipeline teas_content.db.gz');

// 3. Verify every asset in sw_cache_manifest.json exists on disk, matches SHA-256, and is < 20 MiB
const manifestPath = path.join(repoRoot, 'Aasha-AI/aasha-student-pwa/src/sw_cache_manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
assert.equal(manifest.cache_version, 'aasha-student-pwa-v2.2');
assert.equal(manifest.learn_arena_count, 26);
assert.equal(manifest.under_20mib_ceiling, true);
assert.equal(manifest.zero_external_urls, true);
assert.ok(manifest.assets.length >= 53, 'Expected at least 53 precached assets');

for (const asset of manifest.assets) {
  const fullPath = path.join(repoRoot, asset.rel_path);
  assert.ok(fs.existsSync(fullPath), `Missing precache asset on disk: ${asset.rel_path}`);
  const stat = fs.statSync(fullPath);
  assert.equal(stat.size, asset.size_bytes, `Size mismatch for ${asset.rel_path}`);
  if (asset.rel_path.endsWith('.html')) {
    assert.ok(stat.size < 20 * 1024 * 1024, `Child HTML exceeds 20 MiB ceiling: ${asset.rel_path}`);
  }
  assert.equal(sha256File(fullPath), asset.sha256, `SHA-256 mismatch for ${asset.rel_path}`);
}

const sortedHashes = [...manifest.assets]
  .sort((a, b) => (a.rel_path < b.rel_path ? -1 : a.rel_path > b.rel_path ? 1 : 0))
  .map((a) => a.sha256)
  .join('');
const expectedMerkle = crypto.createHash('sha256').update(sortedHashes, 'utf-8').digest('hex');
assert.equal(manifest.merkle_root_sha256, expectedMerkle, 'Merkle root SHA-256 must match sorted leaf digests');

console.log(`✅ PHASE F/G OFFLINE PWA SERVICE WORKER PRECACHE & MERKLE VERIFICATION PASSED (${manifest.assets.length} assets, Merkle=${expectedMerkle.slice(0, 16)}...)!`);
