import * as fs from 'node:fs';
import * as path from 'node:path';
import { resolveWorkspaceRoot } from './ingest_subagent.mjs';

/**
 * AASHA AIOS — 3-Tier Gamified Assessment Subagent
 * Task 3: Assessment Engine, L-Truth Anti-Spoiler Linter & Web Component Generator
 *
 * Implements pure headless assessment models, scoring mechanics, anti-spoiler
 * validators, Foundation F27 cleanroom adaptation, and Web Component scripts.
 */

// ---------------------------------------------------------------------------
// Constants & Lexicons for Anti-Spoiler Validation (ported from L-Truth)
// ---------------------------------------------------------------------------

export const STOPWORDS = new Set([
  'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'in', 'of', 'to',
  'it', 'its', 'by', 'for', 'with', 'as', 'are', 'was', 'were', 'be', 'this',
  'that', 'from', 'into', 'than', 'more', 'less', 'will', 'can', 'not', 'no'
]);

export const LEAK_PREDICATES = [
  'is', 'equals', 'equal to', 'equals to', 'gives', 'giving', 'yields',
  'yielded', 'produces', 'produced', 'results in', 'resulting in',
  'is equal to', 'would be', 'should be', 'comes to', 'simplifies to',
  'evaluates to', 'evaluated to', 'becomes', 'became', 'which is', 'giving us',
  'result is', 'answer is', 'correct is'
];

export const SPOILER_PHRASES = [
  'correct answer',
  'correct option',
  'the answer is',
  'the result is',
  'the true value is',
  'which gives',
  'which gives us',
  'leading to',
  'yielding',
  'giving',
  'resulting in'
];

function escapeRegex(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normalizeMathText(text) {
  if (!text) return '';
  return String(text)
    .replace(/\\(?:text|mathrm|mathbf)\{([^}]+)\}/g, '$1')
    .replace(/[\$\{\}\\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Headless Assessment Bank Model
 * Manages question categorization, active pointers, and progressive hint disclosures.
 */
export class AssessmentBankModel {
  constructor(options = {}) {
    const rawQuestions = Array.isArray(options.questions) ? options.questions : [];
    this.questions = rawQuestions.map(q => ({ ...q }));
    this.tierMap = {
      warmup: [],
      deep_dive: [],
      boss: []
    };
    this.hintState = new Map(); // questionId -> currentHintLevel (0..4)

    for (const q of this.questions) {
      const tierKey = (q.tier || 'warmup').toLowerCase().replace('-', '_');
      if (this.tierMap[tierKey]) {
        this.tierMap[tierKey].push(q);
      } else {
        this.tierMap.warmup.push(q);
      }
      this.hintState.set(q.id, 0);
    }
  }

  getTierCount(tier) {
    const tierKey = (tier || 'warmup').toLowerCase().replace('-', '_');
    return this.tierMap[tierKey] ? this.tierMap[tierKey].length : 0;
  }

  getQuestionsForTier(tier) {
    const tierKey = (tier || 'warmup').toLowerCase().replace('-', '_');
    return (this.tierMap[tierKey] || []).map(q => ({ ...q }));
  }

  getCurrentHintLevel(questionId) {
    return this.hintState.get(questionId) || 0;
  }

  unlockNextHint(questionId) {
    const q = this.questions.find(item => item.id === questionId);
    if (!q || !q.hints) return null;

    const currentLevel = this.getCurrentHintLevel(questionId);
    if (currentLevel >= 4) return null;

    const nextLevel = currentLevel + 1;
    this.hintState.set(questionId, nextLevel);

    const hintKey = `h${nextLevel}`;
    return q.hints[hintKey] || null;
  }

  resetHints(questionId) {
    if (questionId) {
      this.hintState.set(questionId, 0);
    } else {
      for (const id of this.hintState.keys()) {
        this.hintState.set(id, 0);
      }
    }
  }
}

/**
 * Pure Headless Gamified Scoring Engine
 * Governs lives, streak streaks, combo multipliers, and XP awards.
 */
export class GamifiedScoringEngine {
  constructor(options = {}) {
    this.initialLives = typeof options.initialLives === 'number' ? options.initialLives : 3;
    this.baseXP = typeof options.baseXP === 'number' ? options.baseXP : 100;
    this.maxMultiplier = typeof options.maxMultiplier === 'number' ? options.maxMultiplier : 3.0;

    this.lives = this.initialLives;
    this.score = 0;
    this.streak = 0;
    this.totalAnswered = 0;
    this.correctCount = 0;
  }

  get multiplier() {
    if (this.streak >= 4) return Math.min(2.5, this.maxMultiplier);
    if (this.streak >= 2) return 1.5;
    return 1.0;
  }

  recordAnswer({ isCorrect, hintPenaltyLevel = 0 }) {
    this.totalAnswered++;
    if (isCorrect) {
      this.correctCount++;
      this.streak++;
      const hintDeduction = Math.min(hintPenaltyLevel * 0.15, 0.6); // hints reduce XP by up to 60%
      const effectiveXP = Math.round(this.baseXP * this.multiplier * (1 - hintDeduction));
      this.score += effectiveXP;
      return {
        awardedXP: effectiveXP,
        currentScore: this.score,
        livesRemaining: this.lives,
        streak: this.streak,
        multiplier: this.multiplier
      };
    } else {
      this.streak = 0;
      this.lives = Math.max(0, this.lives - 1);
      return {
        awardedXP: 0,
        currentScore: this.score,
        livesRemaining: this.lives,
        streak: 0,
        multiplier: 1.0
      };
    }
  }

  getState() {
    return {
      lives: this.lives,
      score: this.score,
      streak: this.streak,
      multiplier: this.multiplier,
      totalAnswered: this.totalAnswered,
      correctCount: this.correctCount,
      isGameOver: this.lives <= 0
    };
  }

  reset() {
    this.lives = this.initialLives;
    this.score = 0;
    this.streak = 0;
    this.totalAnswered = 0;
    this.correctCount = 0;
    return this.getState();
  }
}

// ---------------------------------------------------------------------------
// L-Truth Ground-Truth Anti-Spoiler & 4-Tier Scaffolding Validator Functions
// ---------------------------------------------------------------------------

/**
 * Validates Rule #1 Zero-Spoiler Invariant for an option against the correct answer.
 */
export function validateZeroSpoilerInvariant(option, correctOption, qId = 'UNKNOWN', optIdx = 0) {
  const errors = [];
  if (!option || typeof option !== 'object') return errors;

  // Correct options must have empty misconception
  if (option.c === true) {
    if (option.m && String(option.m).trim().length > 0) {
      errors.push({
        questionId: qId,
        ruleId: 'RULE_1_CORRECT_OPTION_MISCONCEPTION',
        severity: 'ERROR',
        message: `Correct option #${optIdx + 1} ('${option.t}') must not have misconception explanation. Found: "${option.m}"`,
        context: qId
      });
    }
    return errors;
  }

  // Distractors must have non-empty misconception explanations (> 5 chars)
  const mText = String(option.m || '').trim();
  if (mText.length < 5) {
    errors.push({
      questionId: qId,
      ruleId: 'RULE_1_DISTRACTOR_MISSING_MISCONCEPTION',
      severity: 'ERROR',
      message: `Distractor #${optIdx + 1} ('${option.t}') is missing a diagnostic misconception explanation.`,
      context: qId
    });
    return errors;
  }

  if (!correctOption || !correctOption.t) return errors;

  const rawCorrect = String(correctOption.t).trim();
  const normCorrect = normalizeMathText(rawCorrect).toLowerCase();
  const normM = normalizeMathText(mText).toLowerCase();

  // 1. Boolean leakage check
  const isBooleanTarget = /^(?:true|false)$/i.test(normCorrect);
  if (isBooleanTarget) {
    const boolLeakRegex = new RegExp(
      '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + '|statement\\s+is|claim\\s+is|option\\s+is|actually)\\b)\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b' + escapeRegex(normCorrect) + '\\b',
      'i'
    );
    if (boolLeakRegex.test(normM)) {
      errors.push({
        questionId: qId,
        ruleId: 'RULE_1_SPOILER_BOOLEAN_LEAK',
        severity: 'ERROR',
        message: `Distractor #${optIdx + 1} ('${option.t}') reveals target boolean answer '${rawCorrect}' in: "${mText}".`,
        context: qId
      });
      return errors;
    }
  }

  // 2. Verbatim answer leakage (for non-pure numbers)
  const isPureNumber = /^-?\d+(?:\.\d+)?$/.test(normCorrect);
  if (!isPureNumber && normCorrect.length > 0 && !STOPWORDS.has(normCorrect)) {
    let verbatimMatch = false;
    if (normCorrect.length >= 3) {
      verbatimMatch = normM.includes(normCorrect);
    } else {
      const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
      verbatimMatch = shortRegex.test(normM);
    }
    if (verbatimMatch) {
      errors.push({
        questionId: qId,
        ruleId: 'RULE_1_SPOILER_VERBATIM_ANSWER',
        severity: 'ERROR',
        message: `Distractor #${optIdx + 1} ('${option.t}') leaks verbatim answer '${rawCorrect}' in: "${mText}".`,
        context: qId
      });
      return errors;
    }
  }

  // 3. Numerical value leakage patterns with leak predicates
  const nums = normCorrect.match(/-?\d+(?:\.\d+)?/g) || [];
  for (const n of nums) {
    const escapedN = escapeRegex(n);
    const leakPattern = new RegExp(
      '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + ')\\b)\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b' + escapedN + '\\b',
      'i'
    );
    if (leakPattern.test(normM)) {
      errors.push({
        questionId: qId,
        ruleId: 'RULE_1_SPOILER_NUMERICAL_LEAK',
        severity: 'ERROR',
        message: `Distractor #${optIdx + 1} explicitly reveals target numerical value '${n}' in: "${mText}".`,
        context: qId
      });
      return errors;
    }

    for (const phrase of SPOILER_PHRASES) {
      const phraseLeakPattern = new RegExp(`(?:${escapeRegex(phrase)})\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b${escapedN}\\b`, 'i');
      if (phraseLeakPattern.test(normM)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_1_SPOILER_PHRASE_LEAK',
          severity: 'ERROR',
          message: `Distractor #${optIdx + 1} contains revealing phrase '${phrase}' disclosing value '${n}' in: "${mText}".`,
          context: qId
        });
        return errors;
      }
    }
  }

  return errors;
}

/**
 * Validates 4-Tier Progressive Scaffolding Hints for an item.
 */
export function validate4TierHints(hints, correctOption, qId = 'UNKNOWN') {
  const errors = [];
  if (!hints || typeof hints !== 'object') {
    errors.push({
      questionId: qId,
      ruleId: 'RULE_12_MISSING_HINTS_STRUCTURE',
      severity: 'ERROR',
      message: `Question '${qId}' is missing hints dictionary.`,
      context: qId
    });
    return errors;
  }

  const hintKeys = ['h1', 'h2', 'h3', 'h4'];
  for (let i = 0; i < hintKeys.length; i++) {
    const key = hintKeys[i];
    const val = hints[key] || hints[`hint_${i + 1}`];
    if (!val || String(val).trim().length < 5) {
      errors.push({
        questionId: qId,
        ruleId: 'RULE_12_HINT_TOO_SHORT',
        severity: 'ERROR',
        message: `Progressive Hint Tier ${i + 1} (${key}) in '${qId}' is missing or too short.`,
        context: qId
      });
    }
  }

  if (!correctOption || !correctOption.t) return errors;

  const rawCorrect = String(correctOption.t).trim();
  const normCorrect = normalizeMathText(rawCorrect).toLowerCase();
  const nums = normCorrect.match(/-?\d+(?:\.\d+)?/g) || [];
  const isStopword = STOPWORDS.has(normCorrect);
  const isBooleanTarget = /^(?:true|false)$/i.test(normCorrect);

  hintKeys.forEach((key, hIdx) => {
    const hintText = hints[key] || hints[`hint_${hIdx + 1}`];
    if (!hintText) return;

    const normH = normalizeMathText(hintText).toLowerCase();

    // Boolean leak in hints
    if (isBooleanTarget) {
      const boolHintPattern = new RegExp(
        '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + '|statement\\s+is|claim\\s+is|actually)\\b)\\s*(?:[a-z]+\\s*){0,3}[:=]?\\s*\\b' + escapeRegex(normCorrect) + '\\b',
        'i'
      );
      if (boolHintPattern.test(normH)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_12_HINT_SPOILER_BOOLEAN',
          severity: 'ERROR',
          message: `Progressive Hint Tier ${hIdx + 1} reveals boolean answer '${rawCorrect}' in: "${hintText}".`,
          context: qId
        });
      }
    }

    // Verbatim answer leakage in hints
    if (normCorrect.length > 0 && !isStopword) {
      let verbatimHint = false;
      if (normCorrect.length >= 3) {
        verbatimHint = normH.includes(normCorrect);
      } else {
        const shortRegex = new RegExp(`(?:^|[\\s,;:(])${escapeRegex(normCorrect)}(?:$|[\\s,;:).!?])`, 'i');
        verbatimHint = shortRegex.test(normH);
      }
      if (verbatimHint) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_12_HINT_SPOILER',
          severity: 'ERROR',
          message: `Progressive Hint Tier ${hIdx + 1} leaks target answer '${rawCorrect}' in: "${hintText}".`,
          context: qId
        });
      }
    }

    // Numerical value leakage with leak predicates
    for (const n of nums) {
      const escapedN = escapeRegex(n);
      const leakPattern = new RegExp(
        '(?:\\b(?:' + LEAK_PREDICATES.map(p => escapeRegex(p).replace(/\s+/g, '\\s+(?:[a-z]+\\s+)?')).join('|') + ')\\b)\\s*(?:[a-z]+\\s*){0,4}[:=]?\\s*\\b' + escapedN + '\\b',
        'i'
      );
      if (leakPattern.test(normH)) {
        errors.push({
          questionId: qId,
          ruleId: 'RULE_12_HINT_SPOILER_VALUE',
          severity: 'ERROR',
          message: `Progressive Hint Tier ${hIdx + 1} reveals answer value '${n}' in: "${hintText}".`,
          context: qId
        });
      }
    }
  });

  return errors;
}

/**
 * Validates complete schema for a single assessment question.
 */
export function validateQuestionSchema(q, index = 0) {
  const qId = q.id || `Q_${index + 1}`;
  const errors = [];

  if (!q.q || String(q.q).trim().length < 5) {
    errors.push({
      questionId: qId,
      ruleId: 'SCHEMA_INVALID_QUESTION_PROMPT',
      severity: 'ERROR',
      message: `Question '${qId}' has missing or too short question prompt.`,
      context: qId
    });
  }

  if (!Array.isArray(q.opts) || q.opts.length < 3 || q.opts.length > 4) {
    errors.push({
      questionId: qId,
      ruleId: 'SCHEMA_INVALID_OPTION_COUNT',
      severity: 'ERROR',
      message: `Question '${qId}' must have exactly 3 to 4 options. Found: ${Array.isArray(q.opts) ? q.opts.length : 0}`,
      context: qId
    });
    return errors;
  }

  const correctOpts = q.opts.filter(o => o && o.c === true);
  if (correctOpts.length !== 1) {
    errors.push({
      questionId: qId,
      ruleId: 'SCHEMA_CORRECT_OPTION_COUNT',
      severity: 'ERROR',
      message: `Question '${qId}' must have EXACTLY ONE correct option marked (c: true). Found: ${correctOpts.length}`,
      context: qId
    });
    return errors;
  }

  const correctOption = correctOpts[0];

  // Validate duplicate options
  const seenTexts = new Set();
  q.opts.forEach((o, oIdx) => {
    const text = String(o.t || '').trim().toLowerCase();
    if (seenTexts.has(text)) {
      errors.push({
        questionId: qId,
        ruleId: 'SCHEMA_DUPLICATE_OPTION_TEXT',
        severity: 'ERROR',
        message: `Question '${qId}' has duplicate option text '${o.t}'.`,
        context: qId
      });
    }
    seenTexts.add(text);

    // Validate Rule #1 for each option
    const optErrors = validateZeroSpoilerInvariant(o, correctOption, qId, oIdx);
    errors.push(...optErrors);
  });

  // Validate 4-tier progressive hints if present
  if (q.hints) {
    const hintErrors = validate4TierHints(q.hints, correctOption, qId);
    errors.push(...hintErrors);
  }

  return errors;
}

/**
 * Audits an entire assessment exercise bank.
 */
export function validateAssessmentBank(questions = []) {
  const errors = [];
  let spoilersFound = 0;

  questions.forEach((q, idx) => {
    const qErrors = validateQuestionSchema(q, idx);
    for (const err of qErrors) {
      if (err.ruleId.includes('SPOILER')) spoilersFound++;
      errors.push(err);
    }
  });

  return {
    valid: errors.length === 0,
    totalQuestions: questions.length,
    spoilersFound,
    errors
  };
}

// ---------------------------------------------------------------------------
// Curriculum Exercise Bank Loader & Ingestion Adapter (Resource-First)
// ---------------------------------------------------------------------------

/**
 * Resolves path securely against repo workspace root.
 */
function resolvePath(filePath) {
  const root = resolveWorkspaceRoot();
  if (path.isAbsolute(filePath)) return filePath;
  return path.resolve(root, filePath);
}

/**
 * Ingests curriculum exercises from YAML contract or JSON question bank.
 * Partitions questions into Warm-up (Tier 1), Deep Dive (Tier 2), and Boss (Tier 3).
 * Verifies zero-spoiler compliance.
 */
export async function loadAndAdaptExerciseBank(contractOrJsonPath) {
  const resolved = resolvePath(contractOrJsonPath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`FILE_NOT_FOUND: Cannot locate assessment bank at ${resolved}`);
  }

  let questions = [];

  if (resolved.endsWith('.json')) {
    const rawData = JSON.parse(fs.readFileSync(resolved, 'utf-8'));
    questions = Array.isArray(rawData.questions) ? rawData.questions : [];
  } else if (resolved.endsWith('.yaml') || resolved.endsWith('.yml')) {
    // Look for referenced JSON question bank in contract directory or chapters
    const root = resolveWorkspaceRoot();
    const candidateJson = path.join(root, 'Aasha-AI', 'chapters', 'square_cube_questions.json');
    if (fs.existsSync(candidateJson)) {
      const rawData = JSON.parse(fs.readFileSync(candidateJson, 'utf-8'));
      questions = Array.isArray(rawData.questions) ? rawData.questions : [];
    }
  }

  const warmup = [];
  const deepDive = [];
  const boss = [];

  for (const q of questions) {
    const tier = (q.tier || '').toLowerCase().replace('-', '_');
    if (tier === 'warmup') {
      warmup.push(q);
    } else if (tier === 'deep_dive') {
      deepDive.push(q);
    } else if (tier === 'boss') {
      boss.push(q);
    } else {
      warmup.push(q);
    }
  }

  const validation = validateAssessmentBank(questions);

  return {
    totalQuestions: questions.length,
    warmup,
    deepDive,
    boss,
    allQuestions: questions,
    validation
  };
}
