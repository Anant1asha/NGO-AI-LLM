import test from 'node:test';
import assert from 'node:assert/strict';

import { ingestSubagent } from '../src/ingest_subagent.mjs';
import { simulationSubagent } from '../src/simulation_subagent.mjs';
import { assessmentSubagent } from '../src/assessment_subagent.mjs';
import { monolithSubagent } from '../src/monolith_subagent.mjs';

test('Unified 4-Stage Multi-Agent Orchestration Loop (Ingest -> Sim -> Asmt -> Monolith)', async () => {
  const contractPath = 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml';

  // 1. Task 1: Ingest Subagent
  const ingest = await ingestSubagent({ contractPath });
  assert.equal(ingest.success, true);
  assert.equal(ingest.contract.grade, 8);
  assert.equal(ingest.contract.topic, 'Squares and Cubes');

  // 2. Task 2: Simulation Subagent
  const sim = await simulationSubagent({
    contractData: {
      chapter_meta: { slug: ingest.contract.slug, class: ingest.contract.grade },
      curriculum_intent: { core_concepts: [{ id: 'concept_1', title: 'Square Gnomon' }] }
    }
  });
  assert.equal(sim.success, true);
  assert.ok(sim.clientScript.includes('SquareGnomonModel'));

  // 3. Task 3: Assessment Subagent
  const asmt = await assessmentSubagent({ contractPath, gameTemplateId: 'battlemath' });
  assert.equal(asmt.success, true);
  assert.equal(asmt.assessmentSpec.tiers.warmup.length, 12);
  assert.equal(asmt.assessmentSpec.tiers.deepDive.length, 14);
  assert.equal(asmt.assessmentSpec.tiers.boss.length, 8);
  assert.equal(asmt.verification.zeroSpoilersCertified, true);

  // 4. Task 4: Chapter Monolith Assembly Subagent
  const monolith = await monolithSubagent({
    contractPath,
    outputPath: 'Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html'
  });
  assert.equal(monolith.success, true);
  assert.equal(monolith.verification.offlineReady, true);
  assert.equal(monolith.verification.scopeLockedSizeUnder20MB, true);
  assert.equal(monolith.verification.touchTargetsCompliant, true);
  assert.equal(monolith.verification.mathInsulationCertified, true);
  assert.ok(monolith.byteSize < 20971520);
});
