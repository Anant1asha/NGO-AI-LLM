import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aasha-v7-http-'));
const tmpDb = path.join(tmpDir, 'test_aasha_local.db');
process.env.AASHA_DB_PATH = tmpDb;
process.env.AASHA_STAFF_PIN = '1080';

const { buildServer } = await import('../Aasha-AI/server/server.js');
const app = buildServer();
const baseUrl = await app.listen({ port: 0, host: '127.0.0.1' });

function fnv1a32(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

try {
  // 1. Health endpoint
  const healthRes = await fetch(`${baseUrl}/api/health`);
  assert.equal(healthRes.status, 200);
  const health = await healthRes.json();
  assert.equal(health.status, 'ok');
  assert.equal(health.service, 'aasha-centre-server');

  // 2. Store items seeded
  const storeRes = await fetch(`${baseUrl}/api/store/items`);
  assert.equal(storeRes.status, 200);
  const store = await storeRes.json();
  assert.ok(store.items.length >= 4, 'Expected at least 4 seeded store items');

  // 3. Quiz sync (gold pass + standard pass + misconception failure + duplicate idempotency)
  const syncPayload = {
    studentId: 'stu_ananya_01',
    events: [
      { id: 'ev_1', chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS', nodeId: 'node_equiv', score: 92 },
      { id: 'ev_2', chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS', nodeId: 'node_add', score: 72 },
      { id: 'ev_3', chapterId: 'Chapter3_LPG_Learning', nodeId: 'node_lpg_safety', score: 45 },
      { id: 'ev_1', chapterId: 'NCERT-G06-MATH-CH07-FRACTIONS', nodeId: 'node_equiv', score: 92 }
    ]
  };
  const syncRes = await fetch(`${baseUrl}/api/sync/quiz-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(syncPayload)
  });
  assert.equal(syncRes.status, 200);
  const syncData = await syncRes.json();
  assert.equal(syncData.synced, 3);
  assert.equal(syncData.coinsAwarded, 150);
  assert.equal(syncData.balance, 150);

  // 4. Teacher misconception analytics
  const miscRes = await fetch(`${baseUrl}/api/teacher/misconception-analytics`);
  assert.equal(miscRes.status, 200);
  const miscData = await miscRes.json();
  assert.equal(miscData.status, 'ok');
  assert.ok(miscData.hotspots.some((h) => h.chapterId === 'Chapter3_LPG_Learning' && h.conceptCode === 'node_lpg_safety'));

  // 5. Redeem with wrong PIN -> 403
  const badPinRes = await fetch(`${baseUrl}/api/student/stu_ananya_01/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ itemId: 'item_notebook_a4', staffPin: '9999' })
  });
  assert.equal(badPinRes.status, 403);

  // 6. Redeem item costing 250 with only 150 coins -> 400 INSUFFICIENT_COINS
  const lowBalRes = await fetch(`${baseUrl}/api/student/stu_ananya_01/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ itemId: 'item_geometry_box', staffPin: '1080' })
  });
  assert.equal(lowBalRes.status, 400);

  // 7. Redeem notebook (100 coins) with PIN 1080 -> 200 & coin conservation
  const okRedeemRes = await fetch(`${baseUrl}/api/student/stu_ananya_01/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ itemId: 'item_notebook_a4', staffPin: '1080' })
  });
  assert.equal(okRedeemRes.status, 200);
  const okRedeem = await okRedeemRes.json();
  assert.equal(okRedeem.status, 'redeemed');
  assert.equal(okRedeem.balance, 50);

  // 8. Cohort order pack ingestion + FNV-1a verification
  const packCore = {
    schema_version: '1.0.0',
    center_id: 'CENTER-UP-GN-01',
    exported_at_utc: '2026-11-13T13:55:00Z',
    cohort_metrics: { total_students: 25, avg_mastery_pct: 84, total_tokens_minted: 4500, pending_redemptions: 0 },
    fulfilled_redemptions: [{ order_id: 'ORD-V7-001', item_id: 'item_pencil_pack', cost: 50, status: 'FULFILLED_BY_STAFF' }]
  };
  const integrityHash = `fnv1a32:${fnv1a32(JSON.stringify(packCore) + '::AASHA-OFFLINE-ORDER-PACK-V1')}`;
  const packRes = await fetch(`${baseUrl}/api/sync/cohort-order-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...packCore, integrity_hash: integrityHash })
  });
  assert.equal(packRes.status, 200);
  const packData = await packRes.json();
  assert.equal(packData.status, 'ingested');
  assert.equal(packData.reconciled_orders, 1);

  // 9. Student snapshot backup & restore round-trip
  const snapBody = {
    schemaVersion: 'aasha.student.snapshot.v1',
    studentId: 'stu_ananya_01',
    studentName: 'Ananya Sharma',
    coinsBalance: 50,
    completedChapters: ['NCERT-G06-MATH-CH07-FRACTIONS'],
    streakDays: 4
  };
  const canonicalSnap = JSON.stringify({
    studentId: snapBody.studentId,
    coinsBalance: snapBody.coinsBalance,
    completedChapters: [...snapBody.completedChapters].sort(),
    streakDays: snapBody.streakDays
  });
  snapBody.checksum = `fnv1a32:${fnv1a32(canonicalSnap)}`;
  const snapPost = await fetch(`${baseUrl}/api/sync/student-snapshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapBody)
  });
  assert.equal(snapPost.status, 200);
  const snapGet = await fetch(`${baseUrl}/api/sync/student-snapshot/stu_ananya_01`);
  assert.equal(snapGet.status, 200);
  const snapRestored = await snapGet.json();
  assert.equal(snapRestored.coinsBalance, 50);
  assert.equal(snapRestored.checksum, snapBody.checksum);


  // 10. Multi-centre cohort delta merge + replay idempotency (Phase G43)
  const deltaPayload = {
    deltas: [
      { delta_id: 'DELTA-GN-G43', centre_id: 'CENTER-UP-GN-01', student_awards: [{ student_id: 'stu_ananya_01', coins: 50 }] }
    ]
  };
  const dRes1 = await fetch(`${baseUrl}/api/sync/multi-centre-deltas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(deltaPayload)
  });
  assert.equal(dRes1.status, 200);
  const dData1 = await dRes1.json();
  assert.equal(dData1.merged_centres, 1);
  assert.equal(dData1.total_coins_minted, 50);

  const dRes2 = await fetch(`${baseUrl}/api/sync/multi-centre-deltas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(deltaPayload)
  });
  const dData2 = await dRes2.json();
  assert.equal(dData2.merged_centres, 0);
  assert.equal(dData2.total_coins_minted, 0);

  // 11. Teacher NCVET/PSSCIVE rubric validation endpoint (Phase G43)
  const rubricTpl = JSON.parse(fs.readFileSync(new URL('../Aasha-AI/experience_registry/teacher_authoring_template_v1.json', import.meta.url), 'utf8'));
  const rubRes = await fetch(`${baseUrl}/api/teacher/validate-rubric`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rubricTpl)
  });
  assert.equal(rubRes.status, 200);
  const rubData = await rubRes.json();
  assert.equal(rubData.valid, true);
  assert.equal(rubData.errors.length, 0);


  // 12. TEAS SQLite Catalogue Manifest + Live G44 Catalogue (Phase G44)
  const catRes = await fetch(`${baseUrl}/api/catalogue/teas-sqlite-manifest`);
  assert.equal(catRes.status, 200);
  const catData = await catRes.json();
  assert.equal(catData.status, 'ok');
  assert.ok(catData.live_g44_catalogue.wm_entries_count >= 1129);
  assert.equal(catData.live_g44_catalogue.certified_html5_modules_count, 21);


  // 13. Teacher Remediation Worksheet Endpoint (Phase G45)
  const remRes = await fetch(`${baseUrl}/api/teacher/remediation-worksheet/Chapter3_LPG_Learning`);
  assert.equal(remRes.status, 200);
  const remData = await remRes.json();
  assert.equal(remData.status, 'ok');
  assert.equal(remData.chapterId, 'Chapter3_LPG_Learning');
  assert.ok(remData.strugglingNodes.some((n) => n.conceptCode === 'node_lpg_safety'));
  assert.equal(remData.zero_external_urls, true);


  // 14. Student Seva Certificate & Bilingual Parent Card Endpoint (Phase G46)
  const certRes = await fetch(`${baseUrl}/api/student/stu_ananya_01/seva-certificate`);
  assert.equal(certRes.status, 200);
  const certData = await certRes.json();
  assert.equal(certData.status, 'ok');
  assert.equal(certData.offline_verifiable, true);
  assert.equal(certData.certificate_sha256.length, 64);
  assert.ok(certData.parent_sms_hi.includes('आशा प्रगति'));

  console.log('✅ GAP-V7-01, G43, G44, G45 & G46 LIVE HTTP INTEGRATION TEST PASSED (14/14 endpoint assertions on ephemeral port)');




} finally {
  await app.close();
  fs.rmSync(tmpDir, { recursive: true, force: true });
}
