const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const aashaDir = path.resolve(__dirname, '..', '..', 'Aasha-AI');

try {
  const status = execSync('git status --porcelain benchmarks/qa_ltruth_benchmark.js benchmarks/question_schema_validator.js', {
    cwd: aashaDir,
    encoding: 'utf8'
  });
  console.log('GIT STATUS FOR BENCHMARK FILES:');
  console.log(status ? status : '[CLEAN - NO MODIFICATIONS]');

  const diff = execSync('git diff HEAD benchmarks/qa_ltruth_benchmark.js benchmarks/question_schema_validator.js', {
    cwd: aashaDir,
    encoding: 'utf8'
  });
  console.log('\nGIT DIFF FOR BENCHMARK FILES:');
  console.log(diff ? diff : '[EMPTY DIFF - IDENTICAL TO COMMIT HEAD]');
} catch (e) {
  console.error('Error executing git command:', e.message);
}
