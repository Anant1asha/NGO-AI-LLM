import assert from "node:assert/strict";
import {
  buildMultiBoardCurriculumSummary,
  renderMultiBoardCurriculumMatrixCard,
  renderTeacherCohortDashboard,
} from "../Aasha-AI/aasha-student-pwa/src/app.js";
import { buildServer } from "../Aasha-AI/server/server.js";

// 1. Test PWA Multi-Board Curriculum Matrix Card
const mb = buildMultiBoardCurriculumSummary({});
assert.equal(mb.ok, true);
assert.deepEqual(mb.boards, ["NCERT", "UPMSP", "CBSE", "NCVET"]);
assert.equal(mb.within20MiBCap, true);

const cardHtml = renderMultiBoardCurriculumMatrixCard({});
assert.ok(cardHtml.includes("multi-board-curriculum-matrix-card"));
assert.ok(cardHtml.includes("UPMSP"));

const dashHtml = renderTeacherCohortDashboard({});
assert.ok(dashHtml.includes("multi-board-curriculum-matrix-card"));

// 2. Test Live Fastify HTTP /api/catalogue/multi-board-summary
const app = buildServer();
const base = await app.listen({ port: 0, host: "127.0.0.1" });
try {
  const res = await fetch(`${base}/api/catalogue/multi-board-summary`);
  assert.equal(res.status, 200);
  const json = await res.json();
  assert.equal(json.schemaVersion, "aasha.multi.board.summary.v1");
  assert.equal(json.within20MiBChildCap, true);
  assert.equal(json.zeroExternalUrls, true);
  assert.ok(json.boardsSupported.includes("UPMSP"));
  assert.ok(json.catalogue_sha256.length > 32);
  console.log("G91_MULTI_BOARD_HTTP_PASS", json.catalogue_sha256.slice(0, 12), json.boardsSupported.length);
} finally {
  await app.close();
}
