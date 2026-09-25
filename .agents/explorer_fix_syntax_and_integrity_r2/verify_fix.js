const fs = require('fs');
const path = require('path');

// 1. Read original file
const originalPath = path.resolve('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/square_cube_questions.json');
const content = fs.readFileSync(originalPath, 'utf8');

// 2. Check original parse error
let originalError = null;
try {
  JSON.parse(content);
} catch (e) {
  originalError = e.message;
}
console.log('Original parse error:', originalError);

// 3. Fix line 300 (missing comma)
const lines = content.split('\n');
console.log('Target line 300 before fix:', lines[299]);
lines[299] = '        "h3": "Compute the cube of 100: 100 cubed has seven digits.",';
console.log('Target line 300 after fix: ', lines[299]);

const fixedContent = lines.join('\n');
const fixedData = JSON.parse(fixedContent);
console.log('Parsed successfully! Title:', fixedData.title, 'Questions:', fixedData.questions.length);

// 4. Test QuestionSchemaValidator
const { QuestionSchemaValidator } = require('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/benchmarks/question_schema_validator');
const valResult = QuestionSchemaValidator.validateExerciseBank(fixedData.questions, 'SquaresCubes_Class8');
console.log('\n--- QuestionSchemaValidator Result ---');
console.log('Passed:', valResult.passed);
console.log('Score:', valResult.score);
console.log('Total Questions:', valResult.totalQuestions);
console.log('Total Distractors:', valResult.totalDistractors);
console.log('Total Hints:', valResult.totalHintsChecked);
console.log('Errors count:', valResult.errors.length);

// 5. Test Math Oracle with fixedContent
// Save fixed file temporarily in our agent folder
const tempFilePath = path.resolve(__dirname, 'temp_square_cube_questions.json');
fs.writeFileSync(tempFilePath, fixedContent, 'utf8');

// Require and run oracle logic pointing to temp file
const oraclePath = path.resolve('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/benchmarks/test_square_cube_math_oracle.js');
let oracleCode = fs.readFileSync(oraclePath, 'utf8');
// Replace target path in oracle
oracleCode = oracleCode.replace(
  "const rawData = fs.readFileSync(questionsPath, 'utf8');",
  `const rawData = fs.readFileSync(${JSON.stringify(tempFilePath)}, 'utf8');`
);

console.log('\n--- Running Math Oracle on Fixed Artifact ---');
// Run using Function
const oracleFn = new Function('require', '__dirname', oracleCode);
oracleFn(require, path.dirname(oraclePath));

// Clean up temp file
if (fs.existsSync(tempFilePath)) {
  fs.unlinkSync(tempFilePath);
}
