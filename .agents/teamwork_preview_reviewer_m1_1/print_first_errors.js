const fs = require('fs');
const { QuestionSchemaValidator } = require('c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/benchmarks/question_schema_validator.js');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

const res = QuestionSchemaValidator.validateExerciseBank(data, 'ad_all_questions.json');

for (let i = 0; i < Math.min(14, res.errors.length); i++) {
  const err = res.errors[i];
  console.log(`[${i + 1}] [${err.ruleId}] ${err.questionId}: ${err.message}`);
  const q = data.questions.find(x => x.id === err.questionId);
  console.log(`    Ans: "${q.ans}"`);
}
