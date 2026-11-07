/**
 * AASHA AIOS Multi-Tier Memory Synchronization & Health Engine
 * 
 * Synchronizes and validates all 4 persistent memory tiers:
 *   Tier 1: Serena MCP Local Semantic Memory (.serena/memories/*.md)
 *   Tier 2: Mem0 Local Episodic Preference Store (.scratch/mem0_store.json)
 *   Tier 3: Local SQLite Operational Knowledge Graph (aasha_operational.db)
 *   Tier 4: Graphify Codebase AST Graph (graphify-out/graph.json)
 * 
 * Uses Node.js v24 native `node:sqlite` (DatabaseSync) with zero external npm dependencies.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as child_process from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');

// Path Constants
const SERENA_DIR = path.join(PROJECT_ROOT, '.serena', 'memories');
const SCRATCH_DIR = path.join(PROJECT_ROOT, '.scratch');
const MEM0_FILE = path.join(SCRATCH_DIR, 'mem0_store.json');
const SQLITE_FILE = path.join(PROJECT_ROOT, 'aasha_operational.db');
const GRAPHIFY_FILE = path.join(PROJECT_ROOT, 'graphify-out', 'graph.json');

export const CORE_SERENA_MEMORIES = [
  'core',
  'local_memory',
  'tech_stack',
  'suggested_commands',
  'conventions',
  'task_completion',
  'memory_maintenance',
];

export interface TierHealth {
  name: string;
  tier: number;
  status: 'HEALTHY' | 'DEGRADED' | 'HEALED';
  details: string;
  recordsCount: number;
}

export interface MemorySyncReport {
  timestamp: string;
  project: string;
  overallStatus: 'SYNCED' | 'DEGRADED';
  tiers: {
    serena: TierHealth;
    mem0: TierHealth;
    sqlite: TierHealth;
    graphify: TierHealth;
  };
  actionsTaken: string[];
}

/**
 * Tier 1: Serena MCP Local Memory Auditor
 */
export function auditSerenaTier(): { health: TierHealth; memoryNames: string[]; contents: Map<string, string> } {
  const contents = new Map<string, string>();
  const found: string[] = [];
  const missing: string[] = [];

  if (!fs.existsSync(SERENA_DIR)) {
    return {
      health: {
        name: 'Serena MCP Local Semantic Memory',
        tier: 1,
        status: 'DEGRADED',
        details: `Directory missing: ${SERENA_DIR}`,
        recordsCount: 0,
      },
      memoryNames: [],
      contents,
    };
  }

  for (const name of CORE_SERENA_MEMORIES) {
    const filePath = path.join(SERENA_DIR, `${name}.md`);
    if (fs.existsSync(filePath)) {
      found.push(name);
      contents.set(name, fs.readFileSync(filePath, 'utf-8'));
    } else {
      missing.push(name);
    }
  }

  const isHealthy = missing.length === 0;
  return {
    health: {
      name: 'Serena MCP Local Semantic Memory',
      tier: 1,
      status: isHealthy ? 'HEALTHY' : 'DEGRADED',
      details: isHealthy
        ? `All ${found.length}/${CORE_SERENA_MEMORIES.length} core memories present`
        : `Missing memories: ${missing.join(', ')}`,
      recordsCount: found.length,
    },
    memoryNames: found,
    contents,
  };
}

/**
 * Tier 2: Mem0 Local Episodic Store Validator & Self-Healer
 */
export function auditAndHealMem0Tier(): { health: TierHealth; action?: string; records: any[] } {
  if (!fs.existsSync(SCRATCH_DIR)) {
    fs.mkdirSync(SCRATCH_DIR, { recursive: true });
  }

  let records: any[] = [];
  let action: string | undefined;

  if (!fs.existsSync(MEM0_FILE)) {
    const initialStore = {
      version: '1.0.0',
      lastSync: new Date().toISOString(),
      records: [
        {
          id: 'mem0_init_001',
          scope: 'Project',
          key: 'ecosystem_identity',
          value: 'AASHA AIOS Autonomous AI Agent Ecosystem',
          context: 'System invariant initialized via aasha_memory_engine',
          updatedAt: new Date().toISOString(),
        },
        {
          id: 'mem0_init_002',
          scope: 'Global',
          key: 'api_routing_policy',
          value: 'Tier 1 OpenRouter free pool with zero-bleed lockout on paid Gemini tokens',
          context: 'Anti-bleed governance invariant',
          updatedAt: new Date().toISOString(),
        },
      ],
    };
    fs.writeFileSync(MEM0_FILE, JSON.stringify(initialStore, null, 2), 'utf-8');
    records = initialStore.records;
    action = 'Created default .scratch/mem0_store.json store';
  } else {
    try {
      const raw = fs.readFileSync(MEM0_FILE, 'utf-8');
      const parsed = JSON.parse(raw);
      records = Array.isArray(parsed.records) ? parsed.records : [];
    } catch (err: any) {
      // Self-heal corrupted JSON
      const backupFile = `${MEM0_FILE}.corrupted.${Date.now()}`;
      fs.renameSync(MEM0_FILE, backupFile);
      const healedStore = {
        version: '1.0.0',
        lastSync: new Date().toISOString(),
        records: [
          {
            id: 'mem0_recovered_001',
            scope: 'Project',
            key: 'recovery_marker',
            value: `Recovered from corrupted store (backup saved to ${path.basename(backupFile)})`,
            updatedAt: new Date().toISOString(),
          },
        ],
      };
      fs.writeFileSync(MEM0_FILE, JSON.stringify(healedStore, null, 2), 'utf-8');
      records = healedStore.records;
      action = `Self-healed corrupted store; backed up original to ${path.basename(backupFile)}`;
    }
  }

  return {
    health: {
      name: 'Mem0 Local Episodic Store',
      tier: 2,
      status: action ? 'HEALED' : 'HEALTHY',
      details: action ? action : `Store intact at .scratch/mem0_store.json (${records.length} records)`,
      recordsCount: records.length,
    },
    action,
    records,
  };
}

/**
 * Tier 3: Local SQLite Operational Knowledge Graph Engine
 */
export function auditAndReconcileSQLiteTier(serenaContents: Map<string, string>, mem0Records: any[]): {
  health: TierHealth;
  actions: string[];
} {
  const actions: string[] = [];
  let db: DatabaseSync;

  const dbExisted = fs.existsSync(SQLITE_FILE);
  try {
    db = new DatabaseSync(SQLITE_FILE);
  } catch (err: any) {
    return {
      health: {
        name: 'Native SQLite Operational Knowledge Graph',
        tier: 3,
        status: 'DEGRADED',
        details: `Failed to open database: ${err.message}`,
        recordsCount: 0,
      },
      actions: [`Database open error: ${err.message}`],
    };
  }

  if (!dbExisted) {
    actions.push('Created aasha_operational.db');
  }

  // Schema Initialization
  db.exec(`
    CREATE TABLE IF NOT EXISTS concept_nodes (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      domain TEXT NOT NULL,
      category TEXT NOT NULL,
      metadata TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS operational_state (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      tier TEXT NOT NULL DEFAULT 'local',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS memory_sync_audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      status TEXT NOT NULL,
      details TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  // Auto-seed Serena core memories into concept_nodes if missing
  const insertConcept = db.prepare(`
    INSERT INTO concept_nodes (id, name, domain, category, metadata, updated_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(id) DO UPDATE SET
      metadata = excluded.metadata,
      updated_at = CURRENT_TIMESTAMP
  `);

  let seededConcepts = 0;
  for (const [name, content] of serenaContents.entries()) {
    const id = `serena_mem_${name}`;
    const preview = content.slice(0, 300).replace(/\r?\n/g, ' ');
    insertConcept.run(id, `mem:${name}`, 'AASHA_AIOS', 'SemanticMemory', JSON.stringify({ preview, size: content.length }));
    seededConcepts++;
  }
  if (seededConcepts > 0) {
    actions.push(`Reconciled ${seededConcepts} Serena memories into concept_nodes`);
  }

  // Sync Mem0 records into operational_state
  const insertState = db.prepare(`
    INSERT INTO operational_state (key, value, tier, updated_at)
    VALUES (?, ?, 'mem0', CURRENT_TIMESTAMP)
    ON CONFLICT(key) DO UPDATE SET
      value = excluded.value,
      updated_at = CURRENT_TIMESTAMP
  `);

  let seededState = 0;
  for (const record of mem0Records) {
    if (record.key && record.value !== undefined) {
      const stateKey = `mem0:${record.scope || 'Global'}:${record.key}`;
      insertState.run(stateKey, typeof record.value === 'string' ? record.value : JSON.stringify(record.value));
      seededState++;
    }
  }
  if (seededState > 0) {
    actions.push(`Synced ${seededState} Mem0 records into operational_state`);
  }

  // Count total records across tables
  const conceptCountStmt = db.prepare('SELECT COUNT(*) as c FROM concept_nodes');
  const conceptCount = Number((conceptCountStmt.get() as any)?.c || 0);

  const stateCountStmt = db.prepare('SELECT COUNT(*) as c FROM operational_state');
  const stateCount = Number((stateCountStmt.get() as any)?.c || 0);

  const totalRecords = conceptCount + stateCount;

  // Log audit run
  const insertAudit = db.prepare(`
    INSERT INTO memory_sync_audit_log (status, details)
    VALUES ('SYNC_COMPLETED', ?)
  `);
  insertAudit.run(JSON.stringify({ actions, totalRecords, timestamp: new Date().toISOString() }));

  db.close();

  return {
    health: {
      name: 'Native SQLite Operational Knowledge Graph',
      tier: 3,
      status: !dbExisted || actions.length > 0 ? 'HEALED' : 'HEALTHY',
      details: `Active aasha_operational.db (${conceptCount} concept_nodes, ${stateCount} operational_state rows)`,
      recordsCount: totalRecords,
    },
    actions,
  };
}

/**
 * Auto-heal baseline AST Knowledge Graph for fresh checkouts and CI environments
 * where graphify-out/ is git-ignored.
 */
export function autoHealBaselineGraphify(): { nodesCount: number; action: string } {
  const graphDir = path.dirname(GRAPHIFY_FILE);
  if (!fs.existsSync(graphDir)) {
    fs.mkdirSync(graphDir, { recursive: true });
  }

  // Attempt official graphify build if graphify CLI is available in PATH
  try {
    child_process.execSync('graphify build', { cwd: PROJECT_ROOT, stdio: 'ignore', timeout: 15000 });
    if (fs.existsSync(GRAPHIFY_FILE)) {
      const raw = fs.readFileSync(GRAPHIFY_FILE, 'utf-8');
      const data = JSON.parse(raw);
      const count = data.nodes?.length || data.graph?.nodes?.length || 0;
      if (count > 0) {
        return {
          nodesCount: count,
          action: `Generated AST knowledge graph via graphify build (${count} nodes)`,
        };
      }
    }
  } catch {
    // graphify CLI not in PATH or build timed out; proceed with baseline synthesis
  }

  const nodes: any[] = [];
  const links: any[] = [];

  // 1. Seed Core Serena memory nodes
  for (const name of CORE_SERENA_MEMORIES) {
    nodes.push({
      id: `mem:${name}`,
      label: `Serena Memory: ${name}`,
      type: 'SemanticMemory',
      community: 'Governance',
    });
  }

  // 2. Seed Foundation catalog nodes from experience_registry
  const registryFile = path.join(PROJECT_ROOT, 'Aasha-AI', 'experience_registry', 'registry.json');
  if (fs.existsSync(registryFile)) {
    try {
      const rawReg = fs.readFileSync(registryFile, 'utf-8');
      const reg = JSON.parse(rawReg);
      const foundations = reg.foundations || [];
      for (const f of foundations) {
        nodes.push({
          id: f.id,
          label: f.name || f.id,
          type: 'SimulationFoundation',
          community: f.category || 'EducationalFoundation',
          subjects: f.subjects || (f.subject ? [f.subject] : []),
        });
        links.push({
          source: 'mem:tech_stack',
          target: f.id,
          relation: 'REGISTERED_FOUNDATION',
        });
      }
    } catch {
      // Fallback on parse failure
    }
  }

  // 3. Seed Pipeline Agents from agents.json
  const agentsFile = path.join(PROJECT_ROOT, 'agents.json');
  if (fs.existsSync(agentsFile)) {
    try {
      const rawAgents = fs.readFileSync(agentsFile, 'utf-8');
      const ag = JSON.parse(rawAgents);
      const list = ag.agents || (Array.isArray(ag) ? ag : []);
      for (const a of list) {
        const aId = a.name || a.id;
        if (aId) {
          nodes.push({
            id: `agent:${aId}`,
            label: aId,
            type: 'AIOSPipelineAgent',
            community: 'MultiAgentOrchestration',
          });
          links.push({
            source: 'mem:core',
            target: `agent:${aId}`,
            relation: 'ORCHESTRATED_AGENT',
          });
        }
      }
    } catch {
      // Fallback on parse failure
    }
  }

  // 4. Fallback minimum node guarantee
  if (nodes.length === 0) {
    nodes.push({
      id: 'aasha_aios_core',
      label: 'AASHA AIOS Core System',
      type: 'SystemCore',
      community: 'Architecture',
    });
  }

  const baselineGraph = {
    directed: true,
    multigraph: false,
    graph: { name: 'AASHA AIOS Baseline Knowledge Graph (Auto-Seeded)' },
    nodes,
    links,
  };

  fs.writeFileSync(GRAPHIFY_FILE, JSON.stringify(baselineGraph, null, 2), 'utf-8');
  return {
    nodesCount: nodes.length,
    action: `Auto-initialized baseline AST knowledge graph (${nodes.length} nodes seeded)`,
  };
}

/**
 * Tier 4: Graphify AST Codebase Knowledge Graph Auditor
 */
export function auditGraphifyTier(): { health: TierHealth; action?: string } {
  let action: string | undefined;

  if (!fs.existsSync(GRAPHIFY_FILE)) {
    const healResult = autoHealBaselineGraphify();
    action = healResult.action;
    return {
      health: {
        name: 'Graphify Codebase AST Knowledge Graph',
        tier: 4,
        status: 'HEALED',
        details: healResult.action + ' (expand via graphify build)',
        recordsCount: healResult.nodesCount,
      },
      action,
    };
  }

  try {
    const raw = fs.readFileSync(GRAPHIFY_FILE, 'utf-8');
    const data = JSON.parse(raw);
    const nodesCount = data.nodes?.length || data.graph?.nodes?.length || 0;
    if (nodesCount === 0) {
      const healResult = autoHealBaselineGraphify();
      action = healResult.action;
      return {
        health: {
          name: 'Graphify Codebase AST Knowledge Graph',
          tier: 4,
          status: 'HEALED',
          details: healResult.action + ' (recovered empty graph.json)',
          recordsCount: healResult.nodesCount,
        },
        action,
      };
    }

    return {
      health: {
        name: 'Graphify Codebase AST Knowledge Graph',
        tier: 4,
        status: 'HEALTHY',
        details: `Active AST knowledge graph (${nodesCount} nodes indexed)`,
        recordsCount: nodesCount,
      },
    };
  } catch (err: any) {
    // Malformed graph JSON, auto-heal
    const healResult = autoHealBaselineGraphify();
    action = `Recovered from malformed graph.json: ${healResult.action}`;
    return {
      health: {
        name: 'Graphify Codebase AST Knowledge Graph',
        tier: 4,
        status: 'HEALED',
        details: action,
        recordsCount: healResult.nodesCount,
      },
      action,
    };
  }
}

/**
 * Master Synchronization & Health Pipeline
 */
export function runMemorySync(): MemorySyncReport {
  const actionsTaken: string[] = [];

  // Tier 1: Serena MCP
  const serenaResult = auditSerenaTier();

  // Tier 2: Mem0 Local Store
  const mem0Result = auditAndHealMem0Tier();
  if (mem0Result.action) actionsTaken.push(mem0Result.action);

  // Tier 3: SQLite Operational Graph
  const sqliteResult = auditAndReconcileSQLiteTier(serenaResult.contents, mem0Result.records);
  actionsTaken.push(...sqliteResult.actions);

  // Tier 4: Graphify AST
  const graphifyResult = auditGraphifyTier();
  if (graphifyResult.action) actionsTaken.push(graphifyResult.action);

  const isDegraded =
    serenaResult.health.status === 'DEGRADED' ||
    mem0Result.health.status === 'DEGRADED' ||
    sqliteResult.health.status === 'DEGRADED' ||
    graphifyResult.health.status === 'DEGRADED';

  const report: MemorySyncReport = {
    timestamp: new Date().toISOString(),
    project: 'NGO AI LLM',
    overallStatus: isDegraded ? 'DEGRADED' : 'SYNCED',
    tiers: {
      serena: serenaResult.health,
      mem0: mem0Result.health,
      sqlite: sqliteResult.health,
      graphify: graphifyResult.health,
    },
    actionsTaken,
  };

  return report;
}

export function printMemorySyncReport(report: MemorySyncReport): void {
  console.log('================================================================');
  console.log('       ॥ AASHA AIOS 4-Tier Memory Synchronization Engine ॥       ');
  console.log('================================================================');
  console.log(`• Project         : ${report.project}`);
  console.log(`• Timestamp       : ${report.timestamp}`);
  console.log(`• Overall Status  : ${report.overallStatus === 'SYNCED' ? '✅ FULLY SYNCHRONIZED & HEALTHY' : '⚠️ ATTENTION / DEGRADED'}`);
  console.log('----------------------------------------------------------------');
  console.log(`[Tier 1] ${report.tiers.serena.name}`);
  console.log(`         Status : ${report.tiers.serena.status === 'HEALTHY' ? '✅' : '⚠️'} ${report.tiers.serena.status}`);
  console.log(`         Detail : ${report.tiers.serena.details}`);
  console.log(`[Tier 2] ${report.tiers.mem0.name}`);
  console.log(`         Status : ${report.tiers.mem0.status === 'HEALTHY' || report.tiers.mem0.status === 'HEALED' ? '✅' : '⚠️'} ${report.tiers.mem0.status}`);
  console.log(`         Detail : ${report.tiers.mem0.details}`);
  console.log(`[Tier 3] ${report.tiers.sqlite.name}`);
  console.log(`         Status : ${report.tiers.sqlite.status === 'HEALTHY' || report.tiers.sqlite.status === 'HEALED' ? '✅' : '⚠️'} ${report.tiers.sqlite.status}`);
  console.log(`         Detail : ${report.tiers.sqlite.details}`);
  console.log(`[Tier 4] ${report.tiers.graphify.name}`);
  console.log(`         Status : ${report.tiers.graphify.status === 'HEALTHY' ? '✅' : '⚠️'} ${report.tiers.graphify.status}`);
  console.log(`         Detail : ${report.tiers.graphify.details}`);
  console.log('----------------------------------------------------------------');

  if (report.actionsTaken.length > 0) {
    console.log('• Actions Taken During Sync:');
    for (const act of report.actionsTaken) {
      console.log(`    └─ ${act}`);
    }
  } else {
    console.log('• Actions Taken During Sync: All tiers aligned, zero drift detected.');
  }
  console.log('================================================================\n');
}

// CLI Execution Entry Point
if (process.argv[1] && (process.argv[1].endsWith('aasha_memory_engine.ts') || process.argv[1].endsWith('aasha_memory_engine.js'))) {
  const report = runMemorySync();
  printMemorySyncReport(report);
  if (report.overallStatus === 'DEGRADED') {
    process.exit(1);
  }
}
