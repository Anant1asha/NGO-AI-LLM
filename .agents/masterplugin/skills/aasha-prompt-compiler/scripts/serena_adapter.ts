/**
 * Serena Local Semantic Memory Adapter
 * Reads and manages persistent Markdown memories stored in `.serena/memories/`.
 * Zero external dependencies (Node.js standard library only).
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Project root is 4 levels up: scripts -> aasha-prompt-compiler -> skills -> .agents -> <root>
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const DEFAULT_MEMORIES_DIR = path.resolve(PROJECT_ROOT, '.serena', 'memories');

export interface SerenaMemory {
  name: string;
  filePath: string;
  content: string;
  updatedAt: Date;
}

export class SerenaLocalAdapter {
  private memoriesDir: string;

  constructor(customMemoriesDir?: string) {
    this.memoriesDir = customMemoriesDir || DEFAULT_MEMORIES_DIR;
    if (!fs.existsSync(this.memoriesDir)) {
      fs.mkdirSync(this.memoriesDir, { recursive: true });
    }
  }

  /**
   * List all available Serena memory names
   */
  public listMemories(): string[] {
    if (!fs.existsSync(this.memoriesDir)) return [];
    return fs
      .readdirSync(this.memoriesDir)
      .filter((file) => file.endsWith('.md'))
      .map((file) => file.replace(/\.md$/, ''));
  }

  /**
   * Read memory content by name
   */
  public readMemory(name: string): string | null {
    const filePath = path.join(this.memoriesDir, `${name}.md`);
    if (!fs.existsSync(filePath)) {
      return null;
    }
    return fs.readFileSync(filePath, 'utf-8');
  }

  /**
   * Write or update memory content
   */
  public writeMemory(name: string, content: string): void {
    const filePath = path.join(this.memoriesDir, `${name}.md`);
    fs.writeFileSync(filePath, content, 'utf-8');
  }

  /**
   * Build consolidated prompt context from core Serena memories
   */
  public buildContext(memoryNames: string[] = ['core', 'conventions', 'local_memory']): string {
    const sections: string[] = [];
    for (const name of memoryNames) {
      const content = this.readMemory(name);
      if (content) {
        sections.push(`### Serena Memory [${name}]\n${content.trim()}`);
      }
    }
    return sections.join('\n\n');
  }
}

// CLI usage
if (process.argv[1] && process.argv[1].endsWith('serena_adapter.ts')) {
  const adapter = new SerenaLocalAdapter();
  const memories = adapter.listMemories();
  console.log(`[Serena Adapter] Loaded ${memories.length} memories:`, memories);
  if (process.argv[2] === '--show' && process.argv[3]) {
    const content = adapter.readMemory(process.argv[3]);
    console.log(`\n--- Memory: ${process.argv[3]} ---\n`, content);
  }
}
