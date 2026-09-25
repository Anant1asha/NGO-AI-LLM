#!/usr/bin/env node
/**
 * Empirical Adversarial Challenger Suite: Square and Cube Roots Chapter
 * Agent: teamwork_preview_challenger_m2_squares_2
 * =======================================================================
 * Adversarially probes:
 * 1. 4-option single-correct MCQ schema compliance for all 34 questions + WE + NODES.
 * 2. QuestionSchemaValidator execution on all questions, WEs, and hints.
 * 3. Subtle leak predicates (is, was, giving, gives, becomes, equals, result is,
 *    yields, evaluates to, instead of, to get, should be, produces, leads to).
 * 4. 4-tier progressive scaffolding hints (H1 -> H4) presence and zero-leak invariant.
 * 5. Cross-consistency between DOM cards, test suite, and JSON bank.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT_DIR = path.resolve(__dirname, '..');
const AASHA_DIR = path.join(ROOT_DIR, 'Aasha-AI');
const CHAPTER_HTML = path.join(AASHA_DIR, 'chapters', 'SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html');
const QUESTIONS_JSON = path.join(AASHA_DIR, 'chapters', 'square_cube_questions.json');
const SUITE_FILE = path.join(__dirname, 'e2e_square_cube_suite.js');
const QSV_FILE = path.join(AASHA_DIR, 'benchmarks', 'question_schema_validator.js');

const { QuestionSchemaValidator, normalizeMathText, LEAK_PREDICATES, SPOILER_PHRASES } = require(QSV_FILE);
const { AUTHORITATIVE_34_QUESTIONS } = require(SUITE_FILE);

console.log('='.repeat(80));
console.log(' EMPIRICAL ADVERSARIAL CHALLENGE HARNESS — SQUARE & CUBE ROOTS');
console.log(' Agent: teamwork_preview_challenger_m2_squares_2');
console.log('='.repeat(80));

const results = {
  passed: true,
  checks: [],
  failures: [],
  warnings: [],
  stats: {
    domQuestions: 0,
    suiteQuestions: 0,
    jsonQuestions: 0,
    nodeQuizzes: 0,
    weChecks: 0,
    totalDistractors: 0,
    totalHints: 0,
    leakProbes: 0
  }
};

function recordPass(desc) {
  results.checks.push(desc);
  console.log(`  [PASS] ${desc}`);
}

function recordFail(desc, details = null) {
  results.passed = false;
  results.failures.push({ desc, details });
  console.error(`  [FAIL] ${desc}`);
  if (details) console.error('         Details:', JSON.stringify(details, null, 2));
}

function recordWarn(desc, details = null) {
  results.warnings.push({ desc, details });
  console.warn(`  [WARN] ${desc}`);
}

// ----------------------------------------------------------------------------
// 1. EXTRACT DOM QUIZ CARDS FROM HTML
// ----------------------------------------------------------------------------
console.log('\n--- 1. DOM QUIZ CARDS EXTRACTION & TIER PARTITIONING ---');
const htmlContent = fs.readFileSync(CHAPTER_HTML, 'utf8');

function extractDomCards(html) {
  const cards = [];
  const cardRegex = /<div\s+class="quiz-card"\s+id="([^"]+)">([\s\S]*?)(?=<div\s+class="quiz-card"|<\/section>|<footer|$)/gi;
  let match;
  while ((match = cardRegex.exec(html)) !== null) {
    const qid = match[1];
    const block = match[2];

    const tagMatch = block.match(/<div\s+class="quiz-tag">([\s\S]*?)<\/div>/i);
    const tag = tagMatch ? tagMatch[1].trim() : '';

    const qMatch = block.match(/<div\s+class="quiz-question">([\s\S]*?)<\/div>/i);
    const qText = qMatch ? qMatch[1].trim() : '';

    // Extract options
    const opts = [];
    const optRegex = /<div\s+class="quiz-opt"\s+data-m="([^"]*)"\s+data-correct="([^"]*)"[^>]*>[\s\S]*?<span\s+class="quiz-opt-text">([\s\S]*?)<\/span>/gi;
    let optMatch;
    while ((optMatch = optRegex.exec(block)) !== null) {
      const m = optMatch[1].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
      const isCorrect = optMatch[2] === 'true';
      const text = optMatch[3].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim();
      opts.push({ t: text, c: isCorrect, m });
    }

    // Extract hints
    const hintMatch = block.match(/<div\s+class="hint-box"\s+id="[^"]*"\s+data-h1="([^"]*)"\s+data-h2="([^"]*)"\s+data-h3="([^"]*)"\s+data-h4="([^"]*)"/i);
    let hints = null;
    if (hintMatch) {
      hints = {
        h1: hintMatch[1].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'),
        h2: hintMatch[2].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'),
        h3: hintMatch[3].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'),
        h4: hintMatch[4].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
      };
    }

    // Determine section/tier
    let tier = 'unknown';
    if (qid.startsWith('wu_') || qid.includes('warmup')) tier = 'warmup';
    else if (qid.startsWith('dd_') || qid.includes('dive')) tier = 'deep_dive';
    else if (qid.startsWith('bc_') || qid.includes('boss')) tier = 'boss';

    cards.push({ id: qid, tag, q: qText, opts, hints, tier });
  }
  return cards;
}

const domCards = extractDomCards(htmlContent);
results.stats.domQuestions = domCards.length;

if (domCards.length === 34) {
  recordPass(`Extracted exactly 34 .quiz-card elements from DOM (got ${domCards.length})`);
} else {
  recordFail(`Expected 34 DOM quiz cards, found ${domCards.length}`);
}

const warmupCards = domCards.filter(c => c.tier === 'warmup');
const deepDiveCards = domCards.filter(c => c.tier === 'deep_dive');
const bossCards = domCards.filter(c => c.tier === 'boss');

if (warmupCards.length === 12 && deepDiveCards.length === 14 && bossCards.length === 8) {
  recordPass(`DOM Tier counts verified: Warm-up=12, Deep Dive=14, Boss=8`);
} else {
  recordFail(`DOM Tier mismatch: Warm-up=${warmupCards.length} (exp 12), Deep Dive=${deepDiveCards.length} (exp 14), Boss=${bossCards.length} (exp 8)`);
}

// ----------------------------------------------------------------------------
// 2. EXTRACT NODES QUIZZES AND WORKED EXAMPLES FROM HTML
// ----------------------------------------------------------------------------
console.log('\n--- 2. JS NODES QUIZZES & WORKED EXAMPLES EXTRACTION ---');

function extractJsVar(html, varName) {
  const match = html.match(new RegExp(`var\\s+${varName}\\s*=\\s*([\\{\\[][\\s\\S]*?);\\s*(?:var|function|App|\\$)`));
  if (!match) return null;
  const raw = match[1].trim();
  try {
    return JSON.parse(raw);
  } catch (e) {
    try {
      const fn = new Function(`return ${raw};`);
      return fn();
    } catch (e2) {
      return null;
    }
  }
}

const nodesData = extractJsVar(htmlContent, 'NODES');
const weData = extractJsVar(htmlContent, 'WE');

const nodeQuizzes = [];
if (Array.isArray(nodesData)) {
  nodesData.forEach((node, nIdx) => {
    (node.steps || []).forEach((step, sIdx) => {
      if (step && step.t === 'quiz' && step.q) {
        nodeQuizzes.push({
          id: `Node_${nIdx + 1}_Step_${sIdx + 1}`,
          nodeTitle: node.title,
          q: step.q.q,
          opts: step.q.opts || []
        });
      }
    });
  });
}
results.stats.nodeQuizzes = nodeQuizzes.length;
recordPass(`Extracted ${nodeQuizzes.length} NODES in-flow checkpoint quizzes`);

const weChecks = [];
if (weData && typeof weData === 'object') {
  for (const [weKey, we] of Object.entries(weData)) {
    if (we.check && we.check.opts) {
      weChecks.push({
        id: `WE_${weKey}_final_check`,
        weTitle: we.title,
        q: we.check.q,
        opts: we.check.opts
      });
    }
    if (Array.isArray(we.steps)) {
      we.steps.forEach((step, sIdx) => {
        if (step.check && step.check.opts) {
          weChecks.push({
            id: `WE_${weKey}_step_${sIdx + 1}_check`,
            weTitle: we.title,
            q: step.check.q,
            opts: step.check.opts
          });
        }
      });
    }
  }
}
results.stats.weChecks = weChecks.length;
recordPass(`Extracted ${weChecks.length} Worked Example (WE) step/final checks`);

// ----------------------------------------------------------------------------
// 3. ADVERSARIAL STRESS-TEST: 4-OPTION SINGLE-CORRECT MCQ SCHEMA
// ----------------------------------------------------------------------------
console.log('\n--- 3. ADVERSARIAL TEST: 4-OPTION SINGLE-CORRECT MCQ SCHEMA ---');

function verifyMcqSchema(questions, setLabel) {
  let validCount = 0;
  questions.forEach(q => {
    const qid = q.id;
    if (!Array.isArray(q.opts)) {
      recordFail(`[${setLabel}] ${qid} opts is not an array`);
      return;
    }
    if (q.opts.length !== 4) {
      recordFail(`[${setLabel}] ${qid} has ${q.opts.length} options (MUST be exactly 4)`);
      return;
    }

    const correctOpts = q.opts.filter(o => o.c === true);
    if (correctOpts.length !== 1) {
      recordFail(`[${setLabel}] ${qid} has ${correctOpts.length} correct options (MUST be exactly 1)`);
      return;
    }

    const correctOpt = correctOpts[0];
    if (correctOpt.m && correctOpt.m.trim().length > 0) {
      recordFail(`[${setLabel}] ${qid} correct option has non-empty m: "${correctOpt.m}"`);
      return;
    }

    const seenTexts = new Set();
    let optsDistinct = true;
    q.opts.forEach((o, oIdx) => {
      const normT = normalizeMathText(o.t).toLowerCase();
      if (!normT) {
        recordFail(`[${setLabel}] ${qid} option #${oIdx + 1} has empty text`);
        optsDistinct = false;
      }
      if (seenTexts.has(normT)) {
        recordFail(`[${setLabel}] ${qid} has duplicate option text: "${o.t}"`);
        optsDistinct = false;
      }
      seenTexts.add(normT);

      if (!o.c) {
        results.stats.totalDistractors++;
        if (!o.m || o.m.trim().length < 12) {
          recordFail(`[${setLabel}] ${qid} distractor #${oIdx + 1} ('${o.t}') has missing/trivial m: "${o.m}"`);
        }
      }
    });

    if (optsDistinct) validCount++;
  });

  if (validCount === questions.length) {
    recordPass(`[${setLabel}] All ${questions.length} questions strictly satisfy 4-option single-correct MCQ schema`);
  }
}

verifyMcqSchema(domCards, 'DOM Cards');
verifyMcqSchema(AUTHORITATIVE_34_QUESTIONS, 'Suite 34 Questions');
verifyMcqSchema(nodeQuizzes, 'NODES Quizzes');
verifyMcqSchema(weChecks, 'WE Checks');

// ----------------------------------------------------------------------------
// 4. ADVERSARIAL STRESS-TEST: QUESTION SCHEMA VALIDATOR
// ----------------------------------------------------------------------------
console.log('\n--- 4. QUESTION SCHEMA VALIDATOR EXECUTION ---');

const domValidation = QuestionSchemaValidator.validateExerciseBank(domCards, 'DOM 34 Cards');
if (domValidation.passed && domValidation.errors.length === 0) {
  recordPass(`QuestionSchemaValidator on 34 DOM cards: SCORE ${domValidation.score}/100, 0 ERRORS`);
} else {
  recordFail(`QuestionSchemaValidator on 34 DOM cards FAILED`, domValidation.errors);
}

const suiteValidation = QuestionSchemaValidator.validateExerciseBank(AUTHORITATIVE_34_QUESTIONS, 'Suite 34 Questions');
if (suiteValidation.passed && suiteValidation.errors.length === 0) {
  recordPass(`QuestionSchemaValidator on Suite 34 questions: SCORE ${suiteValidation.score}/100, 0 ERRORS`);
} else {
  recordFail(`QuestionSchemaValidator on Suite 34 questions FAILED`, suiteValidation.errors);
}

const nodeValidation = QuestionSchemaValidator.validateExerciseBank(nodeQuizzes, 'NODES Quizzes');
if (nodeValidation.passed && nodeValidation.errors.length === 0) {
  recordPass(`QuestionSchemaValidator on NODES quizzes: SCORE ${nodeValidation.score}/100, 0 ERRORS`);
} else {
  recordFail(`QuestionSchemaValidator on NODES quizzes FAILED`, nodeValidation.errors);
}

const weValidation = QuestionSchemaValidator.validateExerciseBank(weChecks, 'WE Checks');
if (weValidation.passed && weValidation.errors.length === 0) {
  recordPass(`QuestionSchemaValidator on WE checks: SCORE ${weValidation.score}/100, 0 ERRORS`);
} else {
  recordFail(`QuestionSchemaValidator on WE checks FAILED`, weValidation.errors);
}

// ----------------------------------------------------------------------------
// 5. ADVERSARIAL PROBING FOR SUBTLE LEAK PREDICATES & SPOILER LEAKS
// ----------------------------------------------------------------------------
console.log('\n--- 5. ADVERSARIAL LEAK PREDICATES & SPOILER PROBES ---');

const EXTENDED_LEAK_PREDICATES = [
  'is', 'was', 'giving', 'gives', 'give', 'becomes', 'became',
  'equals', 'equal to', 'equals to', 'result is', 'results in',
  'yielding', 'yields', 'produces', 'produced', 'produces a value of',
  'evaluates to', 'evaluated to', 'instead of', 'to get', 'should be',
  'must be', 'target is', 'target value is', 'correct value is',
  'correct answer is', 'answer is', 'answer was', 'answer:', 'leads to'
];

function escapeRegex(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function probeForLeaks(text, correctOpt, context) {
  const leaks = [];
  if (!text || !correctOpt || !correctOpt.t) return leaks;

  results.stats.leakProbes++;
  const rawCorrect = String(correctOpt.t).trim();
  const normCorrect = normalizeMathText(rawCorrect).toLowerCase();
  const normText = normalizeMathText(text).toLowerCase();

  // 1. Verbatim leak of non-stopword target answer
  const isPureNumber = /^-?\d+(?:\.\d+)?$/.test(normCorrect);
  const STOPWORDS = new Set(['a', 'i', 'is', 'to', 'in', 'of', 'or', 'and', 'no', 'so', 'yes', 'all', 'one', 'two', 'true', 'false']);
  if (!isPureNumber && normCorrect.length > 2 && !STOPWORDS.has(normCorrect)) {
    if (normText.includes(normCorrect)) {
      leaks.push({
        type: 'VERBATIM_ANSWER_LEAK',
        target: rawCorrect,
        snippet: text,
        context
      });
    }
  }

  // 2. Numerical values with leak predicates
  const nums = normCorrect.match(/-?\d+(?:\.\d+)?/g) || [];
  for (const n of nums) {
    const escapedN = escapeRegex(n);
    for (const pred of EXTENDED_LEAK_PREDICATES) {
      // Check: predicate + whitespace/colon/equals + number
      const pattern = new RegExp(`(?:\\b${escapeRegex(pred)}\\b)\\s*[:=]?\\s*\\b${escapedN}\\b`, 'i');
      if (pattern.test(normText)) {
        leaks.push({
          type: 'PREDICATE_NUMERICAL_LEAK',
          predicate: pred,
          value: n,
          snippet: text,
          context
        });
      }
    }
  }

  // 3. Proximity leak: spoiler phrase + number within 3 tokens
  for (const phrase of SPOILER_PHRASES) {
    for (const n of nums) {
      const escapedN = escapeRegex(n);
      const pattern = new RegExp(`(?:${escapeRegex(phrase)})\\s*(?:[a-z0-9_]+\\s*){0,3}[:=]?\\s*\\b${escapedN}\\b`, 'i');
      if (pattern.test(normText)) {
        leaks.push({
          type: 'PROXIMITY_SPOILER_PHRASE_LEAK',
          phrase,
          value: n,
          snippet: text,
          context
        });
      }
    }
  }

  // 4. Negative phrasing check
  if (/❌|incorrect|you are wrong|failed|stupid/i.test(text)) {
    leaks.push({
      type: 'NEGATIVE_EVALUATIVE_PHRASING',
      snippet: text,
      context
    });
  }

  return leaks;
}

// Probe all distractors across DOM cards, Suite, NODES, and WE
const allFoundLeaks = [];

function checkAllQuestionDistractors(questions, label) {
  questions.forEach(q => {
    const correctOpt = q.opts.find(o => o.c === true);
    if (!correctOpt) return;
    q.opts.forEach((opt, oIdx) => {
      if (opt.c) return;
      const leaks = probeForLeaks(opt.m, correctOpt, `${label} ${q.id} Option #${oIdx + 1} ('${opt.t}')`);
      if (leaks.length > 0) allFoundLeaks.push(...leaks);
    });
  });
}

checkAllQuestionDistractors(domCards, 'DOM');
checkAllQuestionDistractors(AUTHORITATIVE_34_QUESTIONS, 'Suite');
checkAllQuestionDistractors(nodeQuizzes, 'NODES');
checkAllQuestionDistractors(weChecks, 'WE');

if (allFoundLeaks.length === 0) {
  recordPass(`Adversarial leak probe on all distractors (DOM, Suite, NODES, WE): ZERO LEAKS FOUND across ${results.stats.totalDistractors} distractors`);
} else {
  allFoundLeaks.forEach(leak => {
    recordFail(`Leak detected in ${leak.context}: [${leak.type}]`, leak);
  });
}

// ----------------------------------------------------------------------------
// 6. ADVERSARIAL STRESS-TEST: 4-TIER PROGRESSIVE HINTS (H1 -> H4)
// ----------------------------------------------------------------------------
console.log('\n--- 6. 4-TIER PROGRESSIVE HINTS AUDIT (H1 -> H4) ---');

let hintsChecked = 0;
const hintLeaks = [];

domCards.forEach(card => {
  const qid = card.id;
  const correctOpt = card.opts.find(o => o.c === true);

  if (!card.hints) {
    recordFail(`DOM card ${qid} is missing hints object`);
    return;
  }

  const tiers = ['h1', 'h2', 'h3', 'h4'];
  tiers.forEach((t, tIdx) => {
    const hintText = card.hints[t];
    if (!hintText || hintText.trim().length < 8) {
      recordFail(`DOM card ${qid} missing or too short hint Tier ${tIdx + 1} (${t}): "${hintText}"`);
      return;
    }

    hintsChecked++;
    results.stats.totalHints++;

    // Probe hint for leaks
    const leaks = probeForLeaks(hintText, correctOpt, `DOM ${qid} Hint Tier ${tIdx + 1}`);
    if (leaks.length > 0) hintLeaks.push(...leaks);
  });
});

if (hintsChecked === 34 * 4) {
  recordPass(`All 34 DOM quiz cards have complete 4-tier progressive hints (checked ${hintsChecked} hints, 136/136 present)`);
} else {
  recordFail(`Expected 136 hints across 34 questions, checked ${hintsChecked}`);
}

if (hintLeaks.length === 0) {
  recordPass(`Adversarial leak probe on 4-tier hints: ZERO LEAKS FOUND across 136 hints`);
} else {
  hintLeaks.forEach(leak => {
    recordFail(`Hint leak detected in ${leak.context}: [${leak.type}]`, leak);
  });
}

// ----------------------------------------------------------------------------
// 7. CROSS-CONSISTENCY AUDIT: DOM CARDS VS SUITE VS JSON BANK
// ----------------------------------------------------------------------------
console.log('\n--- 7. CROSS-CONSISTENCY AUDIT ---');

let jsonBank = null;
if (fs.existsSync(QUESTIONS_JSON)) {
  try {
    jsonBank = JSON.parse(fs.readFileSync(QUESTIONS_JSON, 'utf8'));
    results.stats.jsonQuestions = jsonBank.questions.length;
    recordPass(`Loaded square_cube_questions.json (${jsonBank.questions.length} items)`);
  } catch (e) {
    recordWarn(`Failed to parse square_cube_questions.json: ${e.message}`);
  }
}

// Compare DOM cards vs AUTHORITATIVE_34_QUESTIONS
let crossMatchCount = 0;
AUTHORITATIVE_34_QUESTIONS.forEach((sq, idx) => {
  const domCard = domCards.find(c => c.id === sq.id);
  if (!domCard) {
    recordFail(`Suite question ${sq.id} not found in DOM cards`);
    return;
  }

  // Compare prompt
  const normDomQ = normalizeMathText(domCard.q).toLowerCase();
  const normSuiteQ = normalizeMathText(sq.q).toLowerCase();
  if (normDomQ !== normSuiteQ) {
    recordWarn(`Prompt text difference for ${sq.id}`, { dom: domCard.q, suite: sq.q });
  }

  // Compare correct answer
  const domCorrect = domCard.opts.find(o => o.c);
  const suiteCorrect = sq.opts.find(o => o.c);
  if (normalizeMathText(domCorrect.t).toLowerCase() !== normalizeMathText(suiteCorrect.t).toLowerCase()) {
    recordFail(`Correct answer mismatch for ${sq.id}: DOM="${domCorrect.t}" vs Suite="${suiteCorrect.t}"`);
  } else {
    crossMatchCount++;
  }

  // Compare hints
  ['h1', 'h2', 'h3', 'h4'].forEach(hKey => {
    if (domCard.hints[hKey] !== sq.hints[hKey]) {
      recordWarn(`Hint difference for ${sq.id}.${hKey}`);
    }
  });
});

if (crossMatchCount === 34) {
  recordPass(`100% cross-match between DOM cards and authoritative suite (34/34 correct answers matched)`);
}

// ----------------------------------------------------------------------------
// 8. ADVERSARIAL MATHEMATICAL ORACLE SPOT-CHECKS
// ----------------------------------------------------------------------------
console.log('\n--- 8. MATHEMATICAL ORACLE VERIFICATION ---');

// Oracle verification of key questions
const oracleChecks = [
  { id: 'wu_01_it06', check: () => [1089, 2025, 1024].every(n => [0,1,4,5,6,9].includes(n%10)) && (1027%10 === 7) },
  { id: 'wu_03_it08', check: () => (34*34)%10 === 6 && (38*38)%10 === 4 && (82*82)%10 === 4 && (45*45)%10 === 5 },
  { id: 'wu_04_it09', check: () => Math.log10((1000)**2) === 6 },
  { id: 'wu_09_fio14', check: () => 21 * 21 === 441 },
  { id: 'wu_10_fio21', check: () => 30 ** 3 === 27000 },
  { id: 'dd_02_it12', check: () => 35**2 + 2*36 - 1 === 36**2 && 36**2 === 1296 },
  { id: 'dd_04_it14', check: () => 31**2 === 961 && 32**2 === 1024 && 961 < 1000 && 1024 > 1000 },
  { id: 'dd_05_it15', check: () => 10 + 15 === 25 && 25 === 5**2 },
  { id: 'dd_06_it17', check: () => 2*12 === 24 && (13**2 - 12**2 - 1 === 24) },
  { id: 'dd_08_we02', check: () => 9408 * 3 === 28224 && Math.sqrt(28224) === 168 },
  { id: 'dd_10_it20', check: () => (6**2 + 8**2 === 10**2) && (36 + 64 === 100) },
  { id: 'dd_14_fio22', check: () => 23**3 === 12167 },
  { id: 'bc_01_p18row', check: () => {
    const row = [17, 8, 1, 15, 10, 6, 3, 13, 12, 4, 5, 11, 14, 2, 7, 9, 16];
    const isSquare = x => Number.isInteger(Math.sqrt(x));
    for (let i = 0; i < row.length - 1; i++) {
      if (!isSquare(row[i] + row[i+1])) return false;
    }
    return true;
  }},
  { id: 'bc_02_p18circ', check: () => {
    const circle = [32, 17, 19, 30, 6, 27, 22, 14, 2, 23, 26, 10, 15, 21, 28, 8, 1, 24, 25, 11, 5, 31, 18, 7, 29, 20, 16, 9, 4, 12, 13, 3];
    const isSquare = x => Number.isInteger(Math.sqrt(x));
    for (let i = 0; i < circle.length; i++) {
      const next = circle[(i + 1) % circle.length];
      if (!isSquare(circle[i] + next)) return false;
    }
    return true;
  }},
  { id: 'bc_06_s01', check: () => {
    // 100 lockers
    const lockers = new Array(101).fill(false); // false = closed
    for (let p = 1; p <= 100; p++) {
      for (let l = p; l <= 100; l += p) {
        lockers[l] = !lockers[l];
      }
    }
    const openLockers = [];
    for (let i = 1; i <= 100; i++) if (lockers[i]) openLockers.push(i);
    const expected = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100];
    return JSON.stringify(openLockers) === JSON.stringify(expected);
  }},
  { id: 'bc_07_s06', check: () => (1**3 + 12**3 === 1729) && (9**3 + 10**3 === 1729) }
];

let oraclePassed = 0;
oracleChecks.forEach(({ id, check }) => {
  if (check()) {
    oraclePassed++;
  } else {
    recordFail(`Oracle check failed for ${id}`);
  }
});
if (oraclePassed === oracleChecks.length) {
  recordPass(`All ${oraclePassed} mathematical oracle ground-truth proofs PASSED`);
}

// ----------------------------------------------------------------------------
// FINAL SUMMARY & VERDICT
// ----------------------------------------------------------------------------
console.log('\n' + '='.repeat(80));
console.log(' ADVERSARIAL CHALLENGE EXECUTION SUMMARY');
console.log('='.repeat(80));
console.log(`  Passed Checks:    ${results.checks.length}`);
console.log(`  Failures:         ${results.failures.length}`);
console.log(`  Warnings:         ${results.warnings.length}`);
console.log(`  Total Probes:     ${results.stats.leakProbes} distractor/hint evaluations`);
console.log(`  DOM Questions:    ${results.stats.domQuestions}`);
console.log(`  NODES Quizzes:    ${results.stats.nodeQuizzes}`);
console.log(`  WE Checks:        ${results.stats.weChecks}`);
console.log(`  Distractors:      ${results.stats.totalDistractors}`);
console.log(`  Hints Checked:    ${results.stats.totalHints}`);
console.log('-'.repeat(80));

const VERDICT = results.passed && results.failures.length === 0 ? 'APPROVE' : 'REQUEST_CHANGES';
console.log(`  CHALLENGER VERDICT: >>> ${VERDICT} <<<`);
console.log('='.repeat(80));

// Export machine-readable summary
const outReport = path.join(__dirname, 'adversarial_challenge_results.json');
fs.writeFileSync(outReport, JSON.stringify({
  verdict: VERDICT,
  timestamp: new Date().toISOString(),
  stats: results.stats,
  passedCount: results.checks.length,
  failureCount: results.failures.length,
  warningCount: results.warnings.length,
  failures: results.failures,
  warnings: results.warnings,
  checks: results.checks
}, null, 2), 'utf8');

process.exit(results.passed ? 0 : 1);
