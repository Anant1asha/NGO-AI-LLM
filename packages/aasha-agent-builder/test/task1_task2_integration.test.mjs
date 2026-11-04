import test from 'node:test';
import assert from 'node:assert/strict';

import { ingestSubagent } from '../src/ingest_subagent.mjs';
import { simulationSubagent } from '../src/simulation_subagent.mjs';

test('Task 1 Ingest output flows seamlessly into Task 2 Simulation coordinator', async () => {
  // Step 1: Execute Task 1 Ingestion
  const ingestResult = await ingestSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml',
  });

  assert.equal(ingestResult.success, true);
  assert.ok(ingestResult.contract);
  assert.equal(ingestResult.contract.slug, 'squares_and_cubes');

  // Step 2: Feed Ingestion contract data directly into Task 2 Simulation subagent
  const simResult = await simulationSubagent({
    contractData: {
      chapter_meta: {
        slug: ingestResult.contract.slug,
        class: ingestResult.contract.grade,
      },
      curriculum_intent: {
        core_concepts: [
          {
            id: 'concept_1',
            title: "Queen Ratnamanjuri's Lockers & Geometric Dot Grids",
          },
        ],
      },
      misconceptions: [
        { id: 'misc_linearization' },
      ],
    },
  });

  assert.equal(simResult.success, true);
  assert.equal(simResult.simulationSpec.conceptId, 'concept_1');
  assert.equal(simResult.simulationSpec.touchTargetMinPixels, 44);
  assert.equal(simResult.verification.contractCompliant, true);
  assert.equal(simResult.verification.zeroNetworkDependencies, true);
  assert.equal(simResult.verification.offlineReady, true);
});
