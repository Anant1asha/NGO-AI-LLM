const fs = require('fs');

const jsonPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/ad_all_questions.json';
const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

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

// Let's parse operations automatically from the question text!
const verified = [];
const failed = [];

data.questions.forEach((q, idx) => {
  const text = q.q;
  let calc = null;

  // Pattern: "Add the rational numbers: X and Y"
  let m = text.match(/Add the rational numbers:\s*(-?\d+\/?\d*)\s+and\s+(-?\d+\/?\d*)/i);
  if (m) {
    calc = parseF(m[1]).add(parseF(m[2])).toString();
  }

  // Pattern: "Subtract (X) from (Y)" or "Subtract X from Y"
  if (!calc) {
    m = text.match(/Subtract\s+\(?(-?\d+\/?\d*)\)?\s+from\s+\(?(-?\d+\/?\d*)\)?/i);
    if (m) {
      // Y - X
      calc = parseF(m[2]).sub(parseF(m[1])).toString();
    }
  }

  // Pattern: "Multiply: (X) by (Y)" or "Multiply: X by Y"
  if (!calc) {
    m = text.match(/Multiply:\s+\(?(-?\d+\/?\d*)\)?\s+by\s+\(?(-?\d+\/?\d*)\)?/i);
    if (m) {
      calc = parseF(m[1]).mul(parseF(m[2])).toString();
    }
  }

  // Pattern: "Divide: (X) by (Y)"
  if (!calc) {
    m = text.match(/Divide:\s+\(?(-?\d+\/?\d*)\)?\s+by\s+\(?(-?\d+\/?\d*)\)?/i);
    if (m) {
      calc = parseF(m[1]).div(parseF(m[2])).toString();
    }
  }

  // Pattern: "Find the product and verify the Commutative Property of Multiplication: (X) * (Y)"
  if (!calc) {
    m = text.match(/Commutative Property of Multiplication:\s+\(?(-?\d+\/?\d*)\)?\s*\*\s*\(?(-?\d+\/?\d*)\)?/i);
    if (m) {
      calc = parseF(m[1]).mul(parseF(m[2])).toString();
    }
  }

  // Pattern: "Find the product and verify the Associative Property of Multiplication: (X) * [(-7/3) * (6/-11)]"
  if (!calc) {
    m = text.match(/Associative Property of Multiplication:\s+\(?(-?\d+\/?\d*)\)?\s*\*\s*\[\(?(-?\d+\/?\d*)\)?\s*\*\s*\(?(-?\d+\/?\d*)\)?\]/i);
    if (m) {
      calc = parseF(m[1]).mul(parseF(m[2])).mul(parseF(m[3])).toString();
    }
  }

  // Pattern: "Simplify and verify Distributive Property of Multiplication over Addition: X * [(Y) + (Z)]"
  if (!calc) {
    m = text.match(/Distributive Property.*?:\s+\(?(-?\d+\/?\d*)\)?\s*\*\s*\[\(?(-?\d+\/?\d*)\)?\s*\+\s*\(?(-?\d+\/?\d*)\)?\]/i);
    if (m) {
      calc = parseF(m[1]).mul(parseF(m[2]).add(parseF(m[3]))).toString();
    }
  }

  if (calc !== null) {
    if (calc === q.ans) {
      verified.push({ id: q.id, calc, ans: q.ans });
    } else {
      failed.push({ id: q.id, prompt: q.q, calc, ans: q.ans });
    }
  }
});

console.log(`Automatically parsed and verified: ${verified.length} questions.`);
console.log(`Failed math checks: ${failed.length}`);
if (failed.length > 0) {
  console.log('Failed:', JSON.stringify(failed, null, 2));
}
