import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  LEARN_ARENA_13_CATALOGUE,
  OFFLINE_CHAPTER_CATALOGUE,
  renderLearnCatalogue,
  renderChapterPlayerModal,
  handleChapterMasteryMessage,
  renderCentreLeaderboardCard,
  renderMisconceptionHeatmapCard,
  toggleNcvetPracticalTask,
  exportSignedNcvetPortfolio,
  renderNcvetPortfolioChecklistCard,
  exportCohortMasteryCsv,
  renderPrintableCohortAuditReportHtml
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
  nodeId: 'arena_sec2',
  score: 88,
  wrong: 2
});
assert.equal(masteryRes.handled, true);
assert.equal(masteryRes.awarded, 100);
assert.equal(masteryRes.remediationAssigned, true);
assert.equal(pwaState.coins, 200);
assert.equal(pwaState.syncOutbox.length, 2, 'Must enqueue both mastery pass and diagnostic remediation event when wrong > 0');
assert.equal(pwaState.cohortSummary.misconceptions.length, 1);
assert.equal(pwaState.cohortSummary.misconceptions[0].conceptCode, 'arena_sec2_remediation');
const heatmapHtml = renderMisconceptionHeatmapCard(pwaState.cohortSummary.misconceptions);
assert.ok(heatmapHtml.includes('data-action="launch-remediation-group"'));
assert.ok(heatmapHtml.includes('2 missed in Arena'));

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

  // Verify live /api/sync/quiz-results -> /api/leaderboard round-trip
  await fetch(`${baseUrl}/api/sync/quiz-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      studentId: 'stu_leader_01',
      events: [{ id: 'ev_lb_1', chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS', nodeId: 'arena_full', score: 95 }]
    })
  });
  const lbRes = await fetch(`${baseUrl}/api/leaderboard`);
  assert.equal(lbRes.status, 200);
  const lbBody = await lbRes.json();
  assert.equal(lbBody.status, 'ok');
  assert.ok(lbBody.leaders.some((l) => l.studentId === 'stu_leader_01' && l.lifetimeCoins >= 100));
  const lbHtml = renderCentreLeaderboardCard(lbBody.leaders);
  assert.ok(lbHtml.includes('id="centre-leaderboard-card"'));
  assert.ok(lbHtml.includes('stu_leader_01'));

  // Verify syncing pwaState.syncOutbox to /api/sync/quiz-results populates /api/teacher/misconception-analytics
  await fetch(`${baseUrl}/api/sync/quiz-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ studentId: 'stu_remed_01', events: pwaState.syncOutbox })
  });
  const maRes = await fetch(`${baseUrl}/api/teacher/misconception-analytics`);
  assert.equal(maRes.status, 200);
  const maBody = await maRes.json();
  assert.ok(maBody.hotspots.some((h) => h.chapterId === 'NCERT-G06-MATH-CH07-FRACTIONS' && h.conceptCode === 'arena_sec2_remediation'));
  const serverHeatmapHtml = renderMisconceptionHeatmapCard(maBody.hotspots);
  assert.ok(serverHeatmapHtml.includes('arena_sec2_remediation'));

  // Verify NCVET Practical Skill Portfolio Checklist & GET /api/student/:id/ncvet-portfolio
  const ncvetRes = toggleNcvetPracticalTask(pwaState, 'ncvet_agr_q4301');
  assert.equal(ncvetRes.ok, true);
  assert.equal(ncvetRes.completed, true);
  assert.equal(pwaState.coins, 225);
  const signedPort = exportSignedNcvetPortfolio(pwaState);
  assert.ok(signedPort.signature.startsWith('fnv1a32:'));
  assert.ok(signedPort.qpCodesVerified.includes('AGR/Q4301'));
  const ncvetCardHtml = renderNcvetPortfolioChecklistCard(pwaState);
  assert.ok(ncvetCardHtml.includes('id="ncvet-portfolio-checklist-card"'));
  assert.ok(ncvetCardHtml.includes('AGR/Q4301'));

  await fetch(`${baseUrl}/api/sync/quiz-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ studentId: 'stu_ncvet_01', events: pwaState.syncOutbox })
  });
  const srvPortRes = await fetch(`${baseUrl}/api/student/stu_ncvet_01/ncvet-portfolio`);
  assert.equal(srvPortRes.status, 200);
  const srvPort = await srvPortRes.json();
  assert.equal(srvPort.status, 'ok');
  assert.ok(srvPort.verified_qp_codes.includes('AGR/Q4301'));
  assert.equal(srvPort.portfolio_sha256.length, 64);

  // Verify Offline Cohort CSV & Printable NGO Audit Report Exporter + GET /api/teacher/cohort-export-csv
  const sampleCohort = {
    totalStudents: 2,
    avgMasteryPct: 89.5,
    totalTokensMinted: 250,
    students: [
      { studentId: 'stu_1', name: 'Aarav', masteryPct: 87, tokenBalance: 100 },
      { studentId: 'stu_2', name: 'Diya', masteryPct: 92, tokenBalance: 150 }
    ]
  };
  const csvOut = exportCohortMasteryCsv(sampleCohort, 'CENTER-UP-GN-01');
  assert.ok(csvOut.includes('center_id,student_id,student_name,mastery_pct,token_balance,chapters_passed'));
  assert.ok(csvOut.includes('SUMMARY_TOTAL,All Cohort Learners (2),89.5,250,0'));
  const printHtml = renderPrintableCohortAuditReportHtml(sampleCohort, 'CENTER-UP-GN-01');
  assert.ok(printHtml.includes('Annanth Aasha Foundation — Monthly Cohort Progress'));
  assert.ok(printHtml.includes('Aarav') && printHtml.includes('Diya'));

  const srvCsvRes = await fetch(`${baseUrl}/api/teacher/cohort-export-csv`);
  assert.equal(srvCsvRes.status, 200);
  const srvCsv = await srvCsvRes.json();
  assert.equal(srvCsv.status, 'ok');
  assert.ok(srvCsv.csv.includes('SUMMARY_TOTAL'));
  assert.equal(srvCsv.csv_sha256.length, 64);
} finally {
  await app.close();
}

console.log('✅ PHASE D STUDENT PWA + AASHA STUDIO + CENTRE SERVER LEARN/ARENA LAUNCHER TESTS PASSED!');
