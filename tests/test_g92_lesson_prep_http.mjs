import assert from "node:assert/strict";
import {
  buildTeacherCopilotLessonPrep,
  renderTeacherCohortDashboard,
  renderTeacherCopilotLessonPrepCard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Teacher Copilot Lesson Prep Card
const prep = buildTeacherCopilotLessonPrep({ chapterId: "SCI_CH09_FRICTION" });
assert.equal(prep.ok, true);
assert.equal(prep.durationMinutes, 30);

const cardHtml = renderTeacherCopilotLessonPrepCard({ chapterId: "SCI_CH09_FRICTION" });
assert.ok(cardHtml.includes("teacher-copilot-lesson-prep-card"));
assert.ok(cardHtml.includes("30 min"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("teacher-copilot-lesson-prep-card"));

// 2. Test Live Fastify HTTP /api/teacher/lesson-prep-from-pdf
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/teacher/lesson-prep-from-pdf`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chapterId: "SCI_CH09_FRICTION",
      subject: "science",
      grade: 8,
      keyTerms: ["friction", "motion", "lubricant"],
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.status, "ok");
  assert.equal(posted.offlineOnly, true);
  assert.ok(posted.prep_sha256.length > 32);

  const getRes = await fetch(`${base}/api/teacher/lesson-prep/SCI_CH09_FRICTION`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.equal(fetched.chapterId, "SCI_CH09_FRICTION");
  console.log("G92_LESSON_PREP_HTTP_PASS", fetched.prepSha256.slice(0, 12), fetched.chapterId);
} finally {
  await app.close();
}
