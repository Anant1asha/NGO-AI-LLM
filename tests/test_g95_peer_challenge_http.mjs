import assert from "node:assert/strict";
import {
  buildOfflinePeerArenaInvite,
  renderOfflinePeerArenaChallengeCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Offline Peer Arena Challenge Card
const inv = buildOfflinePeerArenaInvite({ challengerId: "STU-G95-01", chapterId: "SCI_CH08", targetScorePct: 90 });
assert.equal(inv.ok, true);
assert.equal(inv.offlineOnly, true);
assert.ok(inv.inviteCode.startsWith("ARENA-"));

const cardHtml = renderOfflinePeerArenaChallengeCard({ challengerId: "STU-G95-01", chapterId: "SCI_CH08" });
assert.ok(cardHtml.includes("offline-peer-arena-challenge-card"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("offline-peer-arena-challenge-card"));

// 2. Test Live Fastify HTTP /api/student/peer-arena-challenge
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/student/peer-arena-challenge`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      challengerId: "STU-G95-01",
      chapterId: "SCI_CH08",
      genreId: "GENRE-PHY-MATTERJS-LAB",
      targetScorePct: 90,
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.status, "ok");
  assert.equal(posted.offlineOnly, true);
  assert.ok(posted.challenge_sha256.length > 32);

  const getRes = await fetch(`${base}/api/student/peer-arena-challenges/SCI_CH08`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.ok(fetched.challenges.length >= 1);
  console.log("G95_PEER_CHALLENGE_HTTP_PASS", posted.challenge_sha256.slice(0, 12), fetched.challenges.length);
} finally {
  await app.close();
}
