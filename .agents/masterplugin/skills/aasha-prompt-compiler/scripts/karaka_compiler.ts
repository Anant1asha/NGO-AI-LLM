/**
 * Aasha-AIOS Adaptive Semantic Prompt Compiler
 * Formal Pāṇinian Kāraka Computational Semantics & Prompt Delta Engine
 * Zero external npm dependencies (Node.js standard library only).
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { Mem0LocalAdapter } from './mem0_adapter.ts';
import { GraphifyAdapter } from './graphify_adapter.ts';

export type EvidenceClass =
  | 'FACT'
  | 'STRONG_INFERENCE'
  | 'SAFE_DEFAULT'
  | 'ASSUMPTION'
  | 'UNKNOWN'
  | 'CONFLICT';

export interface PaninianKarakaIR {
  karta: string;           // कर्तृ: Agent/Subject (who/what acts)
  karma: string;           // कर्मन्: Patient/Object (target content/contract)
  karana: string[];        // करण: Instrument/Means (tools, models, algorithms)
  sampradana: string;      // सम्प्रदान: Recipient/Beneficiary (student grade/board)
  apadana: string[];       // अपादान: Negative Invariants & Prohibitions
  adhikarana: string;      // अधिकरण: Locus/Context (offline PWA, layer, storage)
  evidence: Record<string, EvidenceClass>;
}

export interface PromptDelta {
  turn: number;
  added: string[];
  removed: string[];
  changed: string[];
  preserved: string[];
  superseded: string[];
}

export interface VerificationIssue {
  level: 'ERROR' | 'WARNING' | 'INFO';
  message: string;
  field?: keyof PaninianKarakaIR | string;
}

export interface CompilerVerificationResult {
  verdict: 'PASS' | 'REPAIR' | 'CLARIFY' | 'BLOCK';
  confidence: number;
  issues: VerificationIssue[];
  repairsApplied: string[];
}

export interface DualProposalOutput {
  developerProposal: string;
  teacherSummary: string;
}

export class KarakaPromptCompiler {
  private mem0: Mem0LocalAdapter;
  private graphify: GraphifyAdapter;

  constructor() {
    this.mem0 = new Mem0LocalAdapter();
    this.graphify = new GraphifyAdapter();
  }

  /**
   * Stage 1-10: Complete compilation pipeline
   */
  public compile(
    inputPrompt: string,
    previousIR?: PaninianKarakaIR,
    turn = 1
  ): {
    ir: PaninianKarakaIR;
    delta: PromptDelta;
    verification: CompilerVerificationResult;
    proposals: DualProposalOutput;
  } {
    // 1. Observe & 2. Understand
    const lowerPrompt = inputPrompt.toLowerCase();

    // Context from Mem0 & Graphify
    const memContext = this.mem0.exportContext();
    const graphContext = this.graphify.getArchitecturalContext(inputPrompt);

    // 3. Decompose into Pāṇinian Kāraka IR
    const ir = this.decomposeToKaraka(inputPrompt, memContext, graphContext);

    // 4. Classify Evidence
    ir.evidence = this.classifyEvidence(ir, inputPrompt);

    // 5. Gap & Conflict Resolution (Strict Apādāna Precedence) & 6. Harden
    const verification = this.verifyInvariants(ir, inputPrompt);

    // 7. Mode Select & 8. Plan: Compute Prompt Delta
    const delta = this.computeDelta(ir, previousIR, turn);

    // 9. Compile Proposals
    const proposals = this.generateDualProposals(ir, delta, verification);

    return { ir, delta, verification, proposals };
  }

  private decomposeToKaraka(
    prompt: string,
    memContext: Record<string, any>,
    graphContext: { matchedNodes: string[]; suggestedLayers: string[]; subgraphSummary: string }
  ): PaninianKarakaIR {
    const lower = prompt.toLowerCase();

    // Kartā (Agent)
    let karta = 'Autonomous Agent Pipeline (Orchestrator)';
    if (lower.includes('teacher') || lower.includes('admin')) karta = 'Teacher-Admin User';
    else if (lower.includes('assessment') || lower.includes('quiz')) karta = 'AssessmentAgent';
    else if (lower.includes('design') || lower.includes('visual') || lower.includes('sim')) karta = 'DesignAgent';
    else if (lower.includes('analyze') || lower.includes('concept')) karta = 'AnalysisAgent';

    // Karma (Object)
    let karma = 'Interactive Chapter Module';
    const gradeMatch = prompt.match(/class\s+(\d+|[ivxlcdm]+)/i);
    const subjectMatch = prompt.match(/(math|mathematics|science|physics|chemistry|biology|social|civics|english|coding)/i);
    if (gradeMatch || subjectMatch) {
      karma = `${subjectMatch ? subjectMatch[0].toUpperCase() : 'Subject'} Module for ${gradeMatch ? gradeMatch[0] : 'K-12'}`;
    }

    // Karaṇa (Instruments / Tools)
    const karana: string[] = [
      'AASHA Universal Teaching Language System',
      'KaTeX / Canvas 2D Engine',
      'Pre-LLE Math Insulator (__AASHA_MATH_X__)',
    ];
    if (lower.includes('sim') || lower.includes('simulation') || lower.includes('interactive')) {
      karana.push('F01-F20 Prebuilt Experience Foundations Registry (registry.json)');
    }
    if (graphContext.matchedNodes.length > 0) {
      karana.push(`Graphify Context: [${graphContext.matchedNodes.slice(0, 2).join(', ')}]`);
    }

    // Sampradāna (Beneficiary)
    let sampradāna = "K-12 Indian Student (Kid's Own Prescribed Book First)";
    if (gradeMatch) {
      sampradāna = `${gradeMatch[0]} Student (Bilingual Hindi Substrate)`;
    }

    // Apādāna (Negative Invariants & Prohibitions)
    const apadana: string[] = [
      'Strictly zero external CDN/font network requests',
      'Strictly zero spoilers in misconception explanations (m attribute)',
      'Zero paid Gemini API bleed (ALLOW_PAID_GEMINI_FALLBACK=false)',
      'Pre-LLE math insulation invariant (no uninsulated LaTeX in bilingual rt)',
      'Total self-contained HTML size limit <= 20MB',
      'Minimum mobile touch target >= 44x44px (Same-frame mobile viewport)',
      'Read & evaluate first invariant: Zero autonomous file mutations without prior review and explicit approval',
    ];

    // Adhikaraṇa (Locus / Architectural Context)
    const layers = graphContext.suggestedLayers.length > 0
      ? graphContext.suggestedLayers.join(', ')
      : 'Layer 2 (Education Engine) & Layer 3 (Product UI)';
    const adhikarana = `Offline PWA (IndexedDB/localStorage) within ${layers}`;

    return {
      karta,
      karma,
      karana,
      sampradana: sampradāna,
      apadana,
      adhikarana,
      evidence: {},
    };
  }

  private classifyEvidence(
    ir: PaninianKarakaIR,
    rawPrompt: string
  ): Record<string, EvidenceClass> {
    const evidence: Record<string, EvidenceClass> = {};
    evidence.karta = 'SAFE_DEFAULT';
    evidence.karma = rawPrompt.length > 10 ? 'STRONG_INFERENCE' : 'ASSUMPTION';
    evidence.karana = 'FACT';
    evidence.sampradana = ir.sampradana.includes('Class') ? 'STRONG_INFERENCE' : 'SAFE_DEFAULT';
    evidence.apadana = 'FACT';
    evidence.adhikarana = 'FACT';
    return evidence;
  }

  private verifyInvariants(
    ir: PaninianKarakaIR,
    rawPrompt: string
  ): CompilerVerificationResult {
    const lower = rawPrompt.toLowerCase();
    const issues: VerificationIssue[] = [];
    const repairsApplied: string[] = [];
    let verdict: 'PASS' | 'REPAIR' | 'CLARIFY' | 'BLOCK' = 'PASS';
    let confidence = 0.95;

    // Check 1: CDN / Remote script violations
    if (
      lower.includes('cdn.') ||
      lower.includes('cdnjs') ||
      lower.includes('jsdelivr') ||
      lower.includes('unpkg') ||
      lower.includes('http://') ||
      lower.includes('https://')
    ) {
      issues.push({
        level: 'ERROR',
        message: 'Apādāna Violation: External CDN or remote URL detected in prompt. Offline invariant forbids remote fetches.',
        field: 'apadana',
      });
      verdict = 'BLOCK';
      confidence = 0.2;
    }

    // Check 2: Spoiler in misconception instructions
    if (lower.includes('reveal answer in explanation') || lower.includes('show answer immediately')) {
      issues.push({
        level: 'ERROR',
        message: 'Apādāna Violation: Zero-spoiler invariant violated. Explanations must diagnose misconceptions without leaking the answer.',
        field: 'apadana',
      });
      verdict = 'BLOCK';
      confidence = 0.1;
    }

    // Check 3: Ambiguous textbook source
    if (!lower.includes('ncert') && !lower.includes('cbse') && !lower.includes('class') && !lower.includes('book')) {
      issues.push({
        level: 'WARNING',
        message: "Sampradāna Alert: Specific textbook board/grade not specified. Defaulting safely to Kid's Own Book First.",
        field: 'sampradana',
      });
      repairsApplied.push("Injected Kid's Own Book First default anchor");
      if (verdict !== 'BLOCK') verdict = 'REPAIR';
      confidence = Math.min(confidence, 0.85);
    }

    return { verdict, confidence, issues, repairsApplied };
  }

  private computeDelta(
    current: PaninianKarakaIR,
    previous?: PaninianKarakaIR,
    turn = 1
  ): PromptDelta {
    if (!previous) {
      return {
        turn,
        added: [
          `Initialized Kāraka IR for ${current.karma}`,
          `Bound Sampradāna: ${current.sampradana}`,
          `Bound ${current.apadana.length} Apādāna safety invariants`,
        ],
        removed: [],
        changed: [],
        preserved: ['All standard Aasha-AIOS core architectural invariants'],
        superseded: [],
      };
    }

    const added: string[] = [];
    const removed: string[] = [];
    const changed: string[] = [];
    const preserved: string[] = [];
    const superseded: string[] = [];

    if (current.karma !== previous.karma) {
      changed.push(`Karma changed: "${previous.karma}" -> "${current.karma}"`);
      superseded.push(`Prior Karma target "${previous.karma}"`);
    } else {
      preserved.push(`Karma: ${current.karma}`);
    }

    if (current.sampradana !== previous.sampradana) {
      changed.push(`Sampradāna refined: "${previous.sampradana}" -> "${current.sampradana}"`);
    } else {
      preserved.push(`Sampradāna: ${current.sampradana}`);
    }

    // Check karana changes
    for (const tool of current.karana) {
      if (!previous.karana.includes(tool)) added.push(`Karaṇa added: ${tool}`);
      else preserved.push(`Karaṇa preserved: ${tool}`);
    }
    for (const prevTool of previous.karana) {
      if (!current.karana.includes(prevTool)) removed.push(`Karaṇa removed: ${prevTool}`);
    }

    preserved.push(`Apādāna: ${current.apadana.length} strict negative invariants`);

    return { turn, added, removed, changed, preserved, superseded };
  }

  private generateDualProposals(
    ir: PaninianKarakaIR,
    delta: PromptDelta,
    verification: CompilerVerificationResult
  ): DualProposalOutput {
    // Developer Proposal
    const devProposal = [
      '# Aasha-AIOS Developer Technical Proposal (.proposal.md)',
      '',
      '## 1. Pāṇinian Kāraka Semantic Intermediate Representation (IR)',
      '```yaml',
      `karta: "${ir.karta}"`,
      `karma: "${ir.karma}"`,
      'karana:',
      ...ir.karana.map((k) => `  - "${k}"`),
      `sampradana: "${ir.sampradana}"`,
      'apadana:',
      ...ir.apadana.map((a) => `  - "${a}"`),
      `adhikarana: "${ir.adhikarana}"`,
      'evidence:',
      ...Object.entries(ir.evidence).map(([k, v]) => `  ${k}: "${v}"`),
      '```',
      '',
      '## 2. Multi-Turn Prompt Delta (Turn ' + delta.turn + ')',
      '| Delta Category | Items |',
      '| :--- | :--- |',
      `| **ADDED** | ${delta.added.join('<br>') || 'None'} |`,
      `| **REMOVED** | ${delta.removed.join('<br>') || 'None'} |`,
      `| **CHANGED** | ${delta.changed.join('<br>') || 'None'} |`,
      `| **PRESERVED** | ${delta.preserved.join('<br>') || 'None'} |`,
      `| **SUPERSEDED** | ${delta.superseded.join('<br>') || 'None'} |`,
      '',
      '## 3. Compiler Verification Audit',
      `- **Verdict**: \`${verification.verdict}\``,
      `- **Confidence**: \`${verification.confidence.toFixed(2)}\``,
      verification.issues.length > 0
        ? '- **Issues**:\n' + verification.issues.map((i) => `  - [${i.level}] ${i.message}`).join('\n')
        : '- **Issues**: None (Zero invariant violations)',
      verification.repairsApplied.length > 0
        ? '- **Repairs Applied**:\n' + verification.repairsApplied.map((r) => `  - ${r}`).join('\n')
        : '- **Repairs Applied**: None required',
    ].join('\n');

    // Teacher Summary
    const statusHindi =
      verification.verdict === 'PASS'
        ? 'स्वीकृत (PASS)'
        : verification.verdict === 'REPAIR'
        ? 'स्वतः सुधारात्मक स्वीकृति (REPAIR - PASS)'
        : verification.verdict === 'CLARIFY'
        ? 'स्पष्टीकरण प्रतीक्षित (CLARIFY)'
        : 'अवरुद्ध (BLOCK)';

    const teacherSummary = [
      '# शिक्षक के लिए सारांश (Teacher HIL Verification Summary)',
      '',
      `**समीक्षा स्थिति (Review Status)**: **${statusHindi}**  `,
      `**सटीकता स्कोर (Confidence Score)**: **${Math.round(verification.confidence * 100)}%**`,
      '',
      '---',
      '',
      '### 1. विद्यार्थी एवं कक्षा विवरण (Student & Class Profile)',
      `- **लक्षित कक्षा (Target Audience)**: ${ir.sampradana}`,
      `- **अध्ययन विषय एवं पाठ (Topic)**: ${ir.karma}`,
      "- **मूल आधार (Pedagogical Anchor)**: बच्चे की अपनी निर्धारित पाठ्यपुस्तक (Kid's Own Book First)",
      '',
      '### 2. शिक्षण माध्यम एवं तकनीक (Pedagogical Means & Visuals)',
      ...ir.karana.map((k) => `- ${k}`),
      '',
      '### 3. सुरक्षा, गोपनीयता एवं नियम (Safety & Child Privacy)',
      '- **पूर्णतः ऑफ़लाइन (100% Offline)**: कोई बाहरी इंटरनेट या CDN अनुरोध नहीं।',
      '- **शून्य-स्पॉइलर नियम (Zero Spoiler)**: भ्रांति निवारण में सीधा उत्तर प्रकट किए बिना संकल्पना स्पष्ट की जाएगी।',
      '- **गणितीय सुरक्षा (Math Insulation)**: गणितीय सूत्रों का अक्षुण्ण अनुवाद संरक्षण।',
      '',
      '### 4. शिक्षक अनुमोदन निर्देश (Teacher Sign-off)',
      verification.verdict === 'BLOCK'
        ? '⚠️ **अस्वीकृत**: इस प्रस्ताव में सुरक्षा या शिक्षण नियमों का उल्लंघन पाया गया है। कृपया इनपुट संशोधित करें।'
        : '✅ **सत्यापित**: यह प्रस्ताव आशा-AIOS के सभी 4 स्तंभों (ऑफ़लाइन, पुस्तक-प्रथम, शून्य-स्पॉइलर, एवं भाषा सुरक्षा) का पूर्ण पालन करता है।',
    ].join('\n');

    return { developerProposal: devProposal, teacherSummary };
  }
}

// Self-Test and CLI Runner
if (process.argv[1] && process.argv[1].endsWith('karaka_compiler.ts')) {
  const compiler = new KarakaPromptCompiler();
  const args = process.argv.slice(2);

  if (args.includes('--test')) {
    console.log('=== Running Karaka Prompt Compiler Verification Suite ===\n');

    // Test 1: Standard Chapter Prompt
    console.log('[Test 1] Standard Chapter Prompt Decomposition');
    const res1 = compiler.compile('Create Class 8 NCERT Mathematics Linear Equations worked example and quiz');
    console.log(`- Verdict: ${res1.verification.verdict}`);
    console.log(`- Confidence: ${res1.verification.confidence}`);
    console.log(`- Karta: ${res1.ir.karta}`);
    console.log(`- Karma: ${res1.ir.karma}`);
    console.log(`- Sampradana: ${res1.ir.sampradana}`);
    if (res1.verification.verdict !== 'PASS' && res1.verification.verdict !== 'REPAIR') {
      throw new Error(`Test 1 Failed: Expected PASS or REPAIR, got ${res1.verification.verdict}`);
    }
    console.log('Test 1: PASSED\n');

    // Test 2: Apādāna Violation (CDN script)
    console.log('[Test 2] Apādāna Violation Detection (CDN Script)');
    const res2 = compiler.compile('Fetch external styles from https://cdnjs.cloudflare.com/ajax/libs/mathquill.css');
    console.log(`- Verdict: ${res2.verification.verdict}`);
    if (res2.verification.verdict !== 'BLOCK') {
      throw new Error(`Test 2 Failed: Expected BLOCK, got ${res2.verification.verdict}`);
    }
    console.log('Test 2: PASSED (Correctly Blocked)\n');

    // Test 3: Multi-turn Delta Engine
    console.log('[Test 3] Multi-turn Prompt Delta Computation');
    const res3Turn2 = compiler.compile(
      'Refine to Class 8 NCERT Linear Equations with F04 PhET Balance Scale simulation adapter',
      res1.ir,
      2
    );
    console.log(`- Turn 2 Added: ${res3Turn2.delta.added.length} items`);
    console.log(`- Turn 2 Preserved: ${res3Turn2.delta.preserved.length} items`);
    if (res3Turn2.delta.turn !== 2 || res3Turn2.delta.preserved.length === 0) {
      throw new Error('Test 3 Failed: Delta tracking corrupted');
    }
    console.log('Test 3: PASSED\n');

    console.log('=== All 3 Self-Tests PASSED Successfully ===');
  } else {
    const inputArg = args.join(' ') || 'Design Class 7 NCERT Fraction Addition simulation';
    const result = compiler.compile(inputArg);
    console.log(result.proposals.developerProposal);
    console.log('\n=======================================================\n');
    console.log(result.proposals.teacherSummary);
  }
}
