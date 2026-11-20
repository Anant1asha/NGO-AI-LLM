import assert from "node:assert/strict";
import { buildServer } from "../Aasha-AI/server/server.js";

const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const payload = {
    sourceCenterId: "CENTER-UP-LKO-02",
    targetCenterId: "CENTER-UP-GN-01",
    lamportEpoch: 22,
    customPdfMastery: [
      {
        studentId: "STU-FED-01",
        jobId: "J-FED-1",
        chapterId: "NCERT_G08_FORCE",
        scorePct: 91,
        wmTapHits: 25,
        masterySha256: "fedsha000111222333444555666777888",
      },
    ],
  };

  const res1 = await fetch(`${base}/api/sync/federated-delta-merge`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  assert.equal(res1.status, 200);
  const j1 = await res1.json();
  assert.equal(j1.status, "ok");
  assert.equal(j1.recordsMerged, 1);
  assert.ok(j1.delta_sha256.length > 32);

  // Idempotent replay check
  const res2 = await fetch(`${base}/api/sync/federated-delta-merge`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  assert.equal(res2.status, 200);
  const j2 = await res2.json();
  assert.equal(j2.recordsMerged, 0);
  assert.equal(j2.duplicateSkipped, 1);

  const stRes = await fetch(`${base}/api/sync/federated-delta-status`);
  assert.equal(stRes.status, 200);
  const st = await stRes.json();
  assert.ok(st.totalDeltas >= 2);
  console.log("G83_FEDERATED_HTTP_PASS", j1.delta_sha256.slice(0, 12), st.totalDeltas);
} finally {
  await app.close();
}
