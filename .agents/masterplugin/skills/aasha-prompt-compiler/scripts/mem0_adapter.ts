/**
 * Mem0 Local Offline Preference & Memory Adapter
 * Scopes: Global, Domain, Project, Task
 * Precedence: Task > Project > Domain > Global
 * Zero external npm dependencies (Node.js standard library only).
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export type MemoryScope = 'Global' | 'Domain' | 'Project' | 'Task';

export interface MemoryRecord {
  id: string;
  scope: MemoryScope;
  key: string;
  value: any;
  context?: string;
  updatedAt: string;
}

export interface MemoryStore {
  version: string;
  records: MemoryRecord[];
}

const DEFAULT_STORE_PATH = path.resolve(
  __dirname,
  '..',
  '.cache',
  'mem0_store.json'
);

export class Mem0LocalAdapter {
  private filePath: string;
  private store: MemoryStore;

  constructor(customPath?: string) {
    this.filePath = customPath || DEFAULT_STORE_PATH;
    this.store = this.loadStore();
  }

  private loadStore(): MemoryStore {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf-8');
        return JSON.parse(raw);
      }
    } catch {
      // Fallback on read error
    }
    return {
      version: '1.0.0',
      records: [
        {
          id: 'def-global-1',
          scope: 'Global',
          key: 'offline_constraint',
          value: 'Strictly zero remote CDN calls; self-contained files under 20MB',
          updatedAt: new Date().toISOString(),
        },
        {
          id: 'def-global-2',
          scope: 'Global',
          key: 'pedagogy_anchor',
          value: "Authoritative derivation from Kid's Own Prescribed Book first",
          updatedAt: new Date().toISOString(),
        },
        {
          id: 'def-domain-1',
          scope: 'Domain',
          key: 'vernacular_substrate',
          value: 'Hindi primary focus with pre-LLE LaTeX math insulation',
          updatedAt: new Date().toISOString(),
        },
        {
          id: 'def-domain-2',
          scope: 'Domain',
          key: 'assessment_rule',
          value: 'Zero-spoiler misconception explanations in m attribute',
          updatedAt: new Date().toISOString(),
        },
      ],
    };
  }

  private saveStore(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.filePath, JSON.stringify(this.store, null, 2), 'utf-8');
  }

  public set(scope: MemoryScope, key: string, value: any, context?: string): MemoryRecord {
    const existingIdx = this.store.records.findIndex(
      (r) => r.scope === scope && r.key === key
    );
    const record: MemoryRecord = {
      id: `${scope.toLowerCase()}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      scope,
      key,
      value,
      context,
      updatedAt: new Date().toISOString(),
    };

    if (existingIdx >= 0) {
      this.store.records[existingIdx] = record;
    } else {
      this.store.records.push(record);
    }
    this.saveStore();
    return record;
  }

  /**
   * Resolves effective preference honoring Task > Project > Domain > Global precedence
   */
  public resolveEffective(key: string, taskName?: string, projectName?: string): any {
    const records = this.store.records.filter((r) => r.key === key);
    if (records.length === 0) return undefined;

    const taskMatch = taskName
      ? records.find((r) => r.scope === 'Task' && r.context === taskName)
      : records.find((r) => r.scope === 'Task');
    if (taskMatch) return taskMatch.value;

    const projectMatch = projectName
      ? records.find((r) => r.scope === 'Project' && r.context === projectName)
      : records.find((r) => r.scope === 'Project');
    if (projectMatch) return projectMatch.value;

    const domainMatch = records.find((r) => r.scope === 'Domain');
    if (domainMatch) return domainMatch.value;

    const globalMatch = records.find((r) => r.scope === 'Global');
    return globalMatch?.value;
  }

  public list(): MemoryRecord[] {
    return this.store.records;
  }

  public exportContext(): Record<string, any> {
    const result: Record<string, any> = {};
    // Sort by ascending precedence so higher precedence overrides lower
    const precedence: MemoryScope[] = ['Global', 'Domain', 'Project', 'Task'];
    for (const scope of precedence) {
      const scopedRecords = this.store.records.filter((r) => r.scope === scope);
      for (const rec of scopedRecords) {
        result[rec.key] = rec.value;
      }
    }
    return result;
  }
}

// CLI execution check
if (process.argv[1] && process.argv[1].endsWith('mem0_adapter.ts')) {
  const adapter = new Mem0LocalAdapter();
  const args = process.argv.slice(2);
  if (args.includes('--list')) {
    console.log('--- Active Mem0 Scoped Records ---');
    console.log(JSON.stringify(adapter.list(), null, 2));
  } else if (args.includes('--effective')) {
    console.log('--- Effective Combined Context ---');
    console.log(JSON.stringify(adapter.exportContext(), null, 2));
  } else {
    console.log('Usage: node mem0_adapter.ts [--list | --effective]');
  }
}
