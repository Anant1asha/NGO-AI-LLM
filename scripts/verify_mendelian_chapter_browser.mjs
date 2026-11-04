/**
 * scripts/verify_mendelian_chapter_browser.mjs
 * Rigorous Playwright End-User Kid Experience & CDP Verification
 * Tests AVR-P321 interactive simulation and the 35th Certified HTML5 chapter.
 */

import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

const SIM_PATH = path.join(ROOT_DIR, 'assets', 'cdn', 'interactives', 'AVR-P321-bio-mendelian-punnett-square-sim.html');
const CHAPTER_PATH = path.join(ROOT_DIR, 'Aasha-AI', 'chapters', 'Heredity_Mendelian_Genetics_Punnett_Square_Class10_Gamified_v5.html');

async function runBrowserTests() {
  console.log('======================================================================');
  console.log(' 🧪 PLAYWRIGHT BROWSER VERIFICATION: MENDELIAN GENETICS CHAPTER');
  console.log('======================================================================\n');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 } // Standard mobile viewport (iPhone 12/13/14)
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    consoleErrors.push(err.message);
  });

  // ---------------------------------------------------------------------------
  // TEST SUITE 1: Standalone Simulation (AVR-P321)
  // ---------------------------------------------------------------------------
  console.log('--- [TEST SUITE 1/2] AVR-P321 Standalone Interactive Simulation ---');
  await page.goto(pathToFileURL(SIM_PATH).href, { waitUntil: 'domcontentloaded' });

  // 1. Check title & headers
  const title = await page.textContent('h1');
  console.log(`  • Title: "${title}" (Expected: contains Punnett Square)`);
  if (!title.includes('Punnett Square')) throw new Error('Simulation title mismatch');

  // 2. Check initial phenotype ratio (Tt x Tt -> 3 Tall : 1 Dwarf)
  const initialRatio = await page.textContent('#pheno_ratio');
  console.log(`  • Initial Phenotypic Ratio: "${initialRatio}" (Expected: 3 Tall : 1 Dwarf)`);
  if (!initialRatio.includes('3 Tall : 1 Dwarf')) throw new Error(`Unexpected initial ratio: ${initialRatio}`);

  // 3. Test Touch Target sizes (>= 44x44px)
  const p1_a1 = await page.$('#p1_a1');
  const box = await p1_a1.boundingBox();
  console.log(`  • Touch Target Size (p1_a1): ${box.width}x${box.height}px (Requirement: >=44x44px)`);
  if (box.width < 44 || box.height < 44) throw new Error(`Touch target size violation: ${box.width}x${box.height}`);

  // 4. Test Preset Button: P1 Cross TT x tt -> F1 (100% Tall)
  console.log('  • Clicking Preset: TT x tt (F1)...');
  await page.click('button:has-text("P1 Cross: TT × tt")');
  await page.waitForTimeout(100);

  const f1Ratio = await page.textContent('#pheno_ratio');
  console.log(`  • Post-Preset Phenotype Ratio: "${f1Ratio}" (Expected: 100% Tall)`);
  if (!f1Ratio.includes('100% Tall')) throw new Error(`F1 ratio failed: ${f1Ratio}`);

  const genoRatio = await page.textContent('#geno_ratio');
  console.log(`  • Post-Preset Genotype Ratio: "${genoRatio}" (Expected: 4 Tt)`);
  if (!genoRatio.includes('4 Tt')) throw new Error(`F1 genotype failed: ${genoRatio}`);

  // 5. Test Allele Toggle Interaction
  console.log('  • Clicking allele toggle to mutate female parent allele 2 (t -> T)...');
  await page.click('#p1_a2');
  await page.waitForTimeout(100);
  const mutatedRatio = await page.textContent('#pheno_ratio');
  console.log(`  • Post-Toggle Ratio: "${mutatedRatio}"`);

  // ---------------------------------------------------------------------------
  // TEST SUITE 2: 35th Certified HTML5 Chapter
  // ---------------------------------------------------------------------------
  console.log('\n--- [TEST SUITE 2/2] 35th Certified HTML5 Chapter ---');
  await page.goto(pathToFileURL(CHAPTER_PATH).href, { waitUntil: 'domcontentloaded' });

  // 1. Verify Brand Header & Coin Counter
  const coinsText = await page.textContent('#coins_count');
  console.log(`  • Initial Coins: ${coinsText}`);

  // 2. Test Section Tabs (Kid navigation)
  console.log('  • Testing Tab Switching: Key Concepts...');
  await page.click('#tab_theory');
  const theoryVisible = await page.isVisible('#sec_theory');
  console.log(`  • Key Concepts Section Visible: ${theoryVisible}`);
  if (!theoryVisible) throw new Error('Theory section did not display');

  // 3. Test Bilingual LLE Popup Tooltip
  console.log('  • Clicking LLE word tooltip ("Heredity")...');
  await page.click('.lle-word:has-text("Heredity")');
  await page.waitForTimeout(100);
  const popupVisible = await page.isVisible('#lle_popup');
  const popupTerm = await page.textContent('#lle_term');
  console.log(`  • LLE Definition Popup Visible: ${popupVisible} ("${popupTerm}")`);
  if (!popupVisible || !popupTerm.includes('HEREDITY')) throw new Error('LLE popup failed');

  // 4. Test TEAS Quiz Section
  console.log('  • Switching to TEAS Quiz Tab...');
  await page.click('#tab_quiz');
  const quizVisible = await page.isVisible('#sec_quiz');
  if (!quizVisible) throw new Error('Quiz section did not display');

  // Question 1: Check prompt
  const qPrompt = await page.textContent('#q_prompt');
  console.log(`  • Question 1 Prompt: "${qPrompt.slice(0, 60)}..."`);

  // Test Hint Scaffolding
  console.log('  • Requesting Hint 1 (H1)...');
  await page.click('#btn_hint');
  const hintText = await page.textContent('#hint_display');
  console.log(`  • Hint Text: "${hintText}"`);
  if (!hintText.includes('Hint 1:')) throw new Error('Hint 1 not rendered');

  // Answer Question 1 correctly: "Dominant allele"
  console.log('  • Answering Question 1: "Dominant allele"...');
  await page.click('button:has-text("Dominant allele")');
  await page.waitForTimeout(100);

  const fbText = await page.textContent('#feedback_box');
  console.log(`  • Answer Feedback: "${fbText.slice(0, 50)}..."`);
  if (!fbText.includes('Exemplary Mastery!')) throw new Error('Feedback not correct');

  const updatedCoins = await page.textContent('#coins_count');
  console.log(`  • Updated Coins After Correct Answer: ${updatedCoins} TEAS Coins (+20 awarded)`);
  if (parseInt(updatedCoins, 10) <= 0) throw new Error('Coins were not awarded');

  // Test Next Question
  console.log('  • Clicking Next Question...');
  await page.click('#btn_next');
  await page.waitForTimeout(100);
  const q2Prompt = await page.textContent('#q_prompt');
  console.log(`  • Question 2 Prompt: "${q2Prompt.slice(0, 60)}..."`);

  // Verify Console Cleanliness
  console.log(`\n  • Console Error Audit: ${consoleErrors.length} errors detected.`);
  if (consoleErrors.length > 0) {
    console.error('Console errors:', consoleErrors);
    throw new Error(`Console errors found: ${consoleErrors.join(', ')}`);
  }

  await browser.close();

  console.log('\n======================================================================');
  console.log(' 🎉 PLAYWRIGHT BROWSER VERIFICATION PASSED (100% SUCCESS RATE)');
  console.log('======================================================================\n');
}

runBrowserTests().catch(err => {
  console.error('Browser test failed:', err);
  process.exit(1);
});
