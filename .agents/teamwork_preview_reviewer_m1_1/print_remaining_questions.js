const fs = require('fs');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

for (let i = 20; i < data.questions.length; i++) {
  const q = data.questions[i];
  console.log(`[${i + 1}] ID: ${q.id} (${q.tag}) [${q.tier}]`);
  console.log(`     Q: ${q.q}`);
  console.log(`     Ans: ${q.ans}`);
}
