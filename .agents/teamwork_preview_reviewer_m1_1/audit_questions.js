const fs = require('fs');
const path = require('path');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

console.log('=== DATA METRICS ===');
console.log('Total questions:', data.questions.length);

let totalOpts = 0;
let badOptCount = 0;
let badCorrectCount = 0;
let correctNotMEmpty = 0;
let distractorMShort = 0;
let duplicateOpts = 0;
let missingHints = 0;

data.questions.forEach((q, idx) => {
  if (!q.opts || q.opts.length !== 4) {
    console.log(`[Q ${q.id}] Option count is not 4:`, q.opts ? q.opts.length : 0);
    badOptCount++;
  }
  const corrects = (q.opts || []).filter(o => o.c === true);
  if (corrects.length !== 1) {
    console.log(`[Q ${q.id}] Correct options count != 1:`, corrects.length);
    badCorrectCount++;
  } else {
    if (corrects[0].m && corrects[0].m.trim().length > 0) {
      console.log(`[Q ${q.id}] Correct option has non-empty m:`, corrects[0].m);
      correctNotMEmpty++;
    }
  }

  const seenOpts = new Set();
  (q.opts || []).forEach((opt, oIdx) => {
    if (seenOpts.has(opt.t)) {
      console.log(`[Q ${q.id}] Duplicate option text:`, opt.t);
      duplicateOpts++;
    }
    seenOpts.add(opt.t);

    if (!opt.c) {
      if (!opt.m || opt.m.trim().length < 15) {
        console.log(`[Q ${q.id}] Distractor ${oIdx} m is < 15 chars: "${opt.m}"`);
        distractorMShort++;
      }
    }
  });

  if (!q.hints || !q.hints.h1 || !q.hints.h2 || !q.hints.h3 || !q.hints.h4) {
    console.log(`[Q ${q.id}] Missing hints:`, q.hints);
    missingHints++;
  }
});

console.log('--- Summary ---');
console.log('badOptCount:', badOptCount);
console.log('badCorrectCount:', badCorrectCount);
console.log('correctNotMEmpty:', correctNotMEmpty);
console.log('distractorMShort:', distractorMShort);
console.log('duplicateOpts:', duplicateOpts);
console.log('missingHints:', missingHints);
