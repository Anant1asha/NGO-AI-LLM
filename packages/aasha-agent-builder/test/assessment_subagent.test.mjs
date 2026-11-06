import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AssessmentBankModel,
  GamifiedScoringEngine,
  validateQuestionSchema,
  validateZeroSpoilerInvariant,
  validate4TierHints,
  validateAssessmentBank,
  loadAndAdaptExerciseBank,
  generateAssessmentScript
} from '../src/assessment_subagent.mjs';

test('AssessmentBankModel organizes 3 tiers and manages progressive hints', () => {
  const rawQuestions = [
    {
      id: 'q1',
      tier: 'warmup',
      q: 'What is 5²?',
      opts: [
        { t: '25', c: true, m: '' },
        { t: '10', c: false, m: 'Doubled base instead of squaring' },
        { t: '15', c: false, m: 'Added 10 to 5 instead of squaring base' }
      ],
      hints: {
        h1: 'Look at exponent',
        h2: 'Repeated mult',
        h3: '5 times 5',
        h4: 'Evaluate 5 * 5'
      }
    },
    {
      id: 'q2',
      tier: 'deep_dive',
      q: 'Evaluate √144',
      opts: [
        { t: '12', c: true, m: '' },
        { t: '72', c: false, m: 'Divided by 2 instead of taking root' },
        { t: '14', c: false, m: 'Estimated near 200 without checking factors' }
      ],
      hints: {
        h1: 'Area to side',
        h2: 'Square of x is 144',
        h3: 'Test 10² and 20²',
        h4: 'Prime factorize 144'
      }
    },
    {
      id: 'q3',
      tier: 'boss',
      q: 'Is 1729 taxicab?',
      opts: [
        { t: 'Yes', c: true, m: '' },
        { t: 'No', c: false, m: 'Ramanujan sum misconception' },
        { t: 'Cannot be determined', c: false, m: 'Lacks formula knowledge' }
      ],
      hints: {
        h1: 'Two cubes sum',
        h2: '1³+12³',
        h3: '9³+10³',
        h4: 'Smallest such number'
      }
    }
  ];

  const model = new AssessmentBankModel({ questions: rawQuestions });
  assert.equal(model.getTierCount('warmup'), 1);
  assert.equal(model.getTierCount('deep_dive'), 1);
  assert.equal(model.getTierCount('boss'), 1);

  // Test hint unlocking progression
  assert.equal(model.getCurrentHintLevel('q1'), 0);
  assert.equal(model.unlockNextHint('q1'), 'Look at exponent');
  assert.equal(model.getCurrentHintLevel('q1'), 1);
  assert.equal(model.unlockNextHint('q1'), 'Repeated mult');
  assert.equal(model.getCurrentHintLevel('q1'), 2);
  assert.equal(model.unlockNextHint('q1'), '5 times 5');
  assert.equal(model.getCurrentHintLevel('q1'), 3);
  assert.equal(model.unlockNextHint('q1'), 'Evaluate 5 * 5');
  assert.equal(model.getCurrentHintLevel('q1'), 4);
  assert.equal(model.unlockNextHint('q1'), null);
});

test('GamifiedScoringEngine handles streaks, multipliers, lives and XP', () => {
  const engine = new GamifiedScoringEngine({ initialLives: 3, baseXP: 100 });
  assert.equal(engine.getState().lives, 3);
  assert.equal(engine.getState().streak, 0);
  assert.equal(engine.getState().multiplier, 1.0);

  // Correct answer increments streak and multiplies XP
  let res = engine.recordAnswer({ isCorrect: true, hintPenaltyLevel: 0 });
  assert.equal(res.awardedXP, 100);
  assert.equal(engine.getState().streak, 1);

  // Another correct answer increments streak
  res = engine.recordAnswer({ isCorrect: true, hintPenaltyLevel: 1 });
  assert.ok(res.awardedXP > 0);
  assert.equal(engine.getState().streak, 2);

  // Wrong answer loses a life and breaks streak
  res = engine.recordAnswer({ isCorrect: false });
  assert.equal(res.awardedXP, 0);
  assert.equal(engine.getState().lives, 2);
  assert.equal(engine.getState().streak, 0);
  assert.equal(engine.getState().multiplier, 1.0);
});

test('Anti-Spoiler Linter catches answer leaks in distractor misconceptions and hints', () => {
  const leakingQuestion = {
    id: 'leak_01',
    q: 'What is 7 multiplied by 7?',
    opts: [
      { t: '49', c: true, m: '' },
      { t: '14', c: false, m: 'Added 7 and 7 giving 49 instead of multiplying.' }, // Leaks '49'
      { t: '42', c: false, m: 'Multiplied 7 by 6 rather than 7.' }
    ],
    hints: {
      h1: 'Recall 7 times table.',
      h2: 'Multiply the base by itself.',
      h3: 'The answer is 49.', // Leaks answer in hint!
      h4: 'Calculate 7 * 7.'
    }
  };
  const errors = validateQuestionSchema(leakingQuestion);
  assert.ok(errors.some(e => e.ruleId === 'RULE_1_SPOILER_NUMERICAL_LEAK' || e.ruleId === 'RULE_1_SPOILER_VALUE' || e.ruleId === 'RULE_1_SPOILER_VERBATIM_ANSWER'));
  assert.ok(errors.some(e => e.ruleId === 'RULE_12_HINT_SPOILER' || e.ruleId === 'RULE_12_HINT_SPOILER_VALUE'));
});

test('Anti-Spoiler Linter approves clean 4-tier diagnostic questions without spoilers', () => {
  const cleanQuestion = {
    id: 'clean_01',
    q: 'What is the square root of 64?',
    opts: [
      { t: '8', c: true, m: '' },
      { t: '32', c: false, m: 'Divided the radicand by 2 instead of finding the repeated square factor.' },
      { t: '16', c: false, m: 'Divided by 4 or confused square root with halving twice.' }
    ],
    hints: {
      h1: 'Look at the square root symbol above 64.',
      h2: 'Recall which single integer multiplied by itself reproduces 64.',
      h3: 'Test consecutive digits between 5 and 10.',
      h4: 'Notice that prime factors group into identical pairs.'
    }
  };
  const errors = validateQuestionSchema(cleanQuestion);
  assert.equal(errors.length, 0, 'Clean question must have 0 validation errors');
});

test('loadAndAdaptExerciseBank loads and verifies complete 34 textbook questions from contract', async () => {
  const bank = await loadAndAdaptExerciseBank('Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml');
  assert.equal(bank.totalQuestions, 34);
  assert.equal(bank.warmup.length, 12);
  assert.equal(bank.deepDive.length, 14);
  assert.equal(bank.boss.length, 8);
  assert.equal(bank.validation.errors.length, 0);
  assert.equal(bank.validation.spoilersFound, 0);
});

test('generateAssessmentScript produces valid self-contained client Web Component', () => {
  const spec = {
    id: 'asmt_test_01',
    title: 'Squares & Cubes 3-Tier Assessment',
    gameMode: 'boss_battle_rapid_fire',
    questions: [
      {
        id: 'q1',
        tier: 'warmup',
        q: 'What is 3²?',
        opts: [
          { t: '9', c: true, m: '' },
          { t: '6', c: false, m: 'Multiplied by 2 instead of squaring.' }
        ],
        hints: {
          h1: 'Look at exponent 2',
          h2: '3 times 3',
          h3: 'Repeated multiplication',
          h4: 'Evaluate 3 * 3'
        }
      }
    ]
  };
  const script = generateAssessmentScript(spec);
  assert.ok(script.includes("customElements.define('aasha-assessment'"));
  assert.ok(script.includes('class AashaGamifiedAssessmentAdapter'));
  assert.ok(script.includes('class AashaAudioEngine'));
  assert.ok(script.includes('min-width: 44px'));
  assert.ok(script.includes('min-height: 44px'));
  assert.ok(!script.includes('http://'));
  assert.ok(!script.includes('https://'));
  // XSS safety
  assert.ok(!script.includes('${SPEC.title}'));
});
