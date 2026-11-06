import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AssessmentBankModel,
  GamifiedScoringEngine
} from '../src/assessment_subagent.mjs';

test('AssessmentBankModel organizes 3 tiers and manages progressive hints', () => {
  const rawQuestions = [
    {
      id: 'q1',
      tier: 'warmup',
      q: 'What is 5²?',
      opts: [
        { t: '25', c: true, m: '' },
        { t: '10', c: false, m: 'Doubled base instead of squaring' }
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
        { t: '72', c: false, m: 'Divided by 2 instead of taking root' }
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
        { t: 'No', c: false, m: 'Ramanujan sum misconception' }
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
