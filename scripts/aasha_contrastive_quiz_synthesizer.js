/**
 * AASHA Cycle 6 Autonomous Bilingual Distractor & Contrastive Misconception Quiz Synthesizer (JS Parity)
 */
const crypto = require("crypto");

class ContrastiveMisconceptionQuizSynthesizerJS {
  static hashOptionKey(questionId, optionId) {
    return crypto.createHash("sha256").update(`${questionId}:${optionId}`).digest("hex");
  }
}

module.exports = {
  ContrastiveMisconceptionQuizSynthesizerJS,
};
