/**
 * AASHA Laya System 1 Pre-Router (Cycle 3):
 * SemanticBloomFilterRouterJS & AdaptiveQuantizedModelCascadeJS
 */
const crypto = require("crypto");

class SemanticBloomFilterRouterJS {
  constructor(numBits = 16384, numHashes = 5) {
    this.numBits = numBits;
    this.numHashes = numHashes;
    this.bits = Buffer.alloc(Math.ceil(numBits / 8), 0);
  }
  addToken(token = "") {
    const clean = String(token).trim().toLowerCase();
    if (!clean) return;
    const digest = crypto.createHash("sha256").update(clean).digest();
    const h1 = digest.readUInt32BE(0);
    const h2 = digest.readUInt32BE(4) || 0x9e3779b9;
    for (let i = 0; i < this.numHashes; i++) {
      const idx = (h1 + i * h2) % this.numBits;
      this.bits[idx >> 3] |= 1 << (idx & 7);
    }
  }
}

class AdaptiveQuantizedModelCascadeJS {
  static selectTier(requiredConfidence = 0.7) {
    if (requiredConfidence <= 0.72) return "TIER0_INT4_MICRO";
    if (requiredConfidence <= 0.86) return "TIER1_INT8_FAST";
    if (requiredConfidence <= 0.94) return "TIER2_FP16_LOCAL_PRO";
    return "TIER3_CLOUD_SYSTEM2";
  }
}

module.exports = {
  SemanticBloomFilterRouterJS,
  AdaptiveQuantizedModelCascadeJS,
};
