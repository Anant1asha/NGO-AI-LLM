import assert from "node:assert/strict";
import {
  buildDec2026MvpReadinessBadge,
  renderDec2026MvpCertificationCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Dec 2026 MVP Readiness Badge & Card
const badge = buildDec2026MvpReadinessBadge({ maxLamportEpoch: 32 });
assert.equal(badge.ok, true);
assert.equal(badge.targetDeadline, "2026-12-31");
assert.equal(badge.within20MiBCap, true);

const cardHtml = renderDec2026MvpCertificationCard({});
assert.ok(cardHtml.includes("dec-2026-mvp-certification-card"));
assert.ok(cardHtml.includes("2026-12-31"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("dec-2026-mvp-certification-card"));

// 2. Test Live Fastify HTTP /api/mvp/dec-2026-readiness-summary
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const res = await fetch(`${base}/api/mvp/dec-2026-readiness-summary`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.dec2026.mvp.readiness.v1");
  assert.equal(json.mvpTargetDeadline, "2026-12-31");
  assert.equal(json.offlineOnly, true);
  assert.equal(json.within20MiBChildCap, true);
  assert.ok(json.readiness_sha256.length > 32);
  console.log("G90_MVP_READINESS_HTTP_PASS", json.readiness_sha256.slice(0, 12), json.mvpTargetDeadline);
} finally {
  await app.close();
}
