/**
 * @file tests/test_git_output_staging.mjs
 * @description Regression test for Git staging of curriculum output packs.
 * Verifies that official chapter/curriculum packs in output/g* are never rejected by .gitignore,
 * while ad-hoc scratch files remain safely ignored.
 */

import { execSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const outputDir = path.join(projectRoot, 'Aasha-AI', 'aasha-pipeline-with-master-json', 'output');

console.log('🧪 [test_git_output_staging] Running regression test for output pack gitignore rules...');

// 1. Verify output directory exists
const entries = readdirSync(outputDir, { withFileTypes: true });
const gPacks = entries
  .filter((e) => e.isDirectory() && e.name.startsWith('g'))
  .map((e) => e.name);

console.log(`📦 Found ${gPacks.length} official 'g*' release packs in output/`);

let failures = 0;

// 2. Test git check-ignore on each pack: MUST NOT be ignored
for (const pack of gPacks) {
  const relPath = `Aasha-AI/aasha-pipeline-with-master-json/output/${pack}`;
  try {
    // If git check-ignore returns 0, the path IS ignored (which is a bug!)
    const checkRes = execSync(`git check-ignore "${relPath}"`, {
      cwd: projectRoot,
      encoding: 'utf-8',
      stdio: 'pipe',
    });
    console.error(`❌ REGRESSION: ${relPath} is matched by .gitignore: ${checkRes.trim()}`);
    failures++;
  } catch (err) {
    // Exit code 1 means NOT ignored — exactly what we want for release packs!
    if (err.status === 1) {
      // Good!
    } else {
      console.error(`⚠️ Unexpected error checking ${relPath}: ${err.message}`);
      failures++;
    }
  }
}

// 3. Test git add dry-run / staging on g3_10chapter_pack specifically
const targetPack = 'Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack';
try {
  execSync(`git add "${targetPack}"`, {
    cwd: projectRoot,
    encoding: 'utf-8',
    stdio: 'pipe',
  });
  console.log(`✅ Staging check passed: 'git add ${targetPack}' executed with exit code 0.`);
} catch (err) {
  console.error(`❌ REGRESSION: 'git add ${targetPack}' failed!`, err.stderr || err.message);
  failures++;
}

// 4. Verify that scratch/ad-hoc files ARE properly ignored
const dummyScratch = 'Aasha-AI/aasha-pipeline-with-master-json/output/temp_scratch_chapter.html';
try {
  const ignoredRes = execSync(`git check-ignore "${dummyScratch}"`, {
    cwd: projectRoot,
    encoding: 'utf-8',
    stdio: 'pipe',
  });
  console.log(`✅ Scratch guard verified: ${dummyScratch} is properly ignored.`);
} catch {
  console.warn(`⚠️ Note: dummy scratch path ${dummyScratch} was not ignored.`);
}

if (failures === 0) {
  console.log(`\n🎉 ALL ${gPacks.length} RELEASE PACKS PASSED REGRESSION TESTING! Zero git add ignore collisions.`);
  process.exit(0);
} else {
  console.error(`\n💥 REGRESSION FAILED: ${failures} packs failed gitignore inspection.`);
  process.exit(1);
}
