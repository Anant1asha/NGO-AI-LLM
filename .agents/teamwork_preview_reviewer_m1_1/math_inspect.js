const fs = require('fs');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

console.log('Validating all 75 questions mathematically...');

// Let's print each question id, prompt, and correct answer
data.questions.forEach((q, idx) => {
  console.log(`[#${idx + 1}] ID: ${q.id} | Tier: ${q.tier}`);
  console.log(`    Q: ${q.q}`);
  console.log(`    Ans: ${q.ans}`);
  const cOpt = q.opts.find(o => o.c === true);
  if (!cOpt || cOpt.t !== q.ans) {
    console.log(`    ERROR: Correct option text "${cOpt ? cOpt.t : 'NONE'}" does NOT match ans "${q.ans}"!`);
  }
});
