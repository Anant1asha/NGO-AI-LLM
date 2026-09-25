const fs = require('fs');
const path = require('path');
const { QuestionSchemaValidator } = require('../../Aasha-AI/benchmarks/question_schema_validator');

const filePath = path.resolve(__dirname, '../../Aasha-AI/chapters/square_cube_questions.json');
const raw = fs.readFileSync(filePath, 'utf8');

console.log('--- Testing Raw JSON Parse ---');
let parsedData = null;
try {
  parsedData = JSON.parse(raw);
  console.log('Raw JSON parsed successfully.');
} catch (e) {
  console.error('Raw JSON parse failed:', e.message);
}

// Now test with the missing comma fixed in memory
console.log('\n--- Testing In-Memory Repaired JSON Parse ---');
const lines = raw.split(/\r?\n/);
console.log('Line 300:', lines[299]);
console.log('Line 301:', lines[300]);

const fixedLines = [...lines];
if (fixedLines[299].includes('"h3"') && !fixedLines[299].trim().endsWith(',')) {
  fixedLines[299] = fixedLines[299] + ',';
}

const fixedRaw = fixedLines.join('\n');
try {
  const data = JSON.parse(fixedRaw);
  console.log('Fixed JSON parsed successfully! Total questions:', data.questions.length);

  // Run validator
  const result = QuestionSchemaValidator.validateExerciseBank(data.questions, 'SquaresCubes_Class8');
  console.log('\n--- Validator Result on In-Memory Fixed Data ---');
  console.log('Passed:', result.passed);
  console.log('Score:', result.score);
  console.log('Total Questions:', result.totalQuestions);
  console.log('Total Distractors:', result.totalDistractors);
  console.log('Total Hints Checked:', result.totalHintsChecked);
  console.log('Spoiler Violations:', result.spoilerViolations);
  console.log('Missing Misconceptions:', result.missingMisconceptions);
  console.log('Low Quality Misconceptions:', result.lowQualityMisconceptions);
  console.log('Structure Violations:', result.structureViolations);
  console.log('Hint Violations:', result.hintViolations);
  console.log('Errors:', JSON.stringify(result.errors, null, 2));
  console.log('Warnings:', JSON.stringify(result.warnings, null, 2));
} catch (e) {
  console.error('Fixed JSON parse or validation failed:', e.message);
}
