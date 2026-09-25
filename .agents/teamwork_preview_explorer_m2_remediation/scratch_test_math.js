const fs = require('fs');
const path = require('path');

const chapterPath = path.resolve(__dirname, '../../Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html');
const content = fs.readFileSync(chapterPath, 'utf8');

// Extract current insulateMathContent and rt
const evalContext = {};
const scriptMatch = content.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  console.error("No script tag found!");
  process.exit(1);
}

// We can extract CONN, WM, insulateMathContent, rt by running in vm
const vm = require('vm');
const sandbox = {
  window: {},
  document: {
    addEventListener: () => {},
    getElementById: () => null
  },
  CustomEvent: class {},
  HTMLElement: class {},
  customElements: { get: () => undefined, define: () => {} }
};
vm.createContext(sandbox);

// Run the script in sandbox to get current functions
vm.runInContext(scriptMatch[1], sandbox);

const currentInsulate = sandbox.insulateMathContent;
const currentRt = sandbox.rt;
const WM = sandbox.WM;
const CONN = sandbox.CONN;

console.log("Current WM['a']:", WM['a']);
console.log("Current WM['d']:", WM['d']);

const testInputs = [
  "Commutative property: a * b = b * a",
  "For any rational number a, a + 0 = a",
  "Compute a/b + c/d",
  "Let $x = p/q$ where $q \\neq 0$",
  "The Commutative Property of Addition states that a + b equals b + a.",
  "Under commutative addition, a + b equals b + a exactly.",
  "Commutative property of multiplication states: a * b equals b * a.",
  "Recognize the distributive pattern: a * (b + c) = (a * b) + (a * c).",
  "The Associative Property of Multiplication states: a * (b * c) = (a * b) * c.",
  "For any rational number a/b, dividing by its opposite -(a/b) results in -1.",
  "When two fractions in the form a/b and c/d are multiplied, the product (ac)/(bd) is also a ratio of integers.",
  "The Associative Property states: (a + b) + c = a + (b + c).",
  "The Associative Law regroups terms: a + (b + c) = (a + b) + c.",
  "The rule (a + b) + c = a + (b + c) is called the Associative Property.",
  "The factor outside the bracket multiplies each term inside: a * (b + c) = ab + ac.",
  "The Distributive property connects multiplication over addition: a(b + c) = ab + ac.",
  "If a = 8/9 and b = -3/8, verify that a + b = b + a. What is the verified value of both sides?",
  "The reciprocal or multiplicative inverse of a rational number a/b is b/a, because (a/b) × (b/a) = 1.",
  "Subtraction (because a - b is generally not equal to b - a)",
  "Associative: (a+b)+c",
  "Commutative: a+b = b+a",
  "A rational number is a number that can be written as p/q where p and q are integers."
];

console.log("\n--- TESTING CURRENT IMPLEMENTATION ---");
for (const input of testInputs) {
  const output = currentRt(input);
  // Check if variable 'a' or 'd' is wrapped as word with Hindi translation
  const badA = output.includes('data-w="a"');
  const badD = output.includes('data-w="d"');
  const hasAashaMath = output.includes('__AASHA_MATH_');
  console.log(`\nInput: ${input}`);
  if (badA) console.log(`  ❌ FAIL: 'a' wrapped as .word!`);
  if (badD) console.log(`  ❌ FAIL: 'd' wrapped as .word!`);
  if (hasAashaMath) console.log(`  ❌ FAIL: residual __AASHA_MATH_ token!`);
  if (!badA && !badD && !hasAashaMath) console.log(`  ✔ PASS`);
  console.log(`  Output snippet: ${output.replace(/<div class="lle-text">([\s\S]*)<\/div>/, '$1')}`);
}
