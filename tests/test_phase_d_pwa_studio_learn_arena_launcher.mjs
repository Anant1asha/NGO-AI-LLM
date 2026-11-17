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
  renderSharedTabletStudentSwitcherCard,
  recordDailyLearningStreak,
  completeCommunitySevaChallenge,
  renderDailyStreakAndSevaCard,
  generateChapterLessonPlanHtml,
  renderTeacherLessonPlanCatalogCard,
  renderFacilitatorRestockModal,
  restockStoreInventoryItem,
  exportStoreInventoryAuditLedger,
  validateNonSpoilerMisconception,
  authorCustomBilingualQuestion,
  renderTeacherCustomQuizBuilderCard,
  evaluateLowRamTabletBudget,
  renderLowRamTabletDiagnosticsCard,
  appendDonorImpactLedgerEntry,
  verifyImpactLedgerChain,
  exportCsrImpactAuditPack,
  renderDonorImpactLedgerCard,
  exportGoldenMasterDeploymentKit,
  renderGoldenMasterReleaseCard,
  generateCohortParentSmsOutboxBatch,
  renderParentSmsDigestOutboxCard,
  matchPeerStudyBuddies,
  renderPeerStudyBuddyMatchmakerCard
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

  // Verify Daily Learning Streak & Bilingual Community Seva Challenge Tracker + Server /api/student/:id/seva-challenge
  const streakRes1 = recordDailyLearningStreak(pwaState, '2026-11-16');
  assert.equal(streakRes1.ok, true);
  assert.equal(streakRes1.bonusAwarded, 15);
  assert.equal(streakRes1.streakDays, 2);

  // Same-day check-in must be idempotent (0 bonus coins)
  const streakResSameDay = recordDailyLearningStreak(pwaState, '2026-11-16');
  assert.equal(streakResSameDay.bonusAwarded, 0);
  assert.equal(streakResSameDay.alreadyCheckedIn, true);

  // Next consecutive day increments streak to 3
  const streakRes2 = recordDailyLearningStreak(pwaState, '2026-11-17');
  assert.equal(streakRes2.streakDays, 3);
  assert.equal(streakRes2.bonusAwarded, 15);

  const sevaRes = completeCommunitySevaChallenge(pwaState, 'seva_jal_audit');
  assert.equal(sevaRes.ok, true);
  assert.equal(sevaRes.rewardCoins, 30);
  assert.equal(sevaRes.completedCount, 1);

  const sevaCardHtml = renderDailyStreakAndSevaCard(pwaState);
  assert.ok(sevaCardHtml.includes('id="daily-streak-seva-card"'));
  assert.ok(sevaCardHtml.includes('3-Day Learning Streak'));

  const srvSevaPost1 = await fetch(`${baseUrl}/api/student/stu_local_01/seva-challenge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challengeId: 'seva_jal_audit', rewardCoins: 30 })
  });
  assert.equal(srvSevaPost1.status, 200);
  const srvSevaBody1 = await srvSevaPost1.json();
  assert.equal(srvSevaBody1.coinsAwarded, 30);

  // Idempotent replay check
  const srvSevaPost2 = await fetch(`${baseUrl}/api/student/stu_local_01/seva-challenge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challengeId: 'seva_jal_audit', rewardCoins: 30 })
  });
  const srvSevaBody2 = await srvSevaPost2.json();
  assert.equal(srvSevaBody2.coinsAwarded, 0);

  const srvSevaGet = await fetch(`${baseUrl}/api/student/stu_local_01/seva-challenges`);
  assert.equal(srvSevaGet.status, 200);
  const srvSevaList = await srvSevaGet.json();
  assert.equal(srvSevaList.completedCount, 1);
  assert.equal(srvSevaList.seva_ledger_sha256.length, 64);

  // Verify Offline 40-Minute Bilingual Classroom Lesson Plan Generator + Server /api/teacher/lesson-plan/:chapterId
  const lpHtml = generateChapterLessonPlanHtml('NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW');
  assert.ok(lpHtml.includes('40-Minute Bilingual Classroom Lesson Plan'));
  assert.ok(lpHtml.includes('NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW_Learning.html'));
  assert.ok(lpHtml.includes('NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW_Arena.html'));
  assert.ok(!/https?:\/\//i.test(lpHtml));

  const lpCatHtml = renderTeacherLessonPlanCatalogCard();
  assert.ok(lpCatHtml.includes('id="teacher-lesson-plan-catalog-card"'));
  assert.ok(lpCatHtml.includes('data-action="export-chapter-lesson-plan"'));

  const srvLpRes = await fetch(`${baseUrl}/api/teacher/lesson-plan/NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW`);
  assert.equal(srvLpRes.status, 200);
  const srvLp = await srvLpRes.json();
  assert.equal(srvLp.status, 'ok');
  assert.equal(srvLp.duration_minutes, 40);
  assert.equal(srvLp.blocks.length, 4);
  assert.equal(srvLp.lesson_plan_sha256.length, 64);
  assert.equal(srvLp.zero_external_urls, true);

  // Verify G48 Offline Store Inventory Restock (Staff PIN) & Audit Ledger + Server /api/store/restock & /api/store/audit-ledger
  const restockModalHtml = renderFacilitatorRestockModal();
  assert.ok(restockModalHtml.includes('id="facilitator-restock-modal"'));

  const badRestock = restockStoreInventoryItem(pwaState, 'item_notebook_a4', 25, '0000');
  assert.equal(badRestock.ok, false);
  assert.equal(badRestock.error, 'INVALID_STAFF_PIN');

  const goodRestock = restockStoreInventoryItem(pwaState, 'item_notebook_a4', 25, '1234');
  assert.equal(goodRestock.ok, true);
  assert.equal(goodRestock.newStock, 75);

  const storeLedger = exportStoreInventoryAuditLedger(pwaState, 'CENTER-UP-GN-01');
  assert.equal(storeLedger.schemaVersion, 'aasha.store.audit.ledger.v1');
  assert.equal(storeLedger.inventory.item_notebook_a4, 75);
  assert.ok(storeLedger.ledgerSignature.startsWith('fnv1a32:'));

  const srvBadRestock = await fetch(`${baseUrl}/api/store/restock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ itemId: 'item_notebook_a4', qty: 20, staffPin: '9999' })
  });
  assert.equal(srvBadRestock.status, 403);

  const srvGoodRestock = await fetch(`${baseUrl}/api/store/restock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ itemId: 'item_notebook_a4', qty: 20, staffPin: '1234' })
  });
  assert.equal(srvGoodRestock.status, 200);
  const srvRestockBody = await srvGoodRestock.json();
  assert.equal(srvRestockBody.addedQty, 20);
  assert.ok(srvRestockBody.newStock >= 70);

  const srvLedgerRes = await fetch(`${baseUrl}/api/store/audit-ledger`);
  assert.equal(srvLedgerRes.status, 200);
  const srvLedger = await srvLedgerRes.json();
  assert.equal(srvLedger.status, 'ok');
  assert.equal(srvLedger.item_count, 4);
  assert.equal(srvLedger.ledger_sha256.length, 64);

  // Verify G49 Offline Teacher Custom Bilingual Assessment Builder & Non-Spoiler Validator + Server /api/teacher/custom-questions
  const spoilerCheck = validateNonSpoilerMisconception('12', 'Remember that the answer is 12 when multiplying.');
  assert.equal(spoilerCheck.valid, false);
  assert.equal(spoilerCheck.error, 'SPOILER_LEAK_IN_MISCONCEPTION');

  const cleanCheck = validateNonSpoilerMisconception('12', 'Check how many equal partitions are in each row before multiplying.');
  assert.equal(cleanCheck.valid, true);

  const qRes = authorCustomBilingualQuestion(pwaState, {
    chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS',
    promptEn: 'Which fraction represents 3 equal parts out of 4?',
    promptHi: '4 बराबर भागों में से 3 भाग कौन-सा भिन्न है?',
    correctOption: '3/4',
    wrongOption: '4/3',
    misconceptionHi: 'कुल बराबर भाग हर (नीचे) में लिखे जाते हैं।'
  });
  assert.equal(qRes.ok, true);
  assert.equal(qRes.totalCustomQuestions, 1);

  const qbHtml = renderTeacherCustomQuizBuilderCard({ customQuestions: pwaState.customQuestions });
  assert.ok(qbHtml.includes('id="teacher-custom-quiz-builder-card"'));
  assert.ok(qbHtml.includes('L-Truth Verified'));

  const srvSpoilerPost = await fetch(`${baseUrl}/api/teacher/custom-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS',
      promptEn: 'What is 6 + 6?',
      promptHi: '6 + 6 क्या है?',
      correctOption: '12',
      wrongOption: '10',
      misconceptionHi: 'The answer is 12.'
    })
  });
  assert.equal(srvSpoilerPost.status, 400);

  const srvValidPost = await fetch(`${baseUrl}/api/teacher/custom-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: 'custom_frac_q1',
      chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS',
      promptEn: 'Which fraction represents 3 equal parts out of 4?',
      promptHi: '4 बराबर भागों में से 3 भाग कौन-सा भिन्न है?',
      correctOption: '3/4',
      wrongOption: '4/3',
      misconceptionHi: 'कुल बराबर भाग हर (नीचे) में लिखे जाते हैं।'
    })
  });
  assert.equal(srvValidPost.status, 200);

  const srvListQ = await fetch(`${baseUrl}/api/teacher/custom-questions/NCERT-G06-MATH-CH07-FRACTIONS`);
  assert.equal(srvListQ.status, 200);
  const srvListBody = await srvListQ.json();
  assert.equal(srvListBody.count, 1);
  assert.equal(srvListBody.questions_sha256.length, 64);

  // Verify G50 Android TWA Wrapper & 2GB Low-RAM Tablet Benchmark + Server /api/system/tablet-benchmark
  const lowRamBench = evaluateLowRamTabletBudget({ deviceMemoryGb: 2, heapUsedMb: 68, maxBundleBytes: 539884 });
  assert.equal(lowRamBench.ok, true);
  assert.equal(lowRamBench.lowRamMode, true);
  assert.equal(lowRamBench.recommendedRenderer, 'Canvas2D_Lightweight_SVG');
  assert.equal(lowRamBench.twaPackageId, 'org.annantaasha.learn.twa');

  const highRamBench = evaluateLowRamTabletBudget({ deviceMemoryGb: 4, heapUsedMb: 90, maxBundleBytes: 539884 });
  assert.equal(highRamBench.lowRamMode, false);
  assert.equal(highRamBench.recommendedRenderer, 'PixiJS_WebGL_Accelerated');

  const diagHtml = renderLowRamTabletDiagnosticsCard({});
  assert.ok(diagHtml.includes('id="low-ram-tablet-diagnostics-card"'));
  assert.ok(diagHtml.includes('org.annantaasha.learn.twa'));

  const srvBenchRes = await fetch(`${baseUrl}/api/system/tablet-benchmark`);
  assert.equal(srvBenchRes.status, 200);
  const srvBench = await srvBenchRes.json();
  assert.equal(srvBench.status, 'ok');
  assert.equal(srvBench.twa_package_id, 'org.annantaasha.learn.twa');
  assert.equal(srvBench.within_2gb_ram_budget, true);
  assert.equal(srvBench.under_20mib_ceiling, true);
  assert.equal(srvBench.benchmark_sha256.length, 64);

  // Verify G51 Append-Only Hash-Chained NGO Donor Impact ID Ledger & CSR Audit Exporter
  const imp1 = appendDonorImpactLedgerEntry(pwaState, { impactId: 'IMP-GN-001', beneficiariesCount: 15, chaptersMastered: 13, sevaHours: 6 });
  assert.equal(imp1.ok, true);
  assert.equal(imp1.entry.prevHash, 'GENESIS_00000000');

  const imp2 = appendDonorImpactLedgerEntry(pwaState, { impactId: 'IMP-GN-002', beneficiariesCount: 12, chaptersMastered: 10, sevaHours: 4 });
  assert.equal(imp2.ok, true);
  assert.equal(imp2.entry.prevHash, imp1.entry.entryHash);

  const chainOk = verifyImpactLedgerChain(pwaState.donorImpactLedger);
  assert.equal(chainOk.valid, true);
  assert.equal(chainOk.totalEntries, 2);

  // Tamper check on Impact Ledger chain
  const tamperedLedger = [{ ...pwaState.donorImpactLedger[0], beneficiariesCount: 999 }, pwaState.donorImpactLedger[1]];
  const chainBad = verifyImpactLedgerChain(tamperedLedger);
  assert.equal(chainBad.valid, false);
  assert.equal(chainBad.brokenAt, 0);

  const csrPack = exportCsrImpactAuditPack(pwaState, 'CENTER-UP-GN-01');
  assert.equal(csrPack.totalBeneficiaries, 27);
  assert.equal(csrPack.totalSevaHours, 10);
  assert.equal(csrPack.chainValid, true);

  const impactCardHtml = renderDonorImpactLedgerCard({ donorImpactLedger: pwaState.donorImpactLedger });
  assert.ok(impactCardHtml.includes('id="donor-impact-ledger-card"'));
  assert.ok(impactCardHtml.includes('27'));

  const srvImp1 = await fetch(`${baseUrl}/api/impact/append-ledger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ impactId: 'IMP-SRV-001', beneficiariesCount: 20, chaptersMastered: 13, sevaHours: 8 })
  });
  assert.equal(srvImp1.status, 200);
  const srvImp1Body = await srvImp1.json();
  assert.equal(srvImp1Body.prev_hash, 'GENESIS_00000000');

  const srvImpExport = await fetch(`${baseUrl}/api/impact/csr-audit-export`);
  assert.equal(srvImpExport.status, 200);
  const srvImpData = await srvImpExport.json();
  assert.equal(srvImpData.chain_valid, true);
  assert.equal(srvImpData.total_beneficiaries, 20);
  assert.equal(srvImpData.ledger_sha256.length, 64);

  // Verify G52 Dec 31, 2026 Golden Master Freeze & Deployment Kit + Server /api/system/golden-master-manifest
  const gmKit = exportGoldenMasterDeploymentKit(pwaState, 'CENTER-UP-GN-01');
  assert.equal(gmKit.releaseTag, 'AASHA-MVP-RC-2026.12.31');
  assert.equal(gmKit.certifiedLearnArenaModules, 26);
  assert.equal(gmKit.precachedAssetsCount, 54);
  assert.ok(gmKit.kitSignature.startsWith('fnv1a32:'));

  const gmCardHtml = renderGoldenMasterReleaseCard(pwaState);
  assert.ok(gmCardHtml.includes('id="golden-master-release-card"'));
  assert.ok(gmCardHtml.includes('AASHA-MVP-RC-2026.12.31'));

  const srvGmRes = await fetch(`${baseUrl}/api/system/golden-master-manifest`);
  assert.equal(srvGmRes.status, 200);
  const srvGm = await srvGmRes.json();
  assert.equal(srvGm.status, 'ok');
  assert.equal(srvGm.release_tag, 'AASHA-MVP-RC-2026.12.31');
  assert.equal(srvGm.phases_a_to_g_certified, true);
  assert.equal(srvGm.manifest_sha256.length, 64);

  // Verify G53 Offline Parent SMS & WhatsApp Digest Outbox Batch Generator + Server /api/teacher/parent-sms-batch
  const smsBatch = generateCohortParentSmsOutboxBatch(sampleCohort, 'CENTER-UP-GN-01');
  assert.equal(smsBatch.schemaVersion, 'aasha.parent.sms.batch.v1');
  assert.equal(smsBatch.totalMessages, 2);
  assert.ok(smsBatch.messages[0].smsHi.includes('नमस्ते अभिभावक!'));
  assert.ok(smsBatch.batchSignature.startsWith('fnv1a32:'));

  const smsCardHtml = renderParentSmsDigestOutboxCard(sampleCohort);
  assert.ok(smsCardHtml.includes('id="parent-sms-digest-outbox-card"'));
  assert.ok(smsCardHtml.includes('2 Families'));

  const srvSmsRes = await fetch(`${baseUrl}/api/teacher/parent-sms-batch`);
  assert.equal(srvSmsRes.status, 200);
  const srvSms = await srvSmsRes.json();
  assert.equal(srvSms.status, 'ok');
  assert.ok(srvSms.message_count >= 1);
  assert.ok(srvSms.messages[0].sms_hi.includes('नमस्ते अभिभावक!'));
  assert.equal(srvSms.batch_sha256.length, 64);

  // Verify G54 Offline Student Peer Study Buddy Pairing & Group Arena Matchmaker + Server /api/teacher/peer-study-pairs
  const mixedCohort = {
    students: [
      { studentId: 'stu_mentor_1', name: 'Ananya', masteryPct: 94 },
      { studentId: 'stu_mentee_1', name: 'Rohan', masteryPct: 52 }
    ]
  };
  const buddyRes = matchPeerStudyBuddies(mixedCohort.students, 'NCERT-G06-MATH-CH07-FRACTIONS');
  assert.equal(buddyRes.ok, true);
  assert.equal(buddyRes.pairCount, 1);
  assert.equal(buddyRes.pairs[0].mentorName, 'Ananya');
  assert.equal(buddyRes.pairs[0].menteeName, 'Rohan');

  const buddyHtml = renderPeerStudyBuddyMatchmakerCard(mixedCohort);
  assert.ok(buddyHtml.includes('id="peer-study-buddy-matchmaker-card"'));
  assert.ok(buddyHtml.includes('Ananya'));
  assert.ok(buddyHtml.includes('Rohan'));

  const srvPairsRes = await fetch(`${baseUrl}/api/teacher/peer-study-pairs`);
  assert.equal(srvPairsRes.status, 200);
  const srvPairs = await srvPairsRes.json();
  assert.equal(srvPairs.status, 'ok');
  assert.ok(srvPairs.pair_count >= 1);
  assert.equal(srvPairs.pairs_sha256.length, 64);
} finally {
  await app.close();
}

console.log('✅ PHASE D STUDENT PWA + AASHA STUDIO + CENTRE SERVER LEARN/ARENA LAUNCHER TESTS PASSED!');
