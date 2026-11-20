import assert from "node:assert/strict";
import {
  buildParentProgressQrCard,
  renderParentProgressQrCard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test Student PWA Bilingual Parent Progress QR Card
const card = buildParentProgressQrCard({
  studentId: "STU-G82-01",
  customPdfMasteryLog: [
    { jobId: "J1", chapterId: "SCI_CH08", scorePct: 92, wmTapHits: 24 },
    { jobId: "J2", chapterId: "MATH_CH07", scorePct: 88, wmTapHits: 16 },
  ],
});
assert.equal(card.ok, true);
assert.equal(card.modulesCompleted, 2);
assert.equal(card.avgScorePct, 90);
assert.equal(card.totalWmTapHits, 40);
assert.equal(card.offlineOnly, true);
assert.ok(card.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));
assert.ok(card.summaryHi.includes("STU-G82-01"));

const html = renderParentProgressQrCard({
  studentId: "STU-G82-01",
  customPdfMasteryLog: [{ jobId: "J1", chapterId: "SCI_CH08", scorePct: 92, wmTapHits: 24 }],
});
assert.ok(html.includes("parent-progress-qr-card"));
assert.ok(html.includes("data:image/svg+xml;utf8,"));

// 2. Test Live Fastify HTTP Parent Progress QR & Offline Teacher Digest
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  // Seed a custom PDF mastery event first
  await fetch(`${base}/api/student/custom-pdf-mastery`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ studentId: "STU-G82-01", jobId: "J1", chapterId: "SCI_CH08", scorePct: 95, wmTapHits: 30 }),
  });

  const qrRes = await fetch(`${base}/api/student/parent-progress-qr/STU-G82-01`);
  assert.equal(qrRes.status, 200);
  const qrJson = await qrRes.json();
  assert.equal(qrJson.schemaVersion, "aasha.parent.progress.qr.v1");
  assert.equal(qrJson.offlineOnly, true);
  assert.ok(qrJson.customModulesCompleted >= 1);
  assert.ok(qrJson.totalWmTapHits >= 30);
  assert.ok(qrJson.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));
  assert.ok(qrJson.parent_progress_sha256.length > 32);

  const digRes = await fetch(`${base}/api/teacher/offline-digest/CENTER-UP-GN-01`);
  assert.equal(digRes.status, 200);
  const digJson = await digRes.json();
  assert.equal(digJson.schemaVersion, "aasha.offline.teacher.digest.v1");
  assert.equal(digJson.within20MiBChildCap, true);
  assert.ok(digJson.digest_sha256.length > 32);
  console.log("G82_PARENT_QR_DIGEST_PASS", qrJson.parent_progress_sha256.slice(0, 12), digJson.digest_sha256.slice(0, 12));
} finally {
  await app.close();
}
