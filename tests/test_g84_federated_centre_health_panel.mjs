import assert from "node:assert/strict";
import {
  buildFederatedCentreHealthSummary,
  renderTeacherCohortDashboard,
  renderTeacherFederatedCentreHealthPanel,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Federated Centre Health Summary & Panel
const summary = buildFederatedCentreHealthSummary({
  federatedDeltas: [
    { sourceCenterId: "CENTER-UP-GN-01", lamportEpoch: 12, recordsMerged: 4 },
    { sourceCenterId: "CENTER-UP-LKO-02", lamportEpoch: 19, recordsMerged: 7 },
  ],
});
assert.equal(summary.ok, true);
assert.equal(summary.centresCount, 2);
assert.equal(summary.maxLamportEpoch, 19);
assert.equal(summary.recordsMerged, 11);
assert.equal(summary.statusBadge, "GREEN_OFFLINE_PARITY");

const panelHtml = renderTeacherFederatedCentreHealthPanel({
  federatedDeltas: [{ sourceCenterId: "CENTER-UP-GN-01", lamportEpoch: 5, recordsMerged: 3 }],
});
assert.ok(panelHtml.includes("teacher-federated-centre-health-panel"));
assert.ok(panelHtml.includes("GREEN_OFFLINE_PARITY"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("teacher-federated-centre-health-panel"));

// 2. Test Live Fastify HTTP /api/teacher/federated-health
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const res = await fetch(`${base}/api/teacher/federated-health`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.teacher.federated.health.v1");
  assert.equal(json.healthStatus, "GREEN_OFFLINE_PARITY");
  assert.equal(json.within20MiBChildCap, true);
  assert.equal(json.zeroExternalUrls, true);
  assert.ok(json.health_sha256.length > 32);
  console.log("G84_FEDERATED_HEALTH_PASS", json.health_sha256.slice(0, 12), json.healthStatus);
} finally {
  await app.close();
}
