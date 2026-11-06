---
name: gamified-quest-architect
description: Operational runbook and domain design patterns for authoring 3-tier gamified mastery loops, reward mechanics, streak shields, and offline Web Component integration (<aasha-game-quest>) for AASHA AIOS.
---

# Gamified Quest Architect Skill: 3-Tier Mastery & Offline Game Loops

This skill governs the design, authoring, and runtime configuration of gamified learning loops and motivational mechanics for the Annanth Aasha Learning Ecosystem (AASHA AIOS).

## 1. Pedagogical Gamification Philosophy (Anti-Frustration Standard)

AASHA's gamified learning does not rely on superficial points or predatory timers. It follows a mastery-driven, non-punitive progression:
1. **Never Punish Exploration**: Wrong answers during exploratory phases must NEVER deduct points, reset progress to zero, or lock the student out.
2. **Mastery Over Speed**: Timers are strictly prohibited for basic concept acquisition. Any timed challenge must be an opt-in "speed run" or boss challenge after mastery is achieved.
3. **Tactile Feedback Loops**: Every interaction (slider move, tile drag, option tap) provides immediate visual (haptic pulse / spring bounce) and Web Audio acoustic feedback.

---

## 2. 3-Tier Quest Progression Model

Every learning chapter is structured as a 3-tier quest narrative:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: NOVICE EXPLORER (The Sensory Sandpit)                              │
│ • Focus: Tactile interaction with Foundation Sim (<aasha-sim>)              │
│ • Goal: Discover physical laws/mechanics through free play                  │
│ • Rules: 0 questions, 0 failure states, milestone badge on parameter reach   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Unlock Quest Key
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 2: APPRENTICE INVESTIGATOR (Guided Challenge Loops)                   │
│ • Focus: 3-5 Scaffolding questions with dynamic interactive updates         │
│ • Goal: Bridge physical intuition to formal mathematical definitions       │
│ • Rules: 4-tier progressive hints (H1 -> H4); zero-spoiler misconceptions   │
│ • Rewards: Streak Shield awarded on consecutive correct answers             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Unlock Final Trial
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 3: MASTER CREATOR (The Boss Challenge / Real-World Transfer)           │
│ • Focus: Parametric multi-step problem solving                             │
│ • Goal: Apply concepts to solve real-world Indian rural/daily scenarios     │
│ • Rewards: Chapter Mastery Badge + Bilingual Concept Certificate            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Web Component Integration Standard (`<aasha-game-quest>`)

Gamification elements must be implemented as clean, framework-agnostic HTML5 Web Components:

```html
<aasha-game-quest 
  data-chapter-id="ch08-rational-numbers"
  data-tier="APPRENTICE"
  data-target-xp="100">
  
  <div class="quest-header">
    <aasha-streak-meter count="3" max="5" shield="true"></aasha-streak-meter>
    <aasha-xp-badge level="2" xp="65" title="अन्वेषक (Investigator)"></aasha-xp-badge>
  </div>

  <div class="quest-viewport">
    <!-- Active Foundation Simulation -->
    <aasha-sim data-foundation="F01_ESCAPE_RUN" data-interactive="true"></aasha-sim>
    
    <!-- Assessment Question Card -->
    <aasha-assessment data-step="1" data-total-steps="4"></aasha-assessment>
  </div>
</aasha-game-quest>
```

### Required Lifecycle & Event Bus Methods:
- `quest.awardXP(amount: number, reason: string)`: Increments local student XP.
- `quest.triggerCelebration(type: 'streak' | 'tier_complete' | 'badge_unlocked')`: Triggers lightweight SVG particle burst.
- `quest.playAudioChime(chord: 'success' | 'tap' | 'milestone')`: Dispatches synthetic Web Audio tone (0 external MP3 files).

---

## 4. Zero-Asset Offline Sound Engine (Web Audio API)

All audio feedback must be dynamically synthesized using standard browser Web Audio oscillators to comply with the 20MB offline ceiling:

```javascript
export function playSyntheticChime(type = 'success') {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  const ctx = new AudioCtx();
  
  if (type === 'success') {
    // Harmonic Major Triad (C5 -> E5 -> G5)
    [523.25, 659.25, 783.99].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.08);
      gain.gain.setValueAtTime(0.15, ctx.currentTime + idx * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.08 + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + idx * 0.08);
      osc.stop(ctx.currentTime + idx * 0.08 + 0.35);
    });
  } else if (type === 'tap') {
    // Gentle 10ms click
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.setValueAtTime(800, ctx.currentTime);
    gain.gain.setValueAtTime(0.05, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.03);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.03);
  }
}
```

---

## 5. Touch Target & Mobile Viewport Constraints
- All quest interactive buttons (`Next`, `Hint`, `Verify`, `Reset`) must measure strictly **$\ge 44 \times 44\text{px}$**.
- Dynamic feedback bars must fit within the same mobile viewport without pushing the simulation canvas below the fold.
