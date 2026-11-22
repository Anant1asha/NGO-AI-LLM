import assert from "node:assert/strict";
import {
  buildOfflineVoiceReadAloudCues,
  renderOfflineVoiceReadAloudCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Offline Voice Read-Aloud Cues & Card
const cues = buildOfflineVoiceReadAloudCues("NCERT-G08-SCI-CH08", [
  { en: "Force", hi: "बल" },
  { en: "Pressure", hi: "दाब" },
]);
assert.equal(cues.ok, true);
assert.equal(cues.offlineOnly, true);
assert.equal(cues.cues.length, 2);

const cardHtml = renderOfflineVoiceReadAloudCard({ chapterId: "NCERT-G08-SCI-CH08" });
assert.ok(cardHtml.includes("offline-voice-readaloud-card"));
assert.ok(cardHtml.includes("hi-IN"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("offline-voice-readaloud-card"));

// 2. Test Live Fastify HTTP /api/student/voice-phoneme-pack
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/student/voice-phoneme-pack`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chapterId: "NCERT-G08-SCI-CH08",
      language: "hi-IN",
      cueCount: 12,
      webvttContent: "WEBVTT\n\n00:00:00.000 --> 00:00:01.200\nForce | बल",
    }),
  });
  assert.equal(postRes.status, 200);
  const posted = await postRes.json();
  assert.equal(posted.status, "ok");
  assert.equal(posted.offlineOnly, true);
  assert.ok(posted.pack_sha256.length > 32);

  const getRes = await fetch(`${base}/api/student/voice-phoneme-pack/NCERT-G08-SCI-CH08`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.equal(fetched.chapterId, "NCERT-G08-SCI-CH08");
  assert.equal(fetched.cueCount, 12);
  console.log("G86_VOICE_PHONEME_HTTP_PASS", fetched.packSha256.slice(0, 12), fetched.cueCount);
} finally {
  await app.close();
}
