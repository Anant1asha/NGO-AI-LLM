/**
 * Graphify AST Knowledge Reader Adapter
 * Zero external npm dependencies (Node.js standard library only).
 * Directly reads graphify-out/graph.json to extract scoped architectural subgraphs.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface GraphNode {
  id?: string;
  name?: string;
  path?: string;
  type?: string;
  label?: string;
  community?: number | string;
  degree?: number;
  [key: string]: any;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation?: string;
  type?: string;
  weight?: number;
  [key: string]: any;
}

export interface GraphData {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  links?: GraphEdge[];
  [key: string]: any;
}

export class GraphifyAdapter {
  private graphPath: string;
  private graphData: GraphData | null = null;

  constructor(customPath?: string) {
    this.graphPath =
      customPath ||
      path.resolve(__dirname, '..', '..', '..', '..', 'graphify-out', 'graph.json');
    this.loadGraph();
  }

  private loadGraph(): void {
    try {
      if (fs.existsSync(this.graphPath)) {
        const raw = fs.readFileSync(this.graphPath, 'utf-8');
        this.graphData = JSON.parse(raw);
      }
    } catch (err) {
      console.warn(`[GraphifyAdapter] Failed to parse graph at ${this.graphPath}`);
    }
  }

  public isAvailable(): boolean {
    return this.graphData !== null && Array.isArray(this.getNodes());
  }

  public getNodes(): GraphNode[] {
    if (!this.graphData) return [];
    return this.graphData.nodes || (this.graphData as any).vertices || [];
  }

  public getEdges(): GraphEdge[] {
    if (!this.graphData) return [];
    return this.graphData.edges || this.graphData.links || [];
  }

  /**
   * Search for nodes matching query keywords
   */
  public query(queryStr: string, limit = 10): GraphNode[] {
    const nodes = this.getNodes();
    if (!nodes.length) return [];

    const lower = queryStr.toLowerCase();
    const matches: { node: GraphNode; score: number }[] = [];

    for (const node of nodes) {
      let score = 0;
      const name = (node.name || node.id || '').toLowerCase();
      const p = (node.path || '').toLowerCase();
      const label = (node.label || '').toLowerCase();

      if (name.includes(lower)) score += 5;
      if (p.includes(lower)) score += 3;
      if (label.includes(lower)) score += 2;

      // Token match
      const tokens = lower.split(/\s+/).filter(Boolean);
      for (const t of tokens) {
        if (name.includes(t)) score += 1;
        if (p.includes(t)) score += 1;
      }

      if (score > 0) {
        matches.push({ node, score });
      }
    }

    matches.sort((a, b) => b.score - a.score);
    return matches.slice(0, limit).map((m) => m.node);
  }

  /**
   * Extracts architectural context summary for Pāṇinian Adhikaraṇa / Karaṇa IR injection
   */
  public getArchitecturalContext(queryStr: string): {
    matchedNodes: string[];
    suggestedLayers: string[];
    subgraphSummary: string;
  } {
    const results = this.query(queryStr, 5);
    const matchedNodes = results.map((n) => n.name || n.id || n.path || 'unknown');

    const suggestedLayers = new Set<string>();
    for (const n of results) {
      const fullPath = (n.path || n.name || '').toLowerCase();
      if (fullPath.includes('layer-1') || fullPath.includes('core')) suggestedLayers.add('Layer 1 (Core Runtime)');
      if (fullPath.includes('layer-2') || fullPath.includes('education')) suggestedLayers.add('Layer 2 (Education Engine)');
      if (fullPath.includes('layer-3') || fullPath.includes('product') || fullPath.includes('pwa')) suggestedLayers.add('Layer 3 (Product UI)');
      if (fullPath.includes('layer-4') || fullPath.includes('skill') || fullPath.includes('extension')) suggestedLayers.add('Layer 4 (Extensions)');
    }

    return {
      matchedNodes,
      suggestedLayers: Array.from(suggestedLayers),
      subgraphSummary: results.length > 0
        ? `Found ${results.length} related architectural node(s) in Graphify AST: ${matchedNodes.slice(0, 3).join(', ')}`
        : 'Zero direct graph nodes matched; falling back to canonical Aasha 4-layer taxonomy',
    };
  }
}

// CLI execution check
if (process.argv[1] && process.argv[1].endsWith('graphify_adapter.ts')) {
  const adapter = new GraphifyAdapter();
  const queryArg = process.argv[2] || 'contract';
  console.log(`--- Graphify Query: "${queryArg}" ---`);
  console.log(`Available: ${adapter.isAvailable()}`);
  const ctx = adapter.getArchitecturalContext(queryArg);
  console.log(JSON.stringify(ctx, null, 2));
}
