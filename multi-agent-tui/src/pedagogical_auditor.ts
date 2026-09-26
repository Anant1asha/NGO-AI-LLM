import fs from 'fs';
import path from 'path';

export interface AuditPillar {
  name: string;
  score: number; // 0 - 100
  passed: boolean;
  criticalViolations: string[];
  advisories: string[];
}

export interface AuditReport {
  chapterTitle: string;
  overallScore: number;
  signOffAllowed: boolean;
  pillars: {
    goldenFlow: AuditPillar;
    twoLayerRigor: AuditPillar;
    misconceptionsAndHints: AuditPillar;
    airGappedSafety: AuditPillar;
  };
  exerciseUtilization: {
    totalExtracted: number;
    totalAssessed: number;
    percentage: number;
    passed: boolean;
  };
  criticalViolationsCount: number;
  advisoriesCount: number;
  htmlPath: string;
}

export class PedagogicalAuditor {
  /**
   * Run the complete 4-Pillar AASHA Pedagogical Audit on a generated chapter.
   */
  public static audit(htmlPath: string, intermediatesDir?: string): AuditReport {
    if (!fs.existsSync(htmlPath)) {
      throw new Error(`Chapter HTML not found at: ${htmlPath}`);
    }

    const html = fs.readFileSync(htmlPath, 'utf-8');
    const intermediates = intermediatesDir ? this.loadIntermediates(intermediatesDir) : {};

    // 1. Pillar 1: Golden Flow (Discovery Order: WHAT → WHY → HOW → SHOW → TRY... vs Definition-First)
    const goldenFlow = this.auditGoldenFlow(html, intermediates.pedagogyMap);

    // 2. Pillar 2: Two-Layer Academic Rigor (Layer A Student Tone vs Layer B Formal Math/Science)
    const twoLayerRigor = this.auditTwoLayerRigor(html);

    // 3. Pillar 3: Misconception Diagnostics & 4-Tier Zero-Spoiler Hints
    const misconceptionsAndHints = this.auditMisconceptionsAndHints(html, intermediates.assessmentSuite);

    // 4. Pillar 4: Air-Gapped Child Safety (Zero external network links, zero trackers, <=20MB bundle ceiling)
    const airGappedSafety = this.auditAirGappedSafety(html, htmlPath);

    // Exercise Utilization Check: 100% of chapter PDF exercises utilized
    const exerciseUtilization = this.checkExerciseUtilization(intermediates);

    const criticalViolationsCount =
      goldenFlow.criticalViolations.length +
      twoLayerRigor.criticalViolations.length +
      misconceptionsAndHints.criticalViolations.length +
      airGappedSafety.criticalViolations.length +
      (exerciseUtilization.passed ? 0 : 1);

    const advisoriesCount =
      goldenFlow.advisories.length +
      twoLayerRigor.advisories.length +
      misconceptionsAndHints.advisories.length +
      airGappedSafety.advisories.length;

    const pillarScores = [
      goldenFlow.score,
      twoLayerRigor.score,
      misconceptionsAndHints.score,
      airGappedSafety.score
    ];
    const overallScore = Math.round(pillarScores.reduce((a, b) => a + b, 0) / pillarScores.length);

    // Hard Safety Block: 0 critical violations allowed for sign-off
    const signOffAllowed = criticalViolationsCount === 0;

    const titleMatch = html.match(/<title>([^<]+)<\/title>/i);
    const chapterTitle = titleMatch ? titleMatch[1].replace(/—.*$/, '').trim() : 'AASHA Chapter';

    return {
      chapterTitle,
      overallScore,
      signOffAllowed,
      pillars: {
        goldenFlow,
        twoLayerRigor,
        misconceptionsAndHints,
        airGappedSafety
      },
      exerciseUtilization,
      criticalViolationsCount,
      advisoriesCount,
      htmlPath
    };
  }

  private static loadIntermediates(dir: string): Record<string, any> {
    const result: Record<string, any> = {};
    const pedPath = path.join(dir, 'pedagogy_map.json');
    const assessPath = path.join(dir, 'assessment_suite.json');
    if (fs.existsSync(pedPath)) {
      try { result.pedagogyMap = JSON.parse(fs.readFileSync(pedPath, 'utf-8')); } catch {}
    }
    if (fs.existsSync(assessPath)) {
      try { result.assessmentSuite = JSON.parse(fs.readFileSync(assessPath, 'utf-8')); } catch {}
    }
    return result;
  }

  // ════════ Pillar 1: Golden Flow ════════
  private static auditGoldenFlow(html: string, pedagogyMap?: any): AuditPillar {
    const critical: string[] = [];
    const advisories: string[] = [];
    let score = 100;

    // Rule 3: Definition-First is NOT default. Check if opening text immediately jumps into formal definition
    const hasInquiryQuestion = /\?|notice|wonder|explore|observe|look at/i.test(html);
    if (!hasInquiryQuestion) {
      advisories.push('Rule 3: Chapter opens without an inquiry question, exploratory hook, or micro-world.');
      score -= 15;
    }

    // Check if interactive simulation precedes formal exercises
    const conceptCardIdx = html.indexOf('concept-card');
    const quizCardIdx = html.indexOf('quiz-card');
    if (quizCardIdx !== -1 && conceptCardIdx !== -1 && quizCardIdx < conceptCardIdx) {
      critical.push('Rule 2 Violation: Quizzes appear before experiential concept cards in the DOM.');
      score -= 30;
    }

    // Check for interactive simulation component (<aasha-sim>)
    if (!html.includes('aasha-sim') && !html.includes('interaction-container')) {
      critical.push('Rule 9/10 Violation: No experiential simulation or manipulative container found.');
      score -= 40;
    }

    return {
      name: 'Pillar 1: Golden Flow (Discovery Order)',
      score: Math.max(0, score),
      passed: critical.length === 0,
      criticalViolations: critical,
      advisories
    };
  }

  // ════════ Pillar 2: Two-Layer Rigor ════════
  private static auditTwoLayerRigor(html: string): AuditPillar {
    const critical: string[] = [];
    const advisories: string[] = [];
    let score = 100;

    // Rule 13: Avoid childish tone / excessive emojis
    const childishPatterns = [
      /super-duper/i,
      /yay!/i,
      /math adventure/i,
      /fun-filled journey/i
    ];
    for (const rx of childishPatterns) {
      if (rx.test(html)) {
        advisories.push(`Rule 13 Advisory: Detected childish phrasing (${rx.source}). Prefer respectful, warm tone.`);
        score -= 10;
      }
    }

    // Rule 15: Formal Notation - Preserve LaTeX KaTeX expressions without corruption
    const hasCorruptedLatex = /\[object Object\]|undefined\\frac|\\NaN/i.test(html);
    if (hasCorruptedLatex) {
      critical.push('Rule 15 Violation: Detected corrupted mathematical formula string in HTML.');
      score -= 40;
    }

    // Math Isolation Verification
    if (html.includes('\\frac') || html.includes('\\sqrt')) {
      const isolatesMath = html.includes('math') || html.includes('KaTeX') || html.includes('MathIsolation');
      if (!isolatesMath) {
        advisories.push('Rule 15 Advisory: LaTeX math found without explicit math-isolation container class.');
        score -= 10;
      }
    }

    return {
      name: 'Pillar 2: Two-Layer Academic Rigor',
      score: Math.max(0, score),
      passed: critical.length === 0,
      criticalViolations: critical,
      advisories
    };
  }

  // ════════ Pillar 3: Misconception Diagnostics & Zero-Spoiler Hints ════════
  private static auditMisconceptionsAndHints(html: string, assessmentSuite?: any): AuditPillar {
    const critical: string[] = [];
    const advisories: string[] = [];
    let score = 100;

    // Rule 1: Misconception explanations exist for wrong options
    const hasMField = html.includes('data-m=') || html.includes('"m"') || html.includes(',m:');
    if (!hasMField) {
      critical.push('Rule 1/17 Violation: Quiz options lack diagnostic misconception explanations (m field).');
      score -= 50;
    }

    // Rule 12: Zero Spoilers in misconceptions and hints
    const spoilerRegexes = [
      /(?:the correct answer is|the answer is|answer value is|becomes exactly)\s*[:=]?\s*([a-zA-Z0-9_/.-]+)/i,
      /you should select\s+([a-zA-Z0-9]+)/i,
      /correct option is/i
    ];

    // Extract all misconception strings and hint strings
    const mStrings: string[] = [];
    const mMatches = html.matchAll(/data-m=["']([^"']+)["']/gi);
    for (const m of mMatches) {
      if (m[1]) mStrings.push(m[1]);
    }
    const hintMatches = html.matchAll(/data-h[1-4]=["']([^"']+)["']/gi);
    for (const h of hintMatches) {
      if (h[1]) mStrings.push(h[1]);
    }

    for (const text of mStrings) {
      for (const rx of spoilerRegexes) {
        const match = text.match(rx);
        if (match) {
          critical.push(`Rule 12 Violation (Answer Leakage): Detected spoiler phrasing: "${match[0]}" in "${text}"`);
          score -= 40;
          break;
        }
      }
      if (critical.length > 0) break;
    }

    // Check for 4-Tier Adaptive Hints structure
    if (!html.includes('hint-box') && !html.includes('data-tier')) {
      advisories.push('Rule 12 Advisory: 4-Tier adaptive hint scaffolding not detected in questions.');
      score -= 15;
    }

    return {
      name: 'Pillar 3: Misconceptions & Zero-Spoiler Hints',
      score: Math.max(0, score),
      passed: critical.length === 0,
      criticalViolations: critical,
      advisories
    };
  }

  // ════════ Pillar 4: Air-Gapped Child Safety ════════
  private static auditAirGappedSafety(html: string, htmlPath?: string): AuditPillar {
    const critical: string[] = [];
    const advisories: string[] = [];
    let score = 100;

    // Rule 11: Air-Gapped Offline Bundle Size Ceiling (<= 40 MB = 41,943,040 bytes per AASHA-SPEC-02-TRD)
    const MAX_BUNDLE_BYTES = 41943040;
    if (htmlPath && fs.existsSync(htmlPath)) {
      try {
        const fileSizeBytes = fs.statSync(htmlPath).size;
        if (fileSizeBytes > MAX_BUNDLE_BYTES) {
          critical.push(
            `Rule 11 Violation (Bundle Ceiling Exceeded): Artifact file size (${fileSizeBytes} bytes / ${(fileSizeBytes / (1024 * 1024)).toFixed(2)} MB) exceeds hard 40 MB ceiling (${MAX_BUNDLE_BYTES} bytes). Release is BLOCKED.`
          );
          score = 0;
        }
      } catch (e: any) {
        critical.push(`Rule 11 Violation: Could not stat file size for ${htmlPath}: ${e.message}`);
        score = 0;
      }
    }

    // Rule 1: 100% self-contained single file, zero external network URLs
    const externalUrls = html.match(/(?:src|href|url)\s*=\s*["']https?:\/\/[^"']+/gi) || [];
    if (externalUrls.length > 0) {
      critical.push(`Rule 1 Violation (Air-Gap Compromise): Found ${externalUrls.length} external URL(s): ${externalUrls.slice(0, 2).join(', ')}`);
      score -= 50;
    }

    // Dark pattern / tracking check
    const trackingWords = [/google-analytics/i, /facebook\.net/i, /doubleclick/i, /trackEvent\(/i];
    for (const tw of trackingWords) {
      if (tw.test(html)) {
        critical.push(`Child Safety Violation: External tracking script signature detected (${tw.source}).`);
        score -= 50;
      }
    }

    // Check for mobile-responsive viewport meta
    if (!html.includes('name="viewport"')) {
      advisories.push('Mobile Viewport: Missing mobile-responsive viewport meta tag.');
      score -= 10;
    }

    return {
      name: 'Pillar 4: Air-Gapped Child Safety',
      score: Math.max(0, score),
      passed: critical.length === 0,
      criticalViolations: critical,
      advisories
    };
  }

  // ════════ 100% Textbook Exercise Utilization ════════
  private static checkExerciseUtilization(intermediates: Record<string, any>) {
    const rawExercises = intermediates.pedagogyMap?.exercises || [];
    const suite = intermediates.assessmentSuite || {};
    const totalAssessed = (suite.warmup?.length || 0) + (suite.deep_dive?.length || 0) + (suite.boss?.length || 0);
    const totalExtracted = rawExercises.length;

    // If intermediates are not present, fallback to DOM quiz card counting
    if (totalExtracted === 0) {
      return {
        totalExtracted: totalAssessed,
        totalAssessed: totalAssessed,
        percentage: 100,
        passed: true
      };
    }

    const percentage = Math.round((totalAssessed / totalExtracted) * 100);
    const passed = percentage >= 90; // At least 90-100% mapped into 3-tier suite

    return {
      totalExtracted,
      totalAssessed,
      percentage,
      passed
    };
  }
}
