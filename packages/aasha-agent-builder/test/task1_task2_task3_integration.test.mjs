import test from 'node:test';
import assert from 'node:assert/strict';

import { ingestSubagent } from '../src/ingest_subagent.mjs';
import { simulationSubagent } from '../src/simulation_subagent.mjs';
import { assessmentSubagent } from '../src/assessment_subagent.mjs';

test('Complete Task 1 -> Task 2 -> Task 3 multi-agent pipeline workflow', async () => {
  // 1. Task 1: Ingest Contract
  const ingestResult = await ingestSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml'
  });
  assert.equal(ingestResult.success, true);
  assert.equal(ingestResult.contract.grade, 8);

  // 2. Task 2: Generate Simulation
  const simResult = await simulationSubagent({
    contractData: {
      chapter_meta: { slug: ingestResult.contract.slug, class: ingestResult.contract.grade },
      curriculum_intent: { core_concepts: [{ id: 'concept_1', title: 'Square Gnomon' }] }
    }
  });
  assert.equal(simResult.success, true);
  assert.ok(simResult.clientScript.length > 1000);

  // 3. Task 3: Generate 3-Tier Gamified Assessment Suite
  const assessmentResult = await assessmentSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml'
  });
  assert.equal(assessmentResult.success, true);
  assert.equal(assessmentResult.verification.zeroSpoilersCertified, true);
  assert.equal(assessmentResult.verification.touchTargetsCompliant, true);
  assert.equal(assessmentResult.verification.zeroNetworkDependencies, true);
  assert.equal(assessmentResult.verification.offlineReady, true);
  assert.equal(assessmentResult.assessmentSpec.tiers.warmup.length, 12);
  assert.equal(assessmentResult.assessmentSpec.tiers.deepDive.length, 14);
  assert.equal(assessmentResult.assessmentSpec.tiers.boss.length, 8);
  assert.ok(assessmentResult.measurements.clientScriptBytes < 100000);
  assert.ok(assessmentResult.clientScript.includes('<aasha-assessment>'));
});
