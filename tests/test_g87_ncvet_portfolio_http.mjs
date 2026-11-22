import assert from "node:assert/strict";
import {
  buildNcvetApprenticeshipPortfolioExport,
  renderNcvetApprenticeshipPortfolioCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA NCVET Apprenticeship Portfolio Card
const exp = buildNcvetApprenticeshipPortfolioExport({
  studentId: "STU-G87-01",
  customPdfMasteryLog: [
    { jobId: "J1", chapterId: "NCVET_SOLAR_01", scorePct: 92, wmTapHits: 20 },
    { jobId: "J2", chapterId: "NCVET_PLUMB_01", scorePct: 88, wmTapHits: 15 },
  ],
});
assert.equal(exp.ok, true);
assert.equal(exp.readinessStatus, "APPRENTICE_READY");
assert.ok(exp.nsqfCreditsEarned > 3);

const cardHtml = renderNcvetApprenticeshipPortfolioCard({
  studentId: "STU-G87-01",
  customPdfMasteryLog: [{ jobId: "J1", chapterId: "NCVET_SOLAR_01", scorePct: 90, wmTapHits: 20 }],
});
assert.ok(cardHtml.includes("ncvet-apprenticeship-portfolio-card"));
assert.ok(cardHtml.includes("NSQF"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("ncvet-apprenticeship-portfolio-card"));

// 2. Test Live Fastify HTTP /api/student/:id/ncvet-apprenticeship-export
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  await fetch(`${base}/api/student/custom-pdf-mastery`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ studentId: "STU-G87-01", jobId: "J1", chapterId: "NCVET_SOLAR_01", scorePct: 94, wmTapHits: 25 }),
  });

  const res = await fetch(`${base}/api/student/STU-G87-01/ncvet-apprenticeship-export`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.ncvet.apprenticeship.export.v1");
  assert.equal(json.offlineOnly, true);
  assert.ok(json.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));
  assert.ok(json.export_sha256.length > 32);
  console.log("G87_NCVET_EXPORT_HTTP_PASS", json.export_sha256.slice(0, 12), json.readinessStatus);
} finally {
  await app.close();
}
