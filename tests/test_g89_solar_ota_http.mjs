import assert from "node:assert/strict";
import {
  renderSolarOtaDeltaVerifierCard,
  renderTeacherCohortDashboard,
  verifySolarOtaDeltaManifest,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Solar OTA Manifest Verifier & Card
const v = verifySolarOtaDeltaManifest({
  deltaId: "OTA-G89-01",
  chunks: [{ chunkId: "C1", sizeBytes: 185000 }],
});
assert.equal(v.ok, true);
assert.equal(v.within20MiBCap, true);

const cardHtml = renderSolarOtaDeltaVerifierCard({ deltaId: "OTA-G89-01" });
assert.ok(cardHtml.includes("solar-ota-delta-verifier-card"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("solar-ota-delta-verifier-card"));

// 2. Test Live Fastify HTTP /api/sync/verify-solar-ota-delta & /api/sync/solar-ota-status/:centerId
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/sync/verify-solar-ota-delta`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      deltaId: "OTA-G89-HTTP-01",
      centerId: "CENTER-UP-GN-01",
      chunks: [{ chunkId: "C1", sizeBytes: 210000 }],
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.verified, true);
  assert.equal(posted.within20MiBCap, true);
  assert.ok(posted.ota_sha256.length > 32);

  const getRes = await fetch(`${base}/api/sync/solar-ota-status/CENTER-UP-GN-01`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.ok(fetched.receipts.length >= 1);
  console.log("G89_SOLAR_OTA_HTTP_PASS", posted.ota_sha256.slice(0, 12), fetched.receipts.length);
} finally {
  await app.close();
}
