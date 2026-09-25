const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '../../Aasha-AI');
const questionsPath = path.join(repoRoot, 'chapters/square_cube_questions.json');
let raw = fs.readFileSync(questionsPath, 'utf8');

// Fix comma at line 300 for memory parsing
const lines = raw.split('\n');
if (!lines[299].trim().endsWith(',')) {
  lines[299] = lines[299].replace(/\"$/, '\",');
}
raw = lines.join('\n');

const data = JSON.parse(raw);
const { QuestionSchemaValidator } = require(path.join(repoRoot, 'benchmarks/question_schema_validator'));

console.log('Total questions parsed:', data.questions.length);

const targetIds = [
  'sc_q34', 'sc_q31', 'sc_q30', 'sc_q21', 'sc_q13', 'sc_q15', 'sc_q22', 'sc_q27', 'sc_q17', 'sc_q28'
];

targetIds.forEach(id => {
  const q = data.questions.find(x => x.id === id);
  if (!q) {
    console.log('NOT FOUND:', id);
    return;
  }
  console.log('\n========================================');
  console.log(`ID: ${q.id} (${q.tag}) [Tier: ${q.tier}]`);
  console.log(`Question: ${q.q}`);
  console.log(`Correct Ans: ${q.ans}`);
  console.log('Options:');
  q.opts.forEach((opt, idx) => {
    console.log(`  [${idx + 1}] ${opt.c ? 'CORRECT' : 'DISTRACTOR'}: "${opt.t}"`);
    if (opt.m) console.log(`      m: "${opt.m}"`);
  });
  console.log('Hints:');
  console.log(`  h1: "${q.hints.h1}"`);
  console.log(`  h2: "${q.hints.h2}"`);
  console.log(`  h3: "${q.hints.h3}"`);
  console.log(`  h4: "${q.hints.h4}"`);

  // Run validator on this question
  const errs = QuestionSchemaValidator.validateQuestion(q);
  console.log(`Validation Errors count: ${errs.length}`);
  if (errs.length > 0) {
    errs.forEach(e => console.log(`  - [${e.ruleId}] ${e.message}`));
  }
});
