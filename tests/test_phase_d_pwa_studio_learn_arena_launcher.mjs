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
  renderPrintableCohortAuditReportHtml,
  exportSignedUsbCohortPack,
  mergeSignedUsbCohortPack,
  buildPhoneticReadAloudDrill,
  speakLleTermOffline,
  renderVocabularyFlashcardDeck,
  registerSharedTabletStudent,
  switchActiveTabletStudent,
  renderSharedTabletStudentSwitcherCard
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

  // Verify Offline USB Cohort Pack Exporter & High-Water-Mark Conflict Merger + Server /api/sync/export-cohort-pack & import-cohort-pack
  const usbPack = exportSignedUsbCohortPack(pwaState, 'CENTER-UP-GN-01');
  assert.equal(usbPack.schemaVersion, 'aasha.usb.cohort.pack.v1');
  assert.ok(usbPack.packSignature.startsWith('fnv1a32:'));

  const targetTabletState = {
    studentId: 'stu_tablet_02',
    studentName: 'Meera',
    coins: 100,
    progress: {
      'NCERT-G06-MATH-CH07-FRACTIONS': { completed: true, scorePct: 70 }
    },
    ncvetCompletedTasks: ['ncvet_ssc_q0101'],
    cohortSummary: {
      students: [{ studentId: 'stu_local_01', name: 'Aasha Scholar', masteryPct: 65, tokenBalance: 100, chaptersPassed: 1 }]
    }
  };
  const mergeRes = mergeSignedUsbCohortPack(targetTabletState, usbPack);
  assert.equal(mergeRes.ok, true);
  assert.equal(targetTabletState.progress['NCERT-G06-MATH-CH07-FRACTIONS'].scorePct, 88);
  assert.ok(targetTabletState.ncvetCompletedTasks.includes('ncvet_agr_q4301'));
  assert.ok(targetTabletState.ncvetCompletedTasks.includes('ncvet_ssc_q0101'));
  const mergedScholar = targetTabletState.cohortSummary.students.find((s) => s.studentId === 'stu_local_01');
  assert.equal(mergedScholar.tokenBalance, 225);

  // Tamper check
  const tamperedPack = { ...usbPack, packSignature: 'fnv1a32:00000000' };
  const tamperRes = mergeSignedUsbCohortPack(targetTabletState, tamperedPack);
  assert.equal(tamperRes.ok, false);
  assert.equal(tamperRes.error, 'USB_PACK_SIGNATURE_MISMATCH');

  const srvExportRes = await fetch(`${baseUrl}/api/sync/export-cohort-pack`);
  assert.equal(srvExportRes.status, 200);
  const srvPack = await srvExportRes.json();
  assert.equal(srvPack.schemaVersion, 'aasha.usb.cohort.pack.v1');
  assert.equal(srvPack.pack_sha256.length, 64);

  const srvImportRes = await fetch(`${baseUrl}/api/sync/import-cohort-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schemaVersion: 'aasha.usb.cohort.pack.v1',
      centerId: 'CENTER-UP-GN-02',
      students: [{ studentId: 'stu_usb_remote_01', name: 'Kabir', tokenBalance: 175, lifetimeCoins: 175 }],
      masteryEvents: [{ studentId: 'stu_usb_remote_01', chapterId: 'NCERT-G09-SCI-CH08-FORCE-MOTION', nodeId: 'arena_full', score: 94, passed: 1 }]
    })
  });
  assert.equal(srvImportRes.status, 200);
  const srvImportBody = await srvImportRes.json();
  assert.equal(srvImportBody.status, 'merged');
  assert.equal(srvImportBody.students_upserted, 1);
  assert.equal(srvImportBody.mastery_records_merged, 1);
  assert.equal(srvImportBody.net_coins_added, 175);

  // Replay idempotency check (high-water-mark should add 0 coins on identical replay)
  const srvImportReplay = await fetch(`${baseUrl}/api/sync/import-cohort-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schemaVersion: 'aasha.usb.cohort.pack.v1',
      centerId: 'CENTER-UP-GN-02',
      students: [{ studentId: 'stu_usb_remote_01', name: 'Kabir', tokenBalance: 175, lifetimeCoins: 175 }],
      masteryEvents: [{ studentId: 'stu_usb_remote_01', chapterId: 'NCERT-G09-SCI-CH08-FORCE-MOTION', nodeId: 'arena_full', score: 94, passed: 1 }]
    })
  });
  const srvReplayBody = await srvImportReplay.json();
  assert.equal(srvReplayBody.net_coins_added, 0);
  assert.equal(srvReplayBody.mastery_records_merged, 0);

  // Verify Offline Student Voice Phonetic Read-Aloud & LLE Pronunciation Drill + Server /api/catalogue/lle-phonetic-drill
  const drill = buildPhoneticReadAloudDrill('photosynthesis');
  assert.equal(drill.termEn, 'photosynthesis');
  assert.equal(drill.phoneticHi, 'फ़ोटोसिंथेसिस');
  assert.equal(drill.syllablesHi, 'फ़ो-टो-सिं-थे-सिस');
  assert.ok(drill.bilingualPrompt.includes('फ़ो-टो-सिं-थे-सिस'));

  const spokenEvents = [];
  const mockSynth = {
    cancel() {},
    speak(u) { spokenEvents.push(u); }
  };
  globalThis.SpeechSynthesisUtterance = class {
    constructor(text) { this.text = text; this.lang = ''; this.rate = 1; }
  };
  const speakRes = speakLleTermOffline({ termEn: 'denominator' }, mockSynth);
  assert.equal(speakRes.ok, true);
  assert.equal(speakRes.spoken, true);
  assert.equal(spokenEvents.length, 2);
  assert.equal(spokenEvents[0].lang, 'en-IN');
  assert.equal(spokenEvents[1].lang, 'hi-IN');

  const flashDeckHtml = renderVocabularyFlashcardDeck();
  assert.ok(flashDeckHtml.includes('data-action="speak-lle-word"'));
  assert.ok(flashDeckHtml.includes('मो-नो-मि-यल'));

  const srvLleRes = await fetch(`${baseUrl}/api/catalogue/lle-phonetic-drill`);
  assert.equal(srvLleRes.status, 200);
  const srvLle = await srvLleRes.json();
  assert.equal(srvLle.status, 'ok');
  assert.equal(srvLle.wm2_count, 1557);
  assert.equal(srvLle.ph_count, 763);
  assert.equal(srvLle.pack_sha256.length, 64);

  // Verify Shared-Tablet Multi-Student Profile Switcher & Session Isolation + Server /api/student/register-local-profile
  const regRes = registerSharedTabletStudent(pwaState, {
    studentId: 'stu_shared_02',
    studentName: 'Riya Verma',
    grade: 9,
    pin: '2468',
    initialCoins: 120
  });
  assert.equal(regRes.ok, true);
  assert.ok(regRes.profileCount >= 2);

  // Wrong PIN must reject profile switch
  const badPinSwitch = switchActiveTabletStudent(pwaState, 'stu_shared_02', '0000');
  assert.equal(badPinSwitch.ok, false);
  assert.equal(badPinSwitch.error, 'INVALID_STUDENT_PIN');

  // Correct PIN switches to Riya Verma with isolated state (0 chapters completed, 120 coins)
  const goodSwitch = switchActiveTabletStudent(pwaState, 'stu_shared_02', '2468');
  assert.equal(goodSwitch.ok, true);
  assert.equal(pwaState.studentId, 'stu_shared_02');
  assert.equal(pwaState.studentName, 'Riya Verma');
  assert.equal(pwaState.coins, 120);
  assert.equal(Object.keys(pwaState.progress).length, 0);
  assert.equal(pwaState.ncvetCompletedTasks.length, 0);

  // Switch back to original scholar and verify zero session loss (coins=225, NCVET AGR/Q4301 preserved)
  const backSwitch = switchActiveTabletStudent(pwaState, 'stu_local_01');
  assert.equal(backSwitch.ok, true);
  assert.equal(pwaState.studentId, 'stu_local_01');
  assert.equal(pwaState.coins, 225);
  assert.ok(pwaState.ncvetCompletedTasks.includes('ncvet_agr_q4301'));

  const switcherHtml = renderSharedTabletStudentSwitcherCard(pwaState);
  assert.ok(switcherHtml.includes('id="shared-tablet-student-switcher-card"'));
  assert.ok(switcherHtml.includes('Riya Verma'));

  const srvRegRes = await fetch(`${baseUrl}/api/student/register-local-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ studentId: 'stu_shared_02', studentName: 'Riya Verma', grade: 9, initialCoins: 120 })
  });
  assert.equal(srvRegRes.status, 200);
  const srvRegBody = await srvRegRes.json();
  assert.equal(srvRegBody.status, 'ok');
  assert.equal(srvRegBody.coinsBalance, 120);
  assert.equal(srvRegBody.session_isolated, true);

  const srvRosterRes = await fetch(`${baseUrl}/api/student/shared-tablet-profiles`);
  assert.equal(srvRosterRes.status, 200);
  const srvRoster = await srvRosterRes.json();
  assert.equal(srvRoster.status, 'ok');
  assert.ok(srvRoster.profiles.some((p) => p.studentId === 'stu_shared_02' && p.studentName === 'Riya Verma'));
} finally {
  await app.close();
}

console.log('✅ PHASE D STUDENT PWA + AASHA STUDIO + CENTRE SERVER LEARN/ARENA LAUNCHER TESTS PASSED!');
