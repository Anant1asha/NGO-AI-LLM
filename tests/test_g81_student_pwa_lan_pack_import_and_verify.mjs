import assert from "node:assert/strict";
import {
  importOfflineLanCohortPack,
  renderStudentOfflineLanPackImportCard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test Student PWA Offline LAN Pack Import & 20 MiB Cap Enforcement
const state = {};
const validPack = {
  schemaVersion: "aasha.offline.cohort.pack.v2",
  pack_sha256: "deadbeef1234567890deadbeef123456",
  modules: [
    { job_id: "G81-J1", chapter_id: "NCERT_G08_FORCE", subject: "science", grade: 8, size_bytes: 195000 },
    { job_id: "G81-J2", chapter_id: "NCERT_G07_LINEAR", subject: "mathematics", grade: 7, size_bytes: 210000 },
  ],
};
const res1 = importOfflineLanCohortPack(state, validPack);
assert.equal(res1.ok, true);
assert.equal(res1.verifiedOffline, true);
assert.equal(res1.importedCount, 2);
assert.equal(res1.totalImportedModules, 2);

// Deduplication check
const resDup = importOfflineLanCohortPack(state, validPack);
assert.equal(resDup.importedCount, 0);
assert.equal(resDup.totalImportedModules, 2);

// Oversized child HTML (> 20 MiB) rejection
const oversized = importOfflineLanCohortPack({}, {
  schemaVersion: "aasha.offline.cohort.pack.v2",
  modules: [{ job_id: "BIG", chapter_id: "BIG_CH", size_bytes: 20971521 }],
});
assert.equal(oversized.ok, false);
assert.equal(oversized.error, "CHILD_HTML_EXCEEDS_20MIB_CAP");

const cardHtml = renderStudentOfflineLanPackImportCard(state);
assert.ok(cardHtml.includes("student-offline-lan-pack-import-card"));
assert.ok(cardHtml.includes("deadbeef12345678"));

// 2. Test Live Fastify HTTP Export -> Import & Tamper Rejection
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const expRes = await fetch(`${base}/api/sync/export-custom-pdf-cohort-pack`);
  assert.equal(expRes.status, 200);
  const exported = await expRes.json();

  const impRes = await fetch(`${base}/api/sync/import-custom-pdf-cohort-pack`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(exported),
  });
  assert.equal(impRes.status, 200);
  const imported = await impRes.json();
  assert.equal(imported.verified, true);
  assert.equal(imported.within20MiBChildCap, true);

  // Tamper check
  const tampered = { ...exported, pack_sha256: "00000000000000000000000000000000" };
  const badRes = await fetch(`${base}/api/sync/import-custom-pdf-cohort-pack`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(tampered),
  });
  assert.equal(badRes.status, 400);
  const badJson = await badRes.json();
  assert.equal(badJson.error, "PACK_SHA256_MISMATCH");
  console.log("G81_LAN_PACK_IMPORT_VERIFY_PASS", imported.pack_sha256.slice(0, 12));
} finally {
  await app.close();
}
