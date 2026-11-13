/**
 * packages/aasha-agent-builder/test/asset_resolver.test.mjs
 * AASHA AIOS — Universal Resource Intelligence & Asset Resolver Bridge (URIRA) Test Suite
 *
 * Verifies M1 capabilities:
 * - SQLite schema initialization (urira_resources & urira_reuse_ledger)
 * - Automated catalog seeding (28 certified local interactives)
 * - Multi-subject requirement resolution (Math, Physics, Biology, Chemistry)
 * - Quality gate compliance auditing (<20MB, offline, mobile viewport)
 * - Token savings calculation and reuse transaction logging
 */

import { test, describe, before } from 'node:test';
import * as assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import {
  assetResolver,
  initUriraDatabase,
  seedUriraResources,
  auditAssetCompliance,
  recordReuseTransaction,
  CERTIFIED_LOCAL_INTERACTIVES
} from '../src/asset_resolver.mjs';
import { resolveWorkspaceRoot } from '../src/ingest_subagent.mjs';

describe('AASHA M1 — Universal Asset Resolver Bridge (URIRA)', () => {
  const root = resolveWorkspaceRoot();
  const testDbPath = path.resolve(root, 'aasha_operational.db');

  before(() => {
    // Ensure database tables exist and are seeded
    initUriraDatabase(testDbPath);
    seedUriraResources(testDbPath);
  });

  test('URIRA-01: SQLite Schema Initialization & Table Verification', () => {
    const db = new DatabaseSync(testDbPath);
    const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(t => t.name);
    
    assert.ok(tables.includes('urira_resources'), 'Table urira_resources must exist');
    assert.ok(tables.includes('urira_reuse_ledger'), 'Table urira_reuse_ledger must exist');

    const countRow = db.prepare('SELECT COUNT(*) as count FROM urira_resources').get();
    assert.ok(countRow.count >= 28, `Must contain at least 28 certified resources, found ${countRow.count}`);
  });

  test('URIRA-02: Resolves Mathematics / Number Line to AVR-P301', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Mathematics',
      grade: 8,
      concept: 'Rational Numbers on Number Line',
      topics: ['rational numbers', 'placement', 'number line']
    });

    assert.equal(result.matched, true, 'Must find a certified match');
    assert.equal(result.tier, 'TIER_1_CERTIFIED_LOCAL', 'Must resolve to Tier 1');
    assert.equal(result.resource.id, 'AVR-P301', 'Must resolve to AVR-P301 Number Line Marker');
    assert.equal(result.resource.license, 'MIT');
    assert.ok(result.resource.embedSnippet.includes('data-resource-id="AVR-P301"'));
    assert.ok(result.tokenSavings.totalSaved >= 20000, 'Must record token savings');
    assert.ok(result.latencyMs < 50, 'Lookup must be ultra-fast (<50ms)');
  });

  test('URIRA-03: Resolves Mathematics / Fraction Strips to AVR-P302', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Mathematics',
      grade: 4,
      concept: 'Equivalent Fractions and Fraction Strips',
      topics: ['fraction strips', 'parts of a whole']
    });

    assert.equal(result.matched, true);
    assert.equal(result.resource.id, 'AVR-P302', 'Must resolve to AVR-P302 Fraction Strip Visualizer');
  });

  test('URIRA-04: Resolves Physics / Vernier Caliper to AVR-P401', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Physics',
      grade: 11,
      concept: 'Units and Measurement',
      topics: ['vernier calipers', 'least count', 'zero error']
    });

    assert.equal(result.matched, true);
    assert.equal(result.resource.id, 'AVR-P401', 'Must resolve to AVR-P401 Vernier Caliper Virtual Lab');
    assert.equal(result.resource.family, 'measurement-lab');
  });

  test('URIRA-05: Resolves Physics / Magnetic Lorentz Force to AVR-P402', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Physics',
      grade: 12,
      concept: 'Moving Charges and Magnetism',
      topics: ['lorentz force', 'cyclotron motion', 'magnetic field']
    });

    assert.equal(result.matched, true);
    assert.equal(result.resource.id, 'AVR-P402', 'Must resolve to AVR-P402 Magnetic Lorentz Force');
  });

  test('URIRA-06: Resolves Biology / Mendelian Genetics to AVR-P321-bio', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Biology',
      grade: 10,
      concept: 'Heredity and Evolution',
      topics: ['mendelian genetics', 'punnett square', 'alleles']
    });

    assert.equal(result.matched, true);
    assert.equal(result.resource.id, 'AVR-P321-bio', 'Must resolve to AVR-P321-bio Punnett Square Sim');
  });

  test('URIRA-07: Resolves Chemistry / Atom Builder to AVR-P313', () => {
    const result = assetResolver.resolveAsset({
      subject: 'Chemistry',
      grade: 9,
      concept: 'Structure of the Atom',
      topics: ['protons neutrons electrons', 'atomic mass', 'atom builder']
    });

    assert.equal(result.matched, true);
    assert.equal(result.resource.id, 'AVR-P313', 'Must resolve to AVR-P313 Atom Builder');
  });

  test('URIRA-08: Quality Gate Compliance Audit on Certified Asset', () => {
    const assetPath = path.resolve(root, 'assets', 'cdn', 'interactives', 'AVR-P301-number-line-marker.html');
    const audit = auditAssetCompliance(assetPath);

    assert.equal(audit.passed, true, 'Certified asset must pass quality gate');
    assert.ok(audit.bytes < 20971520, 'Asset must be under 20 MiB ceiling');
    assert.equal(audit.violations.length, 0, 'Must have zero quality violations');
  });

  test('URIRA-09: Records Reuse Transaction in SQLite Ledger', () => {
    const tx = {
      resolutionId: 'test_res_001',
      chapterId: 'mathematics_class8_rational_numbers',
      conceptNodeId: 'node_1',
      resourceId: 'AVR-P301',
      tierResolved: 'TIER_1_CERTIFIED_LOCAL',
      tokensSaved: 32000,
      usdSaved: 0.064,
      latencyMs: 1.2
    };

    const res = recordReuseTransaction(testDbPath, tx);
    assert.equal(res.recorded, true);

    const db = new DatabaseSync(testDbPath);
    const row = db.prepare('SELECT * FROM urira_reuse_ledger WHERE resolution_id = ?').get('test_res_001');
    assert.ok(row, 'Transaction record must exist in sqlite');
    assert.equal(row.resource_id, 'AVR-P301');
    assert.equal(row.tokens_saved, 32000);
  });

  test('URIRA-10: Fallback to Tier 4 when concept is completely unknown', () => {
    const result = assetResolver.resolveAsset({
      subject: 'UnknownSubject',
      grade: 99,
      concept: 'CompletelyUnmatchedNonExistentPhenomenon'
    });

    assert.equal(result.matched, false);
    assert.equal(result.tier, 'TIER_4_SYNTHESIS_FALLBACK');
    assert.equal(result.resource, null);
    assert.equal(result.tokenSavings.totalSaved, 0);
  });
});
