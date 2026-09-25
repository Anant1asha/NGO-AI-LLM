const { QuestionSchemaValidator } = require('../../Aasha-AI/benchmarks/question_schema_validator');
const { AUTHORITATIVE_34_QUESTIONS } = require('../../tests/e2e_square_cube_suite');

const res = QuestionSchemaValidator.validateExerciseBank(AUTHORITATIVE_34_QUESTIONS);
console.log('Total errors:', res.errors.length);
res.errors.forEach((e, i) => console.log(`${i+1}. [${e.ruleId}] [${e.questionId}] ${e.message}`));
