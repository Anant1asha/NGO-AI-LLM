import assert from "node:assert/strict";
import {
  buildTeacherRemedialPrintQrPayload,
  renderTeacherCohortDashboard,
  renderTeacherRemedialWorksheetPrintCard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Remedial Worksheet Print & QR Card
const p = buildTeacherRemedialPrintQrPayload({
  chapterId: "SCI_CH08",
  customPdfMasteryLog: [
    { studentId: "STU-1", scorePct: 58 },
    { studentId: "STU-2", scorePct: 91 },
  ],
});
assert.equal(p.ok, true);
assert.equal(p.studentsFlaggedCount, 1);
assert.ok(p.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));

const cardHtml = renderTeacherRemedialWorksheetPrintCard({ chapterId: "SCI_CH08" });
assert.ok(cardHtml.includes("teacher-remedial-worksheet-print-card"));
assert.ok(cardHtml.includes("data:image/svg+xml;utf8,"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("teacher-remedial-worksheet-print-card"));

// 2. Test Live Fastify HTTP /api/teacher/remedial-worksheet-print/:chapterId
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  await fetch(`${base}/api/student/custom-pdf-mastery`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ studentId: "STU-G88-LOW", jobId: "J1", chapterId: "SCI_CH08", scorePct: 54, wmTapHits: 8 }),
  });

  const res = await fetch(`${base}/api/teacher/remedial-worksheet-print/SCI_CH08`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.remedial.worksheet.print.v1");
  assert.equal(json.offlineOnly, true);
  assert.ok(json.studentsFlaggedCount >= 1);
  assert.ok(json.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));
  assert.ok(json.worksheet_sha256.length > 32);
  console.log("G88_REMEDIAL_PRINT_HTTP_PASS", json.worksheet_sha256.slice(0, 12), json.studentsFlaggedCount);
} finally {
  await app.close();
}
