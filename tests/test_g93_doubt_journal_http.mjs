import assert from "node:assert/strict";
import {
  recordOfflineStudentDoubt,
  renderStudentDoubtJournalCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Student Doubt Journal & Socratic Hint Card
const state = {};
const dRes = recordOfflineStudentDoubt(state, {
  studentId: "STU-G93-01",
  chapterId: "SCI_CH08",
  doubtText: "Why does pressure increase when area decreases?",
});
assert.equal(dRes.ok, true);
assert.equal(dRes.totalDoubts, 1);

const cardHtml = renderStudentDoubtJournalCard(state);
assert.ok(cardHtml.includes("student-doubt-journal-card"));
assert.ok(cardHtml.includes("Zero-Spoiler Socratic Hint"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("student-doubt-journal-card"));

// 2. Test Live Fastify HTTP /api/student/doubt-journal
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/student/doubt-journal`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      studentId: "STU-G93-01",
      chapterId: "SCI_CH08",
      doubtText: "Why does pressure increase when area decreases?",
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.status, "ok");
  assert.equal(posted.zeroSpoiler, true);
  assert.ok(posted.doubt_sha256.length > 32);

  const getRes = await fetch(`${base}/api/student/doubt-journal/STU-G93-01`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.ok(fetched.entries.length >= 1);
  console.log("G93_DOUBT_JOURNAL_HTTP_PASS", posted.doubt_sha256.slice(0, 12), fetched.entries.length);
} finally {
  await app.close();
}
