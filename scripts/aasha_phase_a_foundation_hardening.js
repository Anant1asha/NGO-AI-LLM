/**
 * scripts/aasha_phase_a_foundation_hardening.js
 * Node.js / CommonJS + ESM-compatible implementation of PHASE_A_FOUNDATION_AND_ROUTER_HARDENING
 * (Chunks A1, A2, A3) for AASHA-ARGON-SUPERADMIN-AUTONOMOUS-BUILDER-V3 (v3.0.0).
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const PROTECTED_BRANCHES = new Set(['main', 'master', 'HEAD', 'production', 'release', '']);
const REQUIRED_TARGET_BRANCH = 'aios/v2-bootstrap';
const MAX_DAILY_SPEND_USD = 1.0;

const METADATA_ONLY_FILES = new Set([
  'CHANGELOG.md',
  'VERIFICATION_REPORT.md',
  'SPRINT_VERIFICATION_REPORT.md',
  'PC_ANTIGRAVITY_STATE.json',
  'COLAB_ANTIGRAVITY_STATE.json'
]);

const PHASE_CHUNKING_ROADMAP = [
  {
    phase: 'PHASE_A_FOUNDATION_AND_ROUTER_HARDENING',
    chunks: [
      { id: 'A1', title: 'A1: 9Router gateway failover, concurrency locks, and persistent memory health verification' },
      { id: 'A2', title: 'A2: Unified state schema lock between PC_ANTIGRAVITY_STATE.json and COLAB_ANTIGRAVITY_STATE.json' },
      { id: 'A3', title: 'A3: Zero-No-Op commit guard in scripts/aasha_continuous_loop.mjs to stop empty loop spam' }
    ]
  },
  {
    phase: 'PHASE_B_COMPILER_AND_LLE_PIPELINE',
    chunks: [
      { id: 'B1', title: 'B1: Source PDF SHA-256 lock and Pydantic TLN chapter_spec.json 3..5 node validator hardening' },
      { id: 'B2', title: 'B2: 6-Agent v5-engine synthesis & 8-Layer LLE (60/40 English-Hindi dictionary injection)' },
      { id: 'B3', title: 'B3: Automated run_self_healing_qa_pass (max_attempts=2) integration with 10 Critical QA Rules' },
      { id: 'B4', title: 'B4: Offline base64 bundler (<20 MiB ceiling) and Dual-Output SQLite exporter (teas_content.db.gz)' }
    ]
  },
  {
    phase: 'PHASE_C_VISUAL_HARVEST_AND_INTERACTIVE_ENGINES',
    chunks: [
      { id: 'C1', title: 'C1: Certify AVR-P301..AVR-P321 visual mechanics and HARV-0001..HARV-0040 patterns via Playwright headless smoke checks' },
      { id: 'C2', title: 'C2: Wire AVR-P406-kingsmath-gamified-assessment and subject-specific interactive templates into experience_registry/registry.json' },
      { id: 'C3', title: 'C3: Pass all 97 strict assertions in Aasha-AIOS/tests/contract/test_visual_contract.js' }
    ]
  },
  {
    phase: 'PHASE_D_STUDENT_PWA_AND_CENTRE_SERVER',
    chunks: [
      { id: 'D1', title: 'D1: Fastify/SQLite Centre Server (Aasha-AI/server/server.js) + Migration 0003_teas_tokens_store_sync.py' },
      { id: 'D2', title: 'D2: Offline Student PWA (app.js, rewards.js, sync.js) with 5th Store tab and Staff PIN 1080 redemption flow' },
      { id: 'D3', title: 'D3: IndexedDB offline caching and low-RAM (4GB device) memory profiling' }
    ]
  },
  {
    phase: 'PHASE_E_AASHA_STUDIO_AND_WEB_ECOSYSTEM',
    chunks: [
      { id: 'E1', title: 'E1: aasha-studio authoring UI integration with live preview and QA scorecard' },
      { id: 'E2', title: 'E2: apsl-backend-foundation & New_repo_web API bridge and NCVET/PSSCIVE qualification mapping' },
      { id: 'E3', title: 'E3: Full E2E cross-repo integration test suite' }
    ]
  },
  {
    phase: 'PHASE_F_PRODUCTION_RELEASE_READINESS',
    chunks: [
      { id: 'F1', title: 'F1: Concurrency, fault-injection, and offline recovery stress testing across all repositories' },
      { id: 'F2', title: 'F2: Final SEC-001 security audit, bundle size audit, and release candidate tag on origin/aios/v2-bootstrap' }
    ]
  }
];

function resolveNextChunk(completedChunks = []) {
  const done = new Set(completedChunks);
  for (const phaseObj of PHASE_CHUNKING_ROADMAP) {
    for (const chunk of phaseObj.chunks) {
      if (!done.has(chunk.id)) {
        return { phase: phaseObj.phase, id: chunk.id, title: chunk.title };
      }
    }
  }
  return {
    phase: 'PHASE_F_PRODUCTION_RELEASE_READINESS',
    id: 'ALL_DONE',
    title: '100% Phases A-F Completed'
  };
}

function evaluateZeroNoOpDiff(stagedFiles = [], diffText = '', targetBranch = REQUIRED_TARGET_BRANCH) {
  const branch = String(targetBranch || '').trim();
  if (PROTECTED_BRANCHES.has(branch) || branch !== REQUIRED_TARGET_BRANCH) {
    throw new Error(`[SEC-001/BRANCH-GUARD] Prohibited branch target: ${branch}`);
  }
  const normalized = stagedFiles.map(f => String(f).replace(/\\/g, '/').trim()).filter(Boolean);
  const functionalFiles = [];
  const metadataFiles = [];

  for (const f of normalized) {
    if (METADATA_ONLY_FILES.has(path.basename(f))) {
      metadataFiles.push(f);
    } else {
      functionalFiles.push(f);
    }
  }

  const volatileRe = /^\+.*(?:"timestamp|"last_run_|"updated_at|"Date"\s*:|\*\*Date\*\*|\*\*Timestamp\*\*|## \[\d{4}-\d{2}-\d{2}T)/i;
  const substantiveLines = [];
  for (const line of String(diffText || '').split(/\r?\n/)) {
    if (!line.startsWith('+') || line.startsWith('+++')) continue;
    if (volatileRe.test(line)) continue;
    const cleaned = line.slice(1).trim();
    if (cleaned) substantiveLines.push(cleaned);
  }

  const allowCommit = functionalFiles.length > 0 && (substantiveLines.length > 0 || diffText === '');
  const diffSha256 = crypto
    .createHash('sha256')
    .update(functionalFiles.slice().sort().join('\n') + '\n' + substantiveLines.join('\n'))
    .digest('hex');

  return {
    allowCommit,
    reason: allowCommit ? 'FUNCTIONAL_PROGRESS_VERIFIED' : 'ZERO_NO_OP_BLOCKED',
    targetBranch: branch,
    functionalFilesCount: functionalFiles.length,
    functionalFiles,
    metadataFilesCount: metadataFiles.length,
    metadataFiles,
    substantiveAddedLinesCount: substantiveLines.length,
    functionalDiffSha256: diffSha256
  };
}

module.exports = {
  PROTECTED_BRANCHES,
  REQUIRED_TARGET_BRANCH,
  MAX_DAILY_SPEND_USD,
  METADATA_ONLY_FILES,
  PHASE_CHUNKING_ROADMAP,
  resolveNextChunk,
  evaluateZeroNoOpDiff
};
