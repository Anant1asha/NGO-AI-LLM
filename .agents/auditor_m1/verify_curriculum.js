const fs = require('fs');
const path = require('path');

const filePath = path.resolve(__dirname, '../../Aasha-AI/chapters/square_cube_questions.json');
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split(/\r?\n/);
if (lines[299].includes('"h3"') && !lines[299].trim().endsWith(',')) {
  lines[299] = lines[299] + ',';
}
const data = JSON.parse(lines.join('\n'));

console.log('Total questions:', data.questions.length);
data.questions.forEach((q, i) => {
  console.log(`[Q${i+1}] ID: ${q.id} | Tier: ${q.tier} | Tag: ${q.tag}`);
  console.log(`    Prompt: ${q.q.substring(0, 80)}...`);
  console.log(`    Ans: ${q.ans}`);
  console.log(`    Opts count: ${q.opts.length} | Has correct: ${q.opts.some(o => o.c)}`);
  const distractorsWithM = q.opts.filter(o => !o.c && o.m && o.m.length > 15).length;
  console.log(`    Distractors with valid m (>15 chars): ${distractorsWithM}/${q.opts.length - 1}`);
  const hintCount = q.hints ? Object.keys(q.hints).length : 0;
  console.log(`    Hints: ${hintCount}`);
});
