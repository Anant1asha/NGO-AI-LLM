import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function sha256(filePath) {
  const content = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(content).digest('hex');
}

const FILES = {
  task1_src: 'packages/aasha-agent-builder/src/ingest_subagent.mjs',
  task1_test: 'packages/aasha-agent-builder/test/ingest_subagent.test.mjs',
  task2_src: 'packages/aasha-agent-builder/src/simulation_subagent.mjs',
  task2_test: 'packages/aasha-agent-builder/test/simulation_subagent.test.mjs',
  task3_src: 'packages/aasha-agent-builder/src/assessment_subagent.mjs',
  task3_test: 'packages/aasha-agent-builder/test/assessment_subagent.test.mjs',
  integration_test: 'packages/aasha-agent-builder/test/task1_task2_task3_integration.test.mjs'
};

const EXPECTED_HASHES = {
  task1_src: '73ef4d19d87f35d6d3158b664ded03c1677a2273c6a57a0e0227089c75ad22a1',
  task2_src: 'da1a9e7cb1cb5ad3850fe2420e03de1ed307e989baeb6fe95f1531ae48c32289',
  task2_test: 'dc1326a47a075743e02b8dcd994c2cbfe0563cfdf9c8ce94b648d83a2cf52b62',
  task3_src: '28647ec759afc558521f1f4ebb945b3a62ea75c804507149fe045b2159003e18',
  task3_test: '59afcafda87cd4a377da8e86a75c7bb9ebe1dba9681d9df5f9e7056e0d105594',
  integration_test: '95f1e8312fdd8bc02877ce6dd56b7fab7fecd81748133382de8f41c04692ea25'
};

console.log('--- AUDITING SUBAGENT IMMUTABILITY ---');
let allMatch = true;

for (const [key, relPath] of Object.entries(FILES)) {
  const fullPath = path.resolve(relPath);
  if (!fs.existsSync(fullPath)) {
    console.error(`Missing file: ${relPath}`);
    allMatch = false;
    continue;
  }
  const currentHash = sha256(fullPath);
  const expectedHash = EXPECTED_HASHES[key];
  const match = expectedHash ? (currentHash === expectedHash) : true;
  console.log(`${key} (${relPath}):`);
  console.log(`  Current : ${currentHash}`);
  if (expectedHash) {
    console.log(`  Expected: ${expectedHash}`);
    console.log(`  Status  : ${match ? 'MATCH (100% BIT-IDENTICAL / IMMUTABLE)' : 'MISMATCH'}`);
  }
  if (!match) allMatch = false;
}

if (!allMatch) {
  console.error('\nERROR: Subagent immutability check failed!');
  process.exit(1);
} else {
  console.log('\nSUCCESS: All subagents remain 100% bit-identical and immutable.');
}
