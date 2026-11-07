/**
 * AASHA Cycle 6 Zero-Internet Local Wi-Fi Direct / QR-Chunk Merkle Delta Sync Protocol (JS Parity)
 */
class OfflineQRAndMeshChunkEncoderJS {
  static xorBuffers(bufA, bufB) {
    const len = Math.max(bufA.length, bufB.length);
    const out = Buffer.alloc(len, 0);
    for (let i = 0; i < len; i++) {
      out[i] = (bufA[i] || 0) ^ (bufB[i] || 0);
    }
    return out;
  }
}

class PeerToPeerMeshGossipSynchronizerJS {
  static getMaxGossipRounds() {
    return 2;
  }
}

module.exports = {
  OfflineQRAndMeshChunkEncoderJS,
  PeerToPeerMeshGossipSynchronizerJS,
};
