import fs from 'fs';
import path from 'path';
import chalk from 'chalk';
import { PedagogicalAuditor } from './pedagogical_auditor';

function runAutomatedTests() {
  console.log('\n=== Running AASHA Pedagogical Auditor Automated Test Suite ===\n');

  const tmpDir = path.join(__dirname, '..', '.tmp_test_audit');
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });

  const validHtml = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Fractions Discovery — AASHA</title>
<style>.math{font-style:italic}</style>
</head>
<body>
<div class="app">
  <h1>Notice how pizza slices divide</h1>
  <div class="concept-card">
    <div class="concept-text">Look at this circle. What fraction of the circle is shaded?</div>
    <aasha-sim id="sim-1" data-plugin="jsxgraph">
      <div class="interaction-container">Canvas Ready</div>
    </aasha-sim>
  </div>
  <div class="quiz-card" id="q1">
    <div class="quiz-question">What does the denominator represent?</div>
    <div class="quiz-opt" data-m="Denominator represents the total number of equal parts.">
      Total equal parts
    </div>
    <div class="quiz-opt" data-m="Remember: numerator is the parts counted, denominator is the total parts.">
      Counted parts
    </div>
    <div class="hint-box" data-tier="1" data-h1="Look at the bottom number." data-h2="Rule: denominator means total parts." data-h3="Analogy: slices in a whole pizza." data-h4="Step: identify which number is below the fraction bar."></div>
  </div>
</div>
</body>
</html>`;

  // ─── Test 1: Compliant Chapter ───
  const validPath = path.join(tmpDir, 'valid_chapter.html');
  fs.writeFileSync(validPath, validHtml, 'utf-8');
  const validReport = PedagogicalAuditor.audit(validPath);

  console.log(`[Test 1] Compliant Chapter Score: ${validReport.overallScore}/100`);
  console.log(`         Critical Violations: ${validReport.criticalViolationsCount}`);
  console.log(`         Sign-Off Allowed: ${validReport.signOffAllowed}`);
  if (validReport.criticalViolationsCount !== 0 || !validReport.signOffAllowed) {
    throw new Error('Test 1 Failed: Compliant chapter should have 0 critical violations and allowed sign-off.');
  }
  console.log('✔ Test 1 Passed: Compliant chapter passed with zero critical violations.\n');

  // ─── Test 2: Injected Answer Spoiler ───
  const spoilerHtml = validHtml.replace(
    'Remember: numerator is the parts counted',
    'Remember: the correct answer is Total equal parts'
  );
  const spoilerPath = path.join(tmpDir, 'spoiler_chapter.html');
  fs.writeFileSync(spoilerPath, spoilerHtml, 'utf-8');
  const spoilerReport = PedagogicalAuditor.audit(spoilerPath);

  console.log(`[Test 2] Spoiler Injected Chapter Score: ${spoilerReport.overallScore}/100`);
  console.log(`         Critical Violations: ${spoilerReport.criticalViolationsCount}`);
  console.log(`         Sign-Off Allowed: ${spoilerReport.signOffAllowed}`);
  const hasSpoilerViolation = spoilerReport.pillars.misconceptionsAndHints.criticalViolations.some(v => v.includes('Answer Leakage'));
  if (!hasSpoilerViolation || spoilerReport.signOffAllowed) {
    throw new Error('Test 2 Failed: Injected spoiler was not caught by Pillar 3, or sign-off was improperly allowed.');
  }
  console.log('✔ Test 2 Passed: Answer spoiler was correctly caught and HARD-BLOCKED sign-off.\n');

  // ─── Test 3: Injected External URL ───
  const externalHtml = validHtml.replace(
    '</head>',
    '<script src="https://external-cdn.example.com/analytics.js"></script></head>'
  );
  const externalPath = path.join(tmpDir, 'external_chapter.html');
  fs.writeFileSync(externalPath, externalHtml, 'utf-8');
  const externalReport = PedagogicalAuditor.audit(externalPath);

  console.log(`[Test 3] External URL Injected Chapter Score: ${externalReport.overallScore}/100`);
  console.log(`         Critical Violations: ${externalReport.criticalViolationsCount}`);
  console.log(`         Sign-Off Allowed: ${externalReport.signOffAllowed}`);
  const hasAirGapViolation = externalReport.pillars.airGappedSafety.criticalViolations.some(v => v.includes('Air-Gap Compromise'));
  if (!hasAirGapViolation || externalReport.signOffAllowed) {
    throw new Error('Test 3 Failed: Injected external URL was not caught by Pillar 4, or sign-off was improperly allowed.');
  }
  console.log('✔ Test 3 Passed: External URL was correctly caught and HARD-BLOCKED sign-off.\n');

  // ─── Test 4: Injected Oversized Bundle (>20 MB) ───
  const oversizedPath = path.join(tmpDir, 'oversized_chapter.html');
  fs.writeFileSync(oversizedPath, validHtml, 'utf-8');
  // Expand file beyond 20MB ceiling (20,971,520 bytes) using truncate/append
  const targetSize = 20971520 + 1024; // 20 MB + 1 KB
  const fd = fs.openSync(oversizedPath, 'r+');
  fs.ftruncateSync(fd, targetSize);
  fs.closeSync(fd);

  const oversizedReport = PedagogicalAuditor.audit(oversizedPath);
  console.log(`[Test 4] Oversized Bundle (${(targetSize / (1024 * 1024)).toFixed(2)} MB) Score: ${oversizedReport.overallScore}/100`);
  console.log(`         Critical Violations: ${oversizedReport.criticalViolationsCount}`);
  console.log(`         Sign-Off Allowed: ${oversizedReport.signOffAllowed}`);
  const hasBundleViolation = oversizedReport.pillars.airGappedSafety.criticalViolations.some(v => v.includes('Bundle Ceiling Exceeded'));
  if (!hasBundleViolation || oversizedReport.signOffAllowed) {
    throw new Error('Test 4 Failed: Injected oversized bundle was not caught by Pillar 4, or sign-off was improperly allowed.');
  }
  console.log('✔ Test 4 Passed: Oversized bundle (>20MB) was correctly caught and HARD-BLOCKED sign-off.\n');

  // Clean up tmp files
  try {
    fs.unlinkSync(validPath);
    fs.unlinkSync(spoilerPath);
    fs.unlinkSync(externalPath);
    fs.unlinkSync(oversizedPath);
    fs.rmdirSync(tmpDir);
  } catch {}

  console.log(chalk.green.bold('🎉 ALL AUTOMATED PEDAGOGICAL AUDITOR TESTS PASSED (100% VERIFIED)!\n'));
}

runAutomatedTests();
