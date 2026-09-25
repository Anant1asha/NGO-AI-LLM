const LEAK_PREDICATES = [
  'is', 'was', '=', 'giving', 'gives', 'give', 'becomes', 'became',
  ', not \\+?', 'not', 'equals', 'equal to', 'equals to', 'result is', 'results in',
  'yielding', 'yields', 'produces', 'produced', 'produces a value of',
  'leaving', 'leaves', 'leads to', 'should be', 'must be', 'to get',
  'target is', 'target value is', 'correct value is', 'correct answer is',
  'answer is', 'answer was', 'answer:', 'instead of'
];

function escapeRegex(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Support adverbs between words of multi-word predicates, plus up to 4 qualifier words before target number
const leakRegexForNum = (n) => new RegExp(
  '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + ')\\b)\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b' + escapeRegex(n) + '\\b',
  'i'
);

const boolLeakRegex = (boolVal) => new RegExp(
  '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + '|statement\\s+is|claim\\s+is|option\\s+is|actually)\\b)\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b' + escapeRegex(boolVal) + '\\b',
  'i'
);

const vectors = [
  { text: 'giving a final total of 25.', target: '25', type: 'num' },
  { text: 'The result becomes approximately 25', target: '25', type: 'num' },
  { text: 'The calculated output became exactly 25', target: '25', type: 'num' },
  { text: 'Leaving a remainder of 25', target: '25', type: 'num' },
  { text: 'This leads directly to 25', target: '25', type: 'num' },
  { text: 'The statement is incorrect, the correct answer is False.', target: 'false', type: 'bool' }
];

let allPassed = true;
vectors.forEach(v => {
  const matched = v.type === 'num' ? leakRegexForNum(v.target).test(v.text) : boolLeakRegex(v.target).test(v.text);
  console.log(v.text + ' -> matched: ' + matched);
  if (!matched) allPassed = false;
});

console.log('All matched: ' + allPassed);
