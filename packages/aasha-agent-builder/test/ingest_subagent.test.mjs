import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  resolveWorkspaceRoot,
  resolveSecurePath,
  verifySourceIntegrity,
  computeFileSha256,
  resolvePythonBinary,
  createIsolatedJobConfig,
  ingestSubagent,
} from '../src/ingest_subagent.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('resolveWorkspaceRoot finds repository root correctly', () => {
  const root = resolveWorkspaceRoot(__dirname);
  assert.ok(fs.existsSync(path.join(root, 'package.json')));
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'));
  assert.equal(pkg.name, 'aasha-learning-ecosystem-root');
});

test('resolveSecurePath allows valid in-boundary files and detects directory traversal attempts', () => {
  const root = resolveWorkspaceRoot(__dirname);
  const safePath = resolveSecurePath(root, 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml', { mustExist: true });
  assert.ok(fs.existsSync(safePath));

  // Traversal attack test: ../ escaping root
  assert.throws(() => {
    resolveSecurePath(path.join(root, 'packages'), '../../Windows/System32/calc.exe');
  }, /Security Violation: Path traversal detected/);
});

test('verifySourceIntegrity accurately calculates SHA-256 and asserts byte provenance without semantic hallucination', () => {
  const root = resolveWorkspaceRoot(__dirname);
  const contractPath = path.join(root, 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml');

  const hash = computeFileSha256(contractPath);
  assert.equal(hash.length, 64);

  const verifiedRes = verifySourceIntegrity(contractPath, hash);
  assert.equal(verifiedRes.verified, true);
  assert.equal(verifiedRes.status, 'SOURCE_INTEGRITY_VERIFIED');

  const mismatchedRes = verifySourceIntegrity(contractPath, '0000000000000000000000000000000000000000000000000000000000000000');
  assert.equal(mismatchedRes.verified, false);
  assert.equal(mismatchedRes.status, 'SOURCE_INTEGRITY_FAILED');
});

test('createIsolatedJobConfig generates dedicated job config overriding pipeline.output_dir', () => {
  const root = resolveWorkspaceRoot(__dirname);
  const masterConfig = path.join(root, 'Aasha-AI/aasha-pipeline-with-master-json/config.yaml');
  const tempJobDir = path.join(root, 'packages/aasha-agent-builder/test/temp_job');
  const tempOutputDir = path.join(tempJobDir, 'output');

  try {
    const jobConfigPath = createIsolatedJobConfig(masterConfig, tempJobDir, tempOutputDir);
    assert.ok(fs.existsSync(jobConfigPath));

    const content = fs.readFileSync(jobConfigPath, 'utf-8');
    const normalizedContent = content.replace(/\r?\n\s+/g, ' ');
    assert.ok(
      normalizedContent.includes(tempOutputDir.replace(/\\/g, '/')) ||
      normalizedContent.includes(tempOutputDir) ||
      normalizedContent.includes(tempOutputDir.replace(/\\/g, '\\\\'))
    );
  } finally {
    if (fs.existsSync(tempJobDir)) {
      fs.rmSync(tempJobDir, { recursive: true, force: true });
    }
  }
});

test('ingestSubagent coordinates contract ingestion with five-dimensional governance matrix', async () => {
  const result = await ingestSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml',
  });

  assert.equal(result.success, true);
  assert.ok(result.contract);
  assert.equal(result.contract.slug, 'squares_and_cubes');
  assert.equal(result.contract.coreConceptsCount, 5);
  assert.equal(result.contract.misconceptionsCount, 5);

  // Assert Five-Dimensional Orthogonal Governance Matrix
  assert.ok(result.governance);
  assert.equal(result.governance.qa_validation, 'QA_NOT_RUN');
  assert.equal(result.governance.pedagogical_review, 'PENDING_TEACHER_REVIEW');
  assert.equal(result.governance.release_authorization, 'NOT_RELEASED');
  // Byte integrity does not equal semantic grounding
  assert.notEqual(result.governance.semantic_grounding, 'TEXTBOOK_GROUNDING_VERIFIED');
});
