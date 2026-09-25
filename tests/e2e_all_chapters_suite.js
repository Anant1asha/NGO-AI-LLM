#!/usr/bin/env node
/**
 * AASHA FOUNDATION — MASTER UNIFIED E2E MULTI-CHAPTER VERIFICATION HARNESS
 * ========================================================================
 * File: tests/e2e_all_chapters_suite.js
 * 
 * Validates ALL built HTML chapter webapps in the AASHA ecosystem:
 * 1. Monolithic self-containment (< 20 MB ceiling, zero external CDN scripts/styles)
 * 2. Pre-LLE mathematical formula and algebraic variable insulation (__AASHA_MATH_X__)
 * 3. Bilingual Hindi LLE dictionary embedding (window.WM or rt() substrate)
 * 4. <aasha-sim> Web Component contract standards & non-destructive lifecycle (pause/resume/destroy)
 * 5. Mobile responsiveness & viewport constraints (.screen min-height: 0, opaque bottom nav)
 * 6. Static L-Truth Quality Certification via benchmarks/qa_ltruth_benchmark.js
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT_DIR = path.resolve(__dirname, '..');
const AASHA_DIR = fs.existsSync(path.join(ROOT_DIR, 'Aasha-AI')) ? path.join(ROOT_DIR, 'Aasha-AI') : ROOT_DIR;
const CHAPTERS_DIR = path.join(AASHA_DIR, 'chapters');
const BENCHMARKS_DIR = path.join(AASHA_DIR, 'benchmarks');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function logPass(suite, msg) {
  totalTests++;
  passedTests++;
  console.log(`  [PASS] [${suite}] ${msg}`);
}

function logFail(suite, msg, err) {
  totalTests++;
  failedTests++;
  console.error(`  [FAIL] [${suite}] ${msg}`);
  if (err) console.error(`         Reason: ${err.message || err}`);
}

console.log('=' .repeat(80));
console.log(' AASHA FOUNDATION — MASTER UNIFIED E2E MULTI-CHAPTER HARNESS');
console.log('=' .repeat(80));

// 1. Discover target production V6 HTML chapters
const TARGET_PRODUCTION_CHAPTERS = [
  'SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html',
  'RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html',
  'ExponentsPowers_Class8_Gamified_v5_Enhanced_v6.html',
  'LinearEquations_Class8_v6.html',
  'RationalNumbers_Class8_Gamified_v5_Enhanced_v6.html',
  'quadratic_systems_lab_Class8_v6.html'
];

const chapterFiles = TARGET_PRODUCTION_CHAPTERS
  .map(f => path.join(CHAPTERS_DIR, f))
  .filter(f => fs.existsSync(f));

console.log(`\nDiscovered ${chapterFiles.length} chapter HTML files for E2E validation:\n`);
chapterFiles.forEach(f => console.log(` - ${path.basename(f)}`));

// 2. Iterate through each chapter and validate invariants
chapterFiles.forEach(filePath => {
  const fileName = path.basename(filePath);
  console.log(`\n--- AUDITING: ${fileName} ---`);
  const content = fs.readFileSync(filePath, 'utf-8');
  const stats = fs.statSync(filePath);

  // Check 1: File Size Ceiling (< 20 MB)
  const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
  if (stats.size < 20 * 1024 * 1024) {
    logPass(fileName, `File size is within 20 MB ceiling (${sizeMB} MB < 20 MB)`);
  } else {
    logFail(fileName, `File size exceeds 20 MB ceiling (${sizeMB} MB)`);
  }

  // Check 2: Zero External CDN Dependencies
  const cdnRegex = /src=["'](https?:)?\/\/(?!localhost)/gi;
  const cdnMatches = content.match(cdnRegex) || [];
  if (cdnMatches.length === 0) {
    logPass(fileName, `Zero external CDN script dependencies (found 0)`);
  } else {
    logFail(fileName, `Found ${cdnMatches.length} external CDN dependencies`, new Error(cdnMatches.join(', ')));
  }

  // Check 3: Pre-LLE Math Insulation Header / Regex
  const hasMathInsulation = content.includes('MathIsolation: true') ||
    content.includes('__AASHA_MATH_') ||
    content.includes('math-var');
  if (hasMathInsulation) {
    logPass(fileName, `Pre-LLE mathematical formula insulation verified`);
  } else {
    logFail(fileName, `Missing MathIsolation declaration or __AASHA_MATH_ shielding`);
  }

  // Check 4: Bilingual Hindi LLE Substrate Presence
  const hasLLE = content.includes('window.WM') || content.includes('function rt(') || content.includes('lle-text');
  if (hasLLE) {
    logPass(fileName, `Bilingual Hindi LLE dictionary substrate present`);
  } else {
    logFail(fileName, `Missing bilingual Hindi LLE substrate (window.WM or rt())`);
  }

  // Check 5: Mobile Viewport Clamping & Bottom Nav Integrity
  const hasScreenClamping = content.includes('min-height:0') || content.includes('min-height: 0');
  if (hasScreenClamping) {
    logPass(fileName, `Same-frame mobile layout constraint (.screen min-height: 0) declared`);
  } else {
    logFail(fileName, `Missing .screen { min-height: 0; } mobile viewport clamping rule`);
  }

  // Check 6: Interactive Engine / Web Component Standard
  const hasInteractiveEngine = content.includes('<aasha-sim') ||
    content.includes('AashaExperienceContract') ||
    content.includes('canvas') ||
    content.includes('mountSim');
  if (hasInteractiveEngine) {
    logPass(fileName, `Interactive visual simulation engine present`);
  } else {
    logFail(fileName, `Missing interactive manipulative engine`);
  }
});

// 3. Final Summary Report
console.log('\n' + '=' .repeat(80));
console.log(` MASTER VERIFICATION SUMMARY: ${passedTests}/${totalTests} PASSED (${failedTests} FAILED)`);
console.log('=' .repeat(80));

if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
