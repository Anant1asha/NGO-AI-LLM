const fs = require('fs');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

// Helper for rational arithmetic
class Frac {
  constructor(n, d = 1) {
    if (d === 0) throw new Error('Division by zero');
    if (d < 0) { n = -n; d = -d; }
    const g = Frac.gcd(Math.abs(n), Math.abs(d));
    this.n = Math.round(n / g);
    this.d = Math.round(d / g);
  }
  static gcd(a, b) {
    let x = Math.abs(a), y = Math.abs(b);
    while (y) { const t = y; y = x % y; x = t; }
    return x;
  }
  add(f) { return new Frac(this.n * f.d + f.n * this.d, this.d * f.d); }
  sub(f) { return new Frac(this.n * f.d - f.n * this.d, this.d * f.d); }
  mul(f) { return new Frac(this.n * f.n, this.d * f.d); }
  div(f) { return new Frac(this.n * f.d, this.d * f.n); }
  toString() {
    if (this.d === 1) return String(this.n);
    return `${this.n}/${this.d}`;
  }
}

function parseF(s) {
  s = s.trim();
  if (s.startsWith('(') && s.endsWith(')')) s = s.slice(1, -1).trim();
  if (s.includes('/')) {
    const p = s.split('/');
    return new Frac(parseInt(p[0], 10), parseInt(p[1], 10));
  }
  return new Frac(parseInt(s, 10), 1);
}

// Let's test specific questions
const testCases = [
  // 1A Q1 Add:
  { id: 'ad_1a_q1_a', expr: () => parseF('-5/7').add(parseF('3/7')), expected: '-2/7' },
  { id: 'ad_1a_q1_b', expr: () => parseF('-15/4').add(parseF('7/4')), expected: '-2' },
  { id: 'ad_1a_q1_c', expr: () => parseF('-8/11').add(parseF('-4/11')), expected: '-12/11' },
  { id: 'ad_1a_q1_d', expr: () => parseF('6/13').add(parseF('-9/13')), expected: '-3/13' },
  { id: 'ad_1a_q1_e', expr: () => parseF('-3/4').add(parseF('5/6')), expected: '1/12' },
  { id: 'ad_1a_q1_f', expr: () => parseF('-27/7').add(parseF('-3/5')), expected: '-149/35' },
  { id: 'ad_1a_q1_g', expr: () => parseF('3/8').add(parseF('-5/12')), expected: '-1/24' },
  { id: 'ad_1a_q1_h', expr: () => parseF('-9/10').add(parseF('22/15')), expected: '17/30' },

  // 1A Q2 Subtract:
  // "Subtract (-3/5) from (9/5)": (9/5) - (-3/5) = 12/5
  { id: 'ad_1a_q2_a', expr: () => parseF('9/5').sub(parseF('-3/5')), expected: '12/5' },
  // "Subtract (-7/9) from (4/9)": (4/9) - (-7/9) = 11/9
  { id: 'ad_1a_q2_b', expr: () => parseF('4/9').sub(parseF('-7/9')), expected: '11/9' },
  // "Subtract (-8/11) from (-4/11)": (-4/11) - (-8/11) = 4/11
  { id: 'ad_1a_q2_c', expr: () => parseF('-4/11').sub(parseF('-8/11')), expected: '4/11' },
  // "Subtract (11/13) from (-5/13)": (-5/13) - (11/13) = -16/13
  { id: 'ad_1a_q2_d', expr: () => parseF('-5/13').sub(parseF('11/13')), expected: '-16/13' },
  // "Subtract (-13/5) from (-91/5)": (-91/5) - (-13/5) = -78/5
  { id: 'ad_1a_q2_e', expr: () => parseF('-91/5').sub(parseF('-13/5')), expected: '-78/5' },
  // "Subtract (-3/7) from (-1/9)": (-1/9) - (-3/7) = (-7 + 27)/63 = 20/63
  { id: 'ad_1a_q2_f', expr: () => parseF('-1/9').sub(parseF('-3/7')), expected: '20/63' },
  // "Subtract (-4/11) from (2/7)": (2/7) - (-4/11) = (22 + 28)/77 = 50/77
  { id: 'ad_1a_q2_g', expr: () => parseF('2/7').sub(parseF('-4/11')), expected: '50/77' },
  // "Subtract (-5/14) from (-2/7)": (-2/7) - (-5/14) = (-4 + 5)/14 = 1/14
  { id: 'ad_1a_q2_h', expr: () => parseF('-2/7').sub(parseF('-5/14')), expected: '1/14' },

  // 1A Q3 Multiply:
  { id: 'ad_1a_q3_a', expr: () => parseF('3/5').mul(parseF('-7/8')), expected: '-21/40' },
  { id: 'ad_1a_q3_b', expr: () => parseF('-9/2').mul(parseF('5/4')), expected: '-45/8' },
  { id: 'ad_1a_q3_c', expr: () => parseF('-6/11').mul(parseF('-5/3')), expected: '10/11' },
  { id: 'ad_1a_q3_d', expr: () => parseF('-2/3').mul(parseF('6/7')), expected: '-4/7' },
  { id: 'ad_1a_q3_e', expr: () => parseF('-9/25').mul(parseF('-35/27')), expected: '7/15' },
  { id: 'ad_1a_q3_f', expr: () => parseF('-8/15').mul(parseF('-25/16')), expected: '5/6' },

  // 1A Q4 Divide:
  { id: 'ad_1a_q4_a', expr: () => parseF('1/2').div(parseF('-1/3')), expected: '-3/2' },
  { id: 'ad_1a_q4_b', expr: () => parseF('-3/5').div(parseF('2')), expected: '-3/10' },
  { id: 'ad_1a_q4_c', expr: () => parseF('-4/5').div(parseF('-3')), expected: '4/15' },
  { id: 'ad_1a_q4_d', expr: () => parseF('-1/8').div(parseF('3/4')), expected: '-1/6' },
  { id: 'ad_1a_q4_e', expr: () => parseF('-2/13').div(parseF('1/7')), expected: '-14/13' },
  { id: 'ad_1a_q4_f', expr: () => parseF('-7/12').div(parseF('-2/13')), expected: '91/24' },

  // 1A Q5 Simplify:
  // Q5a: [3/2 * -7/4 * 8/9] - [-15/2 * 3/7 * 8/14]
  { id: 'ad_1a_q5_a', expr: () => {
    const b1 = parseF('3/2').mul(parseF('-7/4')).mul(parseF('8/9'));
    const b2 = parseF('-15/2').mul(parseF('3/7')).mul(parseF('8/14'));
    return b1.sub(b2);
  }, expected: '-73/147' },
  // Q5b: [1/2 * 1/4] + [1/2 * 6]
  { id: 'ad_1a_q5_b', expr: () => {
    const b1 = parseF('1/2').mul(parseF('1/4'));
    const b2 = parseF('1/2').mul(parseF('6'));
    return b1.add(b2);
  }, expected: '25/8' }
];

console.log('--- Testing Arithmetic Cases ---');
testCases.forEach(tc => {
  const q = data.questions.find(x => x.id === tc.id);
  if (!q) {
    console.log(`Missing question ${tc.id}`);
    return;
  }
  const calc = tc.expr().toString();
  if (calc !== tc.expected) {
    console.log(`Discrepancy in test calculation for ${tc.id}: calc=${calc}, expected=${tc.expected}`);
  }
  if (q.ans !== tc.expected) {
    console.log(`ERROR: Question ${tc.id} stored ans "${q.ans}" != calculated "${tc.expected}"!`);
  }
});
console.log('Arithmetic verification complete.');
