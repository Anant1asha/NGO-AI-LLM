/**
 * AASHA Workstream B (Cycle 3): IndicPhonemeSyncCompilerJS & Sub20MiBBundleOptimizerJS
 */
const crypto = require("crypto");

const OFFLINE_BUNDLE_CEILING_BYTES = 20 * 1024 * 1024;

class IndicPhonemeSyncCompilerJS {
  static compileSyncTrack(text = "", totalDurationMs = 3000) {
    const clean = String(text).trim();
    if (!clean) throw new Error("PhonemeSyncError: empty narration text");
    const tokens = clean.split(/\s+/).filter(Boolean);
    const cues = [];
    let cursor = 0;
    const step = totalDurationMs / tokens.length;
    for (let i = 0; i < tokens.length; i++) {
      const dur = i === tokens.length - 1 ? totalDurationMs - cursor : Math.max(1, Math.round(step));
      cues.push({ index: i, token: tokens[i], start_ms: cursor, end_ms: cursor + dur, duration_ms: dur });
      cursor += dur;
    }
    return { token_count: cues.length, total_duration_ms: totalDurationMs, timing_drift_ms: Math.abs(cursor - totalDurationMs), cues };
  }
}

class Sub20MiBBundleOptimizerJS {
  static computeCasUri(buffer) {
    const digest = crypto.createHash("sha256").update(buffer).digest("hex");
    return `cas://sha256/${digest}`;
  }
}

module.exports = {
  OFFLINE_BUNDLE_CEILING_BYTES,
  IndicPhonemeSyncCompilerJS,
  Sub20MiBBundleOptimizerJS,
};
