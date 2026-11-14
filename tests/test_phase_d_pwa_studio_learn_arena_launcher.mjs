import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  LEARN_ARENA_13_CATALOGUE,
  OFFLINE_CHAPTER_CATALOGUE,
  renderLearnCatalogue,
  renderChapterPlayerModal,
  handleChapterMasteryMessage
} from '../Aasha-AI/aasha-student-pwa/src/app.js';

// 1. Verify Student PWA Learn & Arena Dual Catalogue & Modal Switching
assert.equal(LEARN_ARENA_13_CATALOGUE.length, 13, 'Must expose all 13 canonical NCERT + NCVET Learn/Arena pairs');
assert.equal(OFFLINE_CHAPTER_CATALOGUE.length, 26, 'Must preserve 26-chapter OFFLINE_CHAPTER_CATALOGUE contract');

const catalogueHtml = renderLearnCatalogue({ progress: {}, activeSubject: 'ALL', activeGrade: 'ALL', searchQuery: '' });
assert.ok(catalogueHtml.includes('data-action="launch-chapter"'), 'Catalogue must render Learn launch button');
assert.ok(catalogueHtml.includes('data-action="launch-arena"'), 'Catalogue must render Arena launch button');
assert.ok(catalogueHtml.includes('⚔️ Aasha Arena / अखाड़ा'), 'Catalogue must include bilingual Arena button label');

const learnModal = renderChapterPlayerModal('NCERT-G06-MATH-CH07-FRACTIONS', 'learn');
assert.ok(learnModal.includes('data-active-mode="learn"'), 'Learn modal must mark active mode = learn');
assert.ok(learnModal.includes('/chapters/NCERT-G06-MATH-CH07-FRACTIONS_Learning.html'), 'Learn modal must mount _Learning.html');
assert.ok(learnModal.includes('⚔️ Switch to Arena'), 'Learn modal must provide Switch to Arena toggle');

const arenaModal = renderChapterPlayerModal('NCERT-G06-MATH-CH07-FRACTIONS', 'arena');
assert.ok(arenaModal.includes('data-active-mode="arena"'), 'Arena modal must mark active mode = arena');
assert.ok(arenaModal.includes('/chapters/NCERT-G06-MATH-CH07-FRACTIONS_Arena.html'), 'Arena modal must mount _Arena.html');
assert.ok(arenaModal.includes('📖 Switch to Learn'), 'Arena modal must provide Switch to Learn toggle');

// 2. Verify Mastery postMessage awards Aasha Coins & enqueues Sync Outbox event
const pwaState = { coins: 100, progress: {}, syncOutbox: [] };
const masteryRes = handleChapterMasteryMessage(pwaState, {
  type: 'TEAS_CHAPTER_MASTERY',
  chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS',
  nodeId: 'arena_boss',
  score: 92
});
assert.equal(masteryRes.handled, true);
assert.equal(masteryRes.awarded, 100);
assert.equal(pwaState.coins, 200);
assert.equal(pwaState.syncOutbox.length, 1);

// 3. Verify Centre Server GET /api/catalogue/learn-arena-modules live endpoint
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aasha-phase-d-http-'));
process.env.AASHA_DB_PATH = path.join(tmpDir, 'test_aasha_local.db');
const { buildServer } = await import('../Aasha-AI/server/server.js');
const app = buildServer();
const baseUrl = await app.listen({ port: 0, host: '127.0.0.1' });

try {
  const res = await fetch(`${baseUrl}/api/catalogue/learn-arena-modules`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, 'ok');
  assert.equal(body.chapters_compiled, 13);
  assert.equal(body.total_html5_modules_generated, 26);
  assert.equal(body.total_qa_checks_passed, '871/871');
  assert.equal(body.under_20mib, true);
  assert.equal(body.zero_external_urls, true);
  assert.equal(body.modules.length, 13);
} finally {
  await app.close();
}

console.log('✅ PHASE D STUDENT PWA + AASHA STUDIO + CENTRE SERVER LEARN/ARENA LAUNCHER TESTS PASSED!');
