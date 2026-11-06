---
name: cat-assessment-authoring
description: Psychometric assessment authoring engine implementing Item Response Theory (IRT 1PL/2PL/3PL) and offline Computerized Adaptive Testing (CAT) for AASHA HTML5 modules.
---

# CAT Assessment Authoring: Item Response Theory & Zero-Spoiler Scaffolding

This skill governs the authoring, psychometric calibration, and verification of adaptive assessment items within the Annanth Aasha Learning Ecosystem (AASHA AIOS).

## 1. Item Response Theory (IRT) Calibration Parameters

Every question in the curriculum bank must be tagged with psychometric IRT parameters compatible with standard 2PL/3PL logistic models:

$$P(\theta) = c + \frac{1 - c}{1 + e^{-a(\theta - b)}}$$

- **$b$ (Difficulty)**: Range $[-3.0, +3.0]$. Defines the student ability level $\theta$ at which the probability of success is $50\%$.
  - Tier 1 (Novice): $b \in [-2.5, -0.5]$
  - Tier 2 (Apprentice): $b \in [-0.5, +1.0]$
  - Tier 3 (Master): $b \in [+1.0, +2.5]$
- **$a$ (Discrimination)**: Range $[0.5, 2.5]$. Measures how steeply the item discriminates between student ability levels around $b$.
- **$c$ (Pseudo-guessing)**: For 4-option multiple-choice, default $c = 0.25$; for interactive numeric sliders/inputs, $c = 0.0$.

---

## 2. Invariant Rule #1: Distractor Anti-Spoiler Law

When writing misconception explanations (the `m` attribute of wrong options):
1. **Never Reveal the Correct Value**: The explanation must explain the flaw in the student's reasoning, NOT state what the right number or answer is.
2. **Pedagogical Reflection**: Direct attention back to the visual manipulative or core definition.

### Example:
- **Problem**: "Find $-3/4$ on the number line."
- **Wrong Choice**: $3/4$
- **❌ Violation (Leaking Answer)**: `"Incorrect. The correct answer is -3/4 on the left side."`
- **✅ Compliant ($0$-Spoiler)**: `"ध्यान दें: धनात्मक (Positive) और ऋणात्मक (Negative) संख्याओं की दिशा अलग होती है। शून्य (0) के बाईं ओर देखें।"`

---

## 3. 4-Tier Progressive Hint Scaffolding ($H_1 \to H_4$)

Every assessment question must provide 4 progressive hint levels that unmask sequentially without penalty on request:

1. **$H_1$ (Hook / Visual Anchor)**: Directs the student to observe an element in the simulation canvas.
   - *Example*: *"लौरेन्ट्ज़ बल (Lorentz Force) सिम्युलेटर में चुंबकीय क्षेत्र की दिशा (B) को नीले तीरों से देखें।"*
2. **$H_2$ (Conceptual Clue / Rule)**: States the governing mathematical or physical rule.
   - *Example*: *"फ्लेमिंग का बाएँ हाथ का नियम (Fleming's Left-Hand Rule): अंगूठा बल (F), तर्जनी चुंबकीय क्षेत्र (B), और मध्यमा धारा (I) को दर्शाती है।"*
3. **$H_3$ (Elimination Strategy)**: Helps eliminate impossible distractor options.
   - *Example*: *"यदि धारा ऊपर की ओर है और चुंबकीय क्षेत्र दाईं ओर है, तो बल स्क्रीन के अंदर या बाहर होगा, ऊपर-नीचे नहीं।"*
4. **$H_4$ (Procedural Step)**: Outlines the exact calculation or orientation step without solving it for the student.
   - *Example*: *"बाएँ हाथ की तर्जनी को दाईं ओर इंगित करें, मध्यमा को ऊपर की ओर मोड़ें, अब देखें अंगूठा किस दिशा में संकेत कर रहा है।"*

---

## 4. Offline Computerized Adaptive Testing (CAT) Algorithm

The standalone chapter HTML bundle executes a lightweight in-browser adaptive selection algorithm:

```typescript
export class OfflineCATEngine {
  private theta: number = 0.0; // Initial ability estimate (average)

  // Update student theta using Expected A Posteriori (EAP)
  public updateAbility(item: IRTItem, isCorrect: boolean): number {
    const p = this.probability(this.theta, item.a, item.b, item.c);
    const information = Math.pow(item.a, 2) * (p * (1 - p));
    const delta = (isCorrect ? 1 : 0) - p;
    this.theta = this.theta + (item.a * delta) / (information + 0.1);
    // Clamp theta between -3.0 and +3.0
    this.theta = Math.max(-3.0, Math.min(3.0, this.theta));
    return this.theta;
  }

  // Select next item maximizing Fisher Information at current theta
  public selectNextItem(bank: IRTItem[], attemptedIds: Set<string>): IRTItem {
    const unattempted = bank.filter(i => !attemptedIds.has(i.id));
    return unattempted.reduce((best, curr) => {
      const infoCurr = this.fisherInformation(this.theta, curr);
      const infoBest = this.fisherInformation(this.theta, best);
      return infoCurr > infoBest ? curr : best;
    }, unattempted[0]);
  }

  private probability(theta: number, a: number, b: number, c: number): number {
    return c + (1 - c) / (1 + Math.exp(-a * (theta - b)));
  }

  private fisherInformation(theta: number, item: IRTItem): number {
    const p = this.probability(theta, item.a, item.b, item.c);
    const num = Math.pow(item.a, 2) * Math.pow(p - item.c, 2);
    const denom = Math.pow(1 - item.c, 2) * p * (1 - p);
    return denom === 0 ? 0 : num / denom;
  }
}
```

---

## 5. JSON Item Authoring Schema

```json
{
  "id": "q_class8_ch01_004",
  "topic": "rational_numbers",
  "irt": {
    "a": 1.4,
    "b": -0.2,
    "c": 0.25
  },
  "question": {
    "en": "Which of the following rational numbers lies strictly between $1/4$ and $1/2$?",
    "hi": "निम्नलिखित में से कौन सी परिमेय संख्या $1/4$ और $1/2$ के ठीक बीच में स्थित है?"
  },
  "options": [
    { "key": "A", "val": "$1/8$", "m": "यह मान $1/4$ से भी छोटा है। संख्या रेखा पर $0$ के अधिक निकट देखें।" },
    { "key": "B", "val": "$3/8$", "correct": true },
    { "key": "C", "val": "$5/8$", "m": "यह मान $1/2$ (जो कि $4/8$ है) से बड़ा है।" },
    { "key": "D", "val": "$3/4$", "m": "यह मान $1/2$ से काफी बड़ा है।" }
  ],
  "hints": {
    "h1": "दोनों भिन्नों के हर (denominator) को $8$ बनाकर तुलना करें।",
    "h2": "$1/4 = 2/8$ और $1/2 = 4/8$ होता है।",
    "h3": "अब $2/8$ और $4/8$ के बीच का अंश (numerator) चुनें।",
    "h4": "$2$ और $4$ के बीच केवल संख्या $3$ आती है।"
  }
}
```
