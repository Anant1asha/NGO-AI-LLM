import assert from "node:assert/strict";
import {
  computeStudentStreakBadges,
  renderOfflineLeaderboardAndStreakCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Streak Badge & Leaderboard Card
const streakRes = computeStudentStreakBadges({
  studentId: "STU-G85-01",
  customPdfMasteryLog: [
    { jobId: "J1", chapterId: "SCI_CH08", scorePct: 92, wmTapHits: 15 },
    { jobId: "J2", chapterId: "MATH_CH07", scorePct: 95, wmTapHits: 15 },
    { jobId: "J3", chapterId: "VOC_CH01", scorePct: 90, wmTapHits: 10 },
  ],
});
assert.equal(streakRes.ok, true);
assert.ok(streakRes.badges.includes("GOLD_CHALLENGER"));
assert.ok(streakRes.badges.includes("BILINGUAL_WM_MASTER"));

const cardHtml = renderOfflineLeaderboardAndStreakCard({
  studentId: "STU-G85-01",
  customPdfMasteryLog: [{ jobId: "J1", chapterId: "SCI_CH08", scorePct: 92, wmTapHits: 30 }],
});
assert.ok(cardHtml.includes("offline-leaderboard-streak-card"));
assert.ok(cardHtml.includes("BILINGUAL_WM_MASTER"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("offline-leaderboard-streak-card"));

// 2. Test Live Fastify HTTP /api/student/offline-leaderboard/:centerId
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  await fetch(`${base}/api/student/custom-pdf-mastery`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ studentId: "STU-G85-01", jobId: "J1", chapterId: "SCI_CH08", scorePct: 96, wmTapHits: 32 }),
  });

  const res = await fetch(`${base}/api/student/offline-leaderboard/CENTER-UP-GN-01`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.offline.leaderboard.v1");
  assert.equal(json.offlineOnly, true);
  assert.ok(json.rankedStudents.length >= 1);
  assert.ok(json.leaderboard_sha256.length > 32);
  console.log("G85_LEADERBOARD_HTTP_PASS", json.leaderboard_sha256.slice(0, 12), json.rankedStudents[0].studentId);
} finally {
  await app.close();
}
