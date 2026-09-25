const fs = require('fs');
const bmSource = fs.readFileSync('Aasha-AI/benchmarks/qa_ltruth_benchmark.js', 'utf8');
const customTarget = 'const targetFiles = [path.resolve("Aasha-AI/chapters/RationalNumbers_Class8_MDS.html"), path.resolve("Aasha-AI/chapters/ExponentsPowers_Class8_MDS.html")];';
const modified = bmSource.replace(/const targetFiles = \[[\s\S]*?\];/, customTarget);
eval(modified);