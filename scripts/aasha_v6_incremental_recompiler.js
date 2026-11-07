/**
 * AASHA V6 Canonical IR Compiler (Cycle 3):
 * IncrementalASTDifferentialRecompilerJS & CrossGradeMasteryTransferMatrixJS
 */
const crypto = require("crypto");

class IncrementalASTDifferentialRecompilerJS {
  static computeNodeSignature(node, parentSigs = []) {
    const payload = JSON.stringify({ ...node, parentSigs });
    return crypto.createHash("sha256").update(payload).digest("hex");
  }
}

class CrossGradeMasteryTransferMatrixJS {
  static computeEffectiveMastery(observed, parentPrior, weight = 0.65) {
    return Number(((1 - weight) * observed + weight * Math.min(observed, parentPrior)).toFixed(4));
  }
}

module.exports = {
  IncrementalASTDifferentialRecompilerJS,
  CrossGradeMasteryTransferMatrixJS,
};
