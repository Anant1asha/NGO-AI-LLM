const fs = require('fs');
const { QuestionSchemaValidator } = require('c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/benchmarks/question_schema_validator.js');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

const res = QuestionSchemaValidator.validateExerciseBank(data, 'ad_all_questions.json');

console.log('Total errors:', res.errors.length);
res.errors.forEach((err, idx) => {
  console.log(`\n--- Error #${idx + 1} ---`);
  console.log('Question ID:', err.questionId);
  console.log('Rule:', err.ruleId);
  console.log('Message:', err.message);
  
  const q = data.questions.find(x => x.id === err.questionId);
  if (q) {
    console.log('Prompt:', q.q);
    console.log('Correct Ans:', q.ans);
    console.log('Hints:', JSON.stringify(q.hints, null, 2));
    console.log('Opts:');
    q.opts.forEach((o, oi) => {
      console.log(`  Opt [${oi}] c=${o.c}: "${o.t}" | m: "${o.m}"`);
    });
  }
});
