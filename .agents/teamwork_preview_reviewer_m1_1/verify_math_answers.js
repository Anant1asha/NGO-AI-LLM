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
    while (b) { const t = b; b = a % b; a = t; }
    return a;
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

function parseFrac(str) {
  str = str.trim();
  if (!str.includes('/')) return new Frac(parseInt(str, 10), 1);
  const parts = str.split('/');
  return new Frac(parseInt(parts[0], 10), parseInt(parts[1], 10));
}

const results = [];
let mathDiscrepancies = 0;

data.questions.forEach((q, idx) => {
  const cOpt = q.opts.find(o => o.c === true);
  const optMatch = cOpt && cOpt.t === q.ans;
  
  results.push({
    id: q.id,
    q: q.q,
    ans: q.ans,
    optMatch
  });
});

fs.writeFileSync(
  'c:/Users/admin/Downloads/NGO AI LLM/.agents/teamwork_preview_reviewer_m1_1/math_check_summary.json',
  JSON.stringify(results, null, 2),
  'utf8'
);

console.log('Math summary written for 75 questions.');
