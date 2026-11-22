import assert from "node:assert/strict";
import {
  buildTeacherDoubtBroadcast,
  renderTeacherCohortDashboard,
  renderTeacherDoubtBroadcastCard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Teacher Doubt Broadcast Card
const b = buildTeacherDoubtBroadcast({ chapterId: "SCI_CH08", doubtsResolvedCount: 4 });
assert.equal(b.ok, true);
assert.equal(b.doubtsResolvedCount, 4);

const cardHtml = renderTeacherDoubtBroadcastCard({ chapterId: "SCI_CH08", doubtsResolvedCount: 4 });
assert.ok(cardHtml.includes("teacher-doubt-broadcast-card"));
assert.ok(cardHtml.includes("SCI_CH08"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("teacher-doubt-broadcast-card"));

// 2. Test Live Fastify HTTP /api/teacher/doubt-broadcast
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/teacher/doubt-broadcast`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chapterId: "SCI_CH08",
      doubtsResolvedCount: 3,
      clarificationEn: "Smaller area yields higher pressure.",
      clarificationHi: "कम क्षेत्रफल पर अधिक दाब बनता है।",
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.status, "ok");
  assert.equal(posted.offlineOnly, true);
  assert.ok(posted.broadcast_sha256.length > 32);

  const getRes = await fetch(`${base}/api/teacher/doubt-broadcast/SCI_CH08`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.ok(fetched.broadcasts.length >= 1);
  console.log("G94_DOUBT_BROADCAST_HTTP_PASS", posted.broadcast_sha256.slice(0, 12), fetched.broadcasts.length);
} finally {
  await app.close();
}
