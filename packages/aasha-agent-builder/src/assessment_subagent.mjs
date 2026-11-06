/**
 * AASHA AIOS — 3-Tier Gamified Assessment Subagent
 * Task 3: Assessment Engine, L-Truth Anti-Spoiler Linter & Web Component Generator
 *
 * Implements pure headless assessment models, scoring mechanics, anti-spoiler
 * validators, Foundation F27 cleanroom adaptation, and Web Component scripts.
 */

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
