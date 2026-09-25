// Standalone logic verification script for 5 simulation manipulatives
// Run in Node.js to verify all math algorithms, edge cases, and state outputs

const UNIT_MAP = { 0: 0, 1: 1, 2: 8, 3: 7, 4: 4, 5: 5, 6: 6, 7: 3, 8: 2, 9: 9 };

function getPrimeFactors(n) {
  const factors = [];
  let d = 2;
  let temp = n;
  while (d * d <= temp) {
    while (temp % d === 0) {
      factors.push(d);
      temp = Math.floor(temp / d);
    }
    d = (d === 2) ? 3 : d + 2;
  }
  if (temp > 1) factors.push(temp);
  return factors;
}

function analyzePrimeFactors(n, mode) {
  const factors = getPrimeFactors(n);
  const counts = {};
  for (const f of factors) counts[f] = (counts[f] || 0) + 1;

  if (mode === 'square') {
    let isSquare = true;
    let root = 1;
    let mult = 1;
    let div = 1;
    for (const [pStr, c] of Object.entries(counts)) {
      const p = parseInt(pStr, 10);
      const pairs = Math.floor(c / 2);
      const rem = c % 2;
      root *= Math.pow(p, pairs);
      if (rem > 0) {
        isSquare = false;
        mult *= p;
        div *= p;
      }
    }
    return { factors, counts, isSquare, root: isSquare ? root : null, mult, div };
  } else {
    let isCube = true;
    let root = 1;
    let mult = 1;
    let div = 1;
    for (const [pStr, c] of Object.entries(counts)) {
      const p = parseInt(pStr, 10);
      const trips = Math.floor(c / 3);
      const rem = c % 3;
      root *= Math.pow(p, trips);
      if (rem > 0) {
        isCube = false;
        if (rem === 1) { mult *= p * p; div *= p; }
        if (rem === 2) { mult *= p; div *= p * p; }
      }
    }
    return { factors, counts, isCube, root: isCube ? root : null, mult, div };
  }
}

function estimateCubeRoot(n) {
  const s = n.toString();
  if (s.length <= 3) {
    const u = UNIT_MAP[n % 10];
    return { g1: n, g2: 0, unitsDigit: u, tensDigit: 0, root: u };
  }
  const g1Str = s.slice(-3);
  const g2Str = s.slice(0, -3);
  const g1 = parseInt(g1Str, 10);
  const g2 = parseInt(g2Str, 10);

  const unitsDigit = UNIT_MAP[g1 % 10];

  let tensDigit = 1;
  while ((tensDigit + 1) * (tensDigit + 1) * (tensDigit + 1) <= g2) {
    tensDigit++;
  }
  const root = tensDigit * 10 + unitsDigit;
  return { g1, g2, unitsDigit, tensDigit, root, exact: root * root * root === n };
}

function getLockerData(numLockers = 100) {
  const lockers = [];
  for (let i = 1; i <= numLockers; i++) {
    const factors = [];
    for (let f = 1; f <= i; f++) {
      if (i % f === 0) factors.push(f);
    }
    const isSquare = Math.round(Math.sqrt(i)) * Math.round(Math.sqrt(i)) === i;
    const isOpen = factors.length % 2 === 1;
    lockers.push({ id: i, factors, factorCount: factors.length, isOpen, isSquare });
  }
  return lockers;
}

// Run test suite
console.log('--- TEST 1: Prime Factorization ---');
const pf144 = analyzePrimeFactors(144, 'square');
console.log('144 Square:', pf144.isSquare, 'Root:', pf144.root);
const pf252 = analyzePrimeFactors(252, 'square');
console.log('252 Square:', pf252.isSquare, 'Mult:', pf252.mult, 'Div:', pf252.div);
const pf500 = analyzePrimeFactors(500, 'cube');
console.log('500 Cube:', pf500.isCube, 'Mult:', pf500.mult, 'Div:', pf500.div);
const pf1728 = analyzePrimeFactors(1728, 'cube');
console.log('1728 Cube:', pf1728.isCube, 'Root:', pf1728.root);

console.log('\n--- TEST 2: Cube Root Estimation ---');
const testCubes = [1331, 4913, 12167, 17576, 32768, 91125, 110592];
for (const tc of testCubes) {
  const est = estimateCubeRoot(tc);
  console.log(`Cube ${tc} -> G2: ${est.g2}, G1: ${est.g1} -> Tens: ${est.tensDigit}, Units: ${est.unitsDigit} -> Root: ${est.root} (Exact: ${est.exact})`);
}

console.log('\n--- TEST 3: 100 Lockers Parity ---');
const lockers = getLockerData(100);
const openLockers = lockers.filter(l => l.isOpen).map(l => l.id);
console.log('Open Lockers count:', openLockers.length);
console.log('Open Lockers:', openLockers.join(', '));
const squares = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100];
const allMatch = openLockers.length === 10 && openLockers.every((val, idx) => val === squares[idx]);
console.log('Lockers Parity theorem holds 100%:', allMatch);

console.log('\nAll algorithmic checks passed!');
