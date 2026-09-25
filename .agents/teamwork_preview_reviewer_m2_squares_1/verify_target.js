const fs = require('fs');
const path = require('path');

const targetPath = path.resolve('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html');

console.log(`Analyzing: ${targetPath}`);

if (!fs.existsSync(targetPath)) {
  console.error(`ERROR: Target file does not exist!`);
  process.exit(1);
}

const stat = fs.statSync(targetPath);
const sizeBytes = stat.size;
const sizeMB = (sizeBytes / (1024 * 1024)).toFixed(3);
console.log(`File Size: ${sizeBytes} bytes (${sizeMB} MB)`);

const content = fs.readFileSync(targetPath, 'utf8');

// 1. External CDN dependencies
const httpSrcMatches = [...content.matchAll(/src=["'](https?:\/\/[^"']+)["']/gi)];
const httpHrefMatches = [...content.matchAll(/href=["'](https?:\/\/[^"']+)["']/gi)];
const httpUrlMatches = [...content.matchAll(/url\(\s*["']?(https?:\/\/[^"')]+)["']?\s*\)/gi)];
const scriptSrcMatches = [...content.matchAll(/<script[^>]+src=[^>]*>/gi)];
const linkStylesheetMatches = [...content.matchAll(/<link[^>]+rel=["']?stylesheet["']?[^>]*>/gi)];

console.log('\n--- EXTERNAL CDN & SELF-CONTAINMENT CHECK ---');
console.log(`http(s) src matches: ${httpSrcMatches.length}`);
if (httpSrcMatches.length > 0) console.log(httpSrcMatches.map(m => m[1]));
console.log(`http(s) href matches: ${httpHrefMatches.length}`);
if (httpHrefMatches.length > 0) console.log(httpHrefMatches.map(m => m[1]));
console.log(`http(s) url() matches: ${httpUrlMatches.length}`);
if (httpUrlMatches.length > 0) console.log(httpUrlMatches.map(m => m[1]));
console.log(`<script src=...>: ${scriptSrcMatches.length}`);
console.log(`<link rel="stylesheet"...>: ${linkStylesheetMatches.length}`);

// 2. Sections and Quiz Cards
console.log('\n--- TEXTBOOK QUESTIONS & SECTIONS CHECK ---');
const warmupIdx = content.indexOf('id="section-warmup"');
const deepDiveIdx = content.indexOf('id="section-deep_dive"');
const bossIdx = content.indexOf('id="section-boss"');

console.log(`section-warmup index: ${warmupIdx}`);
console.log(`section-deep_dive index: ${deepDiveIdx}`);
console.log(`section-boss index: ${bossIdx}`);

// Extract sections
let warmupContent = '';
let deepDiveContent = '';
let bossContent = '';

if (warmupIdx !== -1 && deepDiveIdx !== -1 && bossIdx !== -1) {
  warmupContent = content.substring(warmupIdx, deepDiveIdx);
  deepDiveContent = content.substring(deepDiveIdx, bossIdx);
  // boss goes until next major section or end of main
  const nextSecIdx = content.indexOf('</main>', bossIdx);
  bossContent = content.substring(bossIdx, nextSecIdx !== -1 ? nextSecIdx : content.length);
}

function countQuizCards(html) {
  const matches = [...html.matchAll(/class=["'][^"']*quiz-card[^"']*["']/gi)];
  return matches.length;
}

const totalCards = countQuizCards(content);
const warmupCards = countQuizCards(warmupContent);
const deepDiveCards = countQuizCards(deepDiveContent);
const bossCards = countQuizCards(bossContent);

console.log(`Total .quiz-card in document: ${totalCards}`);
console.log(`Warm-up .quiz-card: ${warmupCards} (Expected: 12)`);
console.log(`Deep Dive .quiz-card: ${deepDiveCards} (Expected: 14)`);
console.log(`Boss .quiz-card: ${bossCards} (Expected: 8)`);

// Check card ids
const cardIdMatches = [...content.matchAll(/id=["'](q-[^"']+)["']/gi)].map(m => m[1]);
console.log(`Total q-* IDs found: ${cardIdMatches.length}`);
console.log('Sample IDs:', cardIdMatches.slice(0, 5), '...', cardIdMatches.slice(-3));

// 3. Golden Flow and Worked Examples
console.log('\n--- GOLDEN FLOW & WORKED EXAMPLES CHECK ---');
const hasNodes = content.includes('const NODES =') || content.includes('var NODES =') || content.includes('let NODES =');
console.log(`NODES array present: ${hasNodes}`);

const hasWeCheckRendered = content.includes('_weCheckRendered');
console.log(`_weCheckRendered guard present: ${hasWeCheckRendered}`);

// Check occurrences of _weCheckRendered
const weCheckMatches = [...content.matchAll(/_weCheckRendered/g)];
console.log(`_weCheckRendered occurrences: ${weCheckMatches.length}`);

// 4. <aasha-sim> and Simulation Engines
console.log('\n--- SIMULATION ENGINES CHECK ---');
const hasAashaSim = content.includes('customElements.define(\'aasha-sim\'') || content.includes('customElements.define("aasha-sim"');
console.log(`<aasha-sim> custom element registered: ${hasAashaSim}`);

const simEngines = [
  'drawSquareGridSim',
  'drawIsoCubeSim',
  'drawPrimeFactorSim',
  'drawLockerRiddleSim',
  'drawCubeEstimatorSim'
];

simEngines.forEach(eng => {
  const hasEng = content.includes(eng);
  console.log(`Simulation function ${eng}: ${hasEng}`);
});

// 5. Math Insulation & LLE Substrate
console.log('\n--- MATH INSULATION & LLE SUBSTRATE CHECK ---');
const hasMathIsolationHeader = content.includes('/* MathIsolation: true */');
const hasMathVar = content.includes('math-var');
const hasAashaMathPlaceholder = content.includes('__AASHA_MATH_');
const hasWindowWM = content.includes('window.WM');
const hasWordDialog = content.includes('id="wordDialog"');

console.log(`/* MathIsolation: true */: ${hasMathIsolationHeader}`);
console.log(`math-var references: ${hasMathVar}`);
console.log(`__AASHA_MATH_ references: ${hasAashaMathPlaceholder}`);
console.log(`window.WM dictionary: ${hasWindowWM}`);
console.log(`#wordDialog modal: ${hasWordDialog}`);

// 6. Mobile Responsiveness CSS
console.log('\n--- RESPONSIVENESS CSS CHECK ---');
console.log(`.screen { min-height: 0; }: ${content.includes('.screen') && content.includes('min-height: 0')}`);
console.log(`touch-action: pan-x: ${content.includes('touch-action: pan-x')}`);
console.log(`44px touch targets: ${content.includes('44px')}`);
console.log(`backdrop-filter: blur: ${content.includes('backdrop-filter: blur')}`);
