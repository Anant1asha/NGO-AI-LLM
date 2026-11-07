// Seeded file


export class MerkleSnapshotDiffEngineTS {
  static computeMerkleRoot(payload = {}) {
    const keys = Object.keys(payload).sort();
    if (keys.length === 0) return crypto.createHash("sha256").update("EMPTY").digest("hex");
    let level = keys.map((k) => crypto.createHash("sha256").update(`${k}:${JSON.stringify(payload[k])}`).digest("hex"));
    while (level.length > 1) {
      const next = [];
      for (let i = 0; i < level.length; i += 2) {
        const left = level[i];
        const right = i + 1 < level.length ? level[i + 1] : left;
        next.push(crypto.createHash("sha256").update(`${left}|${right}`).digest("hex"));
      }
      level = next;
    }
    return level[0];
  }
}
