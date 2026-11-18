import assert from "node:assert/strict";
import {
  buildStudentMasteryLeaderboard,
  renderStudentMasteryLeaderboardPanel,
  renderRewardsBadges,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Student Mastery Leaderboard & Streak Badges Calculation
const defaultBoard = buildStudentMasteryLeaderboard({});
assert.equal(defaultBoard.ok, true);
assert.equal(defaultBoard.statusBadge, "GREEN_OFFLINE_LEADERBOARD");
assert.equal(defaultBoard.within20MiBChildCap, true);
assert.equal(defaultBoard.zeroExternalUrls, true);
assert.equal(defaultBoard.totalStudents, 3);
assert.equal(defaultBoard.leaderboard[0].rank, 1);
assert.equal(defaultBoard.leaderboard[0].name, "Priya Sharma");

// Test custom cohort with streak badges and tiers
const customBoard = buildStudentMasteryLeaderboard({
  students: [
    { studentId: "STU-A", name: "Ananya", score: 98, streak: 32, coins: 500, completedCount: 12 },
    { studentId: "STU-B", name: "Brijesh", score: 91, streak: 7, coins: 220, completedCount: 5 },
    { studentId: "STU-C", name: "Chitra", score: 78, streak: 2, coins: 60, completedCount: 2 },
  ],
});
assert.equal(customBoard.ok, true);
assert.equal(customBoard.totalStudents, 3);

// Ananya: Rank 1, 32 streak (MASIK_CHAMPION), 12 completed (MASTERY_GURU)
const top = customBoard.leaderboard[0];
assert.equal(top.studentId, "STU-A");
assert.equal(top.rank, 1);
assert.equal(top.tier, "MASTERY_GURU");
const topBadgeIds = top.badges.map((b) => b.id);
assert.ok(topBadgeIds.includes("FIRST_STEP"));
assert.ok(topBadgeIds.includes("TRI_STREAK"));
assert.ok(topBadgeIds.includes("SAPTAHIK_VEER"));
assert.ok(topBadgeIds.includes("MASIK_CHAMPION"));
assert.ok(topBadgeIds.includes("VIDYA_SAHAYAK"));
assert.ok(topBadgeIds.includes("MASTERY_GURU"));

// Brijesh: Rank 2, 7 streak (SAPTAHIK_VEER), 5 completed (VIDYA_VEER)
const second = customBoard.leaderboard[1];
assert.equal(second.studentId, "STU-B");
assert.equal(second.rank, 2);
assert.equal(second.tier, "VIDYA_VEER");
const secondBadgeIds = second.badges.map((b) => b.id);
assert.ok(secondBadgeIds.includes("SAPTAHIK_VEER"));
assert.ok(!secondBadgeIds.includes("MASIK_CHAMPION"));

// 2. Test HTML Component Rendering
const panelHtml = renderStudentMasteryLeaderboardPanel(customBoard);
assert.ok(panelHtml.includes("student-mastery-leaderboard-panel"));
assert.ok(panelHtml.includes("GREEN_OFFLINE_LEADERBOARD"));
assert.ok(panelHtml.includes("🥇"));
assert.ok(panelHtml.includes("🥈"));
assert.ok(panelHtml.includes("Ananya"));
assert.ok(panelHtml.includes("Brijesh"));
assert.ok(panelHtml.includes("Mastery Guru"));

// Verify integration in renderRewardsBadges
const rewardsHtml = renderRewardsBadges({ coins: 150 });
assert.ok(rewardsHtml.includes("student-mastery-leaderboard-panel"));

// 3. Test Live Fastify HTTP Endpoints
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  // GET /api/student/leaderboard
  const res1 = await fetch(`${base}/api/student/leaderboard`);
  assert.equal(res1.status, 200);
  const json1 = await res1.json();
  assert.equal(json1.status, "ok");
  assert.equal(json1.schemaVersion, "aasha.student.leaderboard.v1");
  assert.equal(json1.within20MiBChildCap, true);
  assert.equal(json1.zeroExternalUrls, true);
  assert.ok(Array.isArray(json1.leaderboard));
  assert.ok(json1.leaderboard.length > 0);
  assert.ok(json1.leaderboard_sha256.length > 32);

  // GET /api/student/leaderboard/:centerId
  const res2 = await fetch(`${base}/api/student/leaderboard/CENTER-BIHAR-01`);
  assert.equal(res2.status, 200);
  const json2 = await res2.json();
  assert.equal(json2.status, "ok");
  assert.equal(json2.centerId, "CENTER-BIHAR-01");
  assert.ok(json2.leaderboard.length > 0);
  assert.equal(json2.leaderboard[0].rank, 1);

  console.log("G85_OFFLINE_STUDENT_MASTERY_LEADERBOARD_PASS", json1.leaderboard_sha256.slice(0, 12), json1.centerId);
} finally {
  await app.close();
}
