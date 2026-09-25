const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const vm = require('vm');

// 1. Read step 24 output (direct from Hatchable read_file)
const step24Path = "C:/Users/admin/.gemini/antigravity/brain/d20a2ff5-00b1-47e5-b187-491d6f51dc36/.system_generated/steps/24/output.txt";
const step24Raw = fs.readFileSync(step24Path, 'utf8');
const step24Json = JSON.parse(step24Raw);
const remoteCode = step24Json.content;

// 2. Read worker_1's local deltas.js
const workerCodePath = "c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_worker_1/deltas.js";
const workerCode = fs.readFileSync(workerCodePath, 'utf8');

// Compare SHA-256
const remoteHash = crypto.createHash('sha256').update(remoteCode).digest('hex');
const workerHash = crypto.createHash('sha256').update(workerCode).digest('hex');

console.log("=== REMOTE VS LOCAL INTEGRITY ===");
console.log(`Remote Code Bytes: ${Buffer.byteLength(remoteCode, 'utf8')}`);
console.log(`Worker Code Bytes: ${Buffer.byteLength(workerCode, 'utf8')}`);
console.log(`Remote SHA-256: ${remoteHash}`);
console.log(`Worker SHA-256: ${workerHash}`);
console.log(`Exact Byte Match: ${remoteHash === workerHash}`);

// Write remote code to our audit directory
fs.writeFileSync(path.join(__dirname, 'remote_deltas.js'), remoteCode, 'utf8');

// 3. Extract DELTA_REGISTRY and inspect
// We can strip exports and evaluate in VM
let executableCode = remoteCode
  .replace(/export const access = [^;]+;/g, '')
  .replace(/export const methods = [^;]+;/g, '')
  .replace(/export default async function/g, 'async function handleRequest')
  + '\nmodule.exports = { DELTA_REGISTRY, handleRequest };';

const sandbox = { module: { exports: {} }, exports: {}, console };
vm.createContext(sandbox);
vm.runInContext(executableCode, sandbox);

const { DELTA_REGISTRY } = sandbox.module.exports;
console.log("\n=== REGISTRY OVERVIEW ===");
console.log("Chapters found:", Object.keys(DELTA_REGISTRY));

// 4. Detailed Audit
const FORBIDDEN_WORDS = /\b(is|giving|becomes|instead of|to get|yielding|result is|should be)\b/i;

let totalQuestions = 0;
let totalOptions = 0;
let totalDistractors = 0;
let forbiddenWordViolations = [];
let shortExplanationViolations = [];
let optionCountViolations = [];
let correctCountViolations = [];
let hintTierViolations = [];
let calculationLeakViolations = [];

for (const [chapterId, chapter] of Object.entries(DELTA_REGISTRY)) {
  console.log(`\n--- Chapter: ${chapterId} (Grade ${chapter.grade}) ---`);
  console.log(`Title: ${chapter.title}`);
  console.log(`Version: ${chapter.version}`);
  console.log(`F01 Mechanics:`, chapter.f01Mechanics);
  console.log(`Visual Manipulatives:`, Object.keys(chapter.visualManipulatives || {}));
  console.log(`Vocab Count:`, Object.keys(chapter.vocab || {}).length);
  console.log(`Questions Count: ${chapter.itemBank.length}`);

  const items = chapter.itemBank;
  totalQuestions += items.length;

  for (const q of items) {
    // Check option count
    if (!q.options || q.options.length !== 4) {
      optionCountViolations.push({ id: q.id, count: q.options ? q.options.length : 0 });
    }

    // Check correct count
    const correctOpts = q.options.filter(o => o.isCorrect === true);
    if (correctOpts.length !== 1) {
      correctCountViolations.push({ id: q.id, correctCount: correctOpts.length });
    }
    const correctText = correctOpts[0] ? correctOpts[0].text : '';

    // Check distractors
    for (let i = 0; i < q.options.length; i++) {
      totalOptions++;
      const opt = q.options[i];
      if (!opt.isCorrect) {
        totalDistractors++;
        if (!opt.m || opt.m.length < 15) {
          shortExplanationViolations.push({ id: q.id, optIndex: i, m: opt.m });
        }
        if (opt.m && FORBIDDEN_WORDS.test(opt.m)) {
          const match = opt.m.match(FORBIDDEN_WORDS);
          forbiddenWordViolations.push({ id: q.id, optIndex: i, word: match[0], m: opt.m });
        }
        // Check calculation leaks
        // Rule: "Misconception explanations (m attribute) must never include arithmetic calculations that evaluate to the correct answer value (e.g., avoid "yields 2", "gives 4", or "= -5" when that value matches the target answer)."
        if (opt.m && correctText) {
          // If correct answer is a pure number or fraction, check if opt.m contains explicit evaluation
          // e.g. " = X" or "yields X" or "gives X"
          const cleanCorrect = correctText.replace(/\\\(|\\\)/g, '').replace(/m²|cm²|m|cm|min|hours|Rs/g, '').trim();
          if (cleanCorrect && cleanCorrect.length <= 5 && opt.m.includes(cleanCorrect)) {
            // Check if context looks like calculation
            calculationLeakViolations.push({ id: q.id, optIndex: i, cleanCorrect, m: opt.m });
          }
        }
      }
    }

    // Check hints
    if (!q.hints || q.hints.length !== 4) {
      hintTierViolations.push({ id: q.id, hintCount: q.hints ? q.hints.length : 0 });
    } else {
      const tiers = q.hints.map(h => h.tier);
      if (tiers.join(',') !== 'H1,H2,H3,H4') {
        hintTierViolations.push({ id: q.id, tiers });
      }
    }
  }
}

console.log("\n================ AUDIT SUMMARY ================");
console.log(`Total Questions: ${totalQuestions} (Expected: 43)`);
console.log(`Total Options: ${totalOptions} (Expected: 172)`);
console.log(`Total Distractors: ${totalDistractors} (Expected: 129)`);
console.log(`Forbidden Word Violations: ${forbiddenWordViolations.length}`);
if (forbiddenWordViolations.length > 0) {
  console.log("VIOLATIONS:", JSON.stringify(forbiddenWordViolations, null, 2));
}
console.log(`Short Explanation Violations (<15 chars): ${shortExplanationViolations.length}`);
if (shortExplanationViolations.length > 0) {
  console.log("VIOLATIONS:", JSON.stringify(shortExplanationViolations, null, 2));
}
console.log(`Option Count Violations (!== 4): ${optionCountViolations.length}`);
if (optionCountViolations.length > 0) {
  console.log("VIOLATIONS:", JSON.stringify(optionCountViolations, null, 2));
}
console.log(`Correct Option Count Violations (!== 1): ${correctCountViolations.length}`);
if (correctCountViolations.length > 0) {
  console.log("VIOLATIONS:", JSON.stringify(correctCountViolations, null, 2));
}
console.log(`Hint Tier Violations (!== H1..H4): ${hintTierViolations.length}`);
if (hintTierViolations.length > 0) {
  console.log("VIOLATIONS:", JSON.stringify(hintTierViolations, null, 2));
}
console.log(`Calculation Leak Suspicion Count: ${calculationLeakViolations.length}`);
if (calculationLeakViolations.length > 0) {
  console.log("CALCULATION LEAK SUSPICIONS:", JSON.stringify(calculationLeakViolations, null, 2));
}
