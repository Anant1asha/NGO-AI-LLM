import assert from "node:assert/strict";
import {
  buildOfflineQrLanSharePayload,
  renderTeacherBatchPackDownloadAndQrLanCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA UI & Offline QR/LAN Payload Builder
const payload = buildOfflineQrLanSharePayload({
  centerId: "CENTER-UP-GN-01",
  studioPdfJobs: [{ jobId: "J1" }, { jobId: "J2" }],
}, { shareId: "LANSHARE-G80-TEST" });

assert.equal(payload.ok, true);
assert.equal(payload.moduleCount, 2);
assert.equal(payload.within20MiBChildCap, true);
assert.ok(payload.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));
assert.ok(payload.lanUrl.includes("shareId=LANSHARE-G80-TEST"));

const cardHtml = renderTeacherBatchPackDownloadAndQrLanCard({
  centerId: "CENTER-UP-GN-01",
  studioPdfJobs: [{ jobId: "J1" }],
});
assert.ok(cardHtml.includes("teacher-batch-pack-qr-lan-card"));
assert.ok(cardHtml.includes("data:image/svg+xml;utf8,"));

const dashboardHtml = renderTeacherCohortDashboard({ studioPdfJobs: [{ jobId: "J1" }] });
assert.ok(dashboardHtml.includes("teacher-batch-pack-qr-lan-card"));

// 2. Test Live Fastify HTTP + SQLite LAN Share Endpoints
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const postRes = await fetch(`${base}/api/studio/lan-pack-share`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      shareId: "LANSHARE-G80-HTTP-01",
      centerId: "CENTER-UP-GN-01",
      packSha256: "abc123def4567890abc123def4567890",
      moduleCount: 6,
      lanHost: "192.168.1.10:3000",
    }),
  });
  assert.equal(postRes.status, 200);
  const created = await postRes.json();
  assert.equal(created.status, "ok");
  assert.equal(created.offlineOnly, true);
  assert.equal(created.within20MiBChildCap, true);
  assert.ok(created.qrSvgDataUri.startsWith("data:image/svg+xml;utf8,"));

  const getRes = await fetch(`${base}/api/studio/lan-pack-share/LANSHARE-G80-HTTP-01`);
  assert.equal(getRes.status, 200);
  const fetched = await getRes.json();
  assert.equal(fetched.shareId, "LANSHARE-G80-HTTP-01");
  assert.equal(fetched.moduleCount, 6);
  assert.equal(fetched.within20MiBChildCap, true);
  console.log("G80_QR_LAN_SHARE_PASS", fetched.shareId, fetched.moduleCount);
} finally {
  await app.close();
}
