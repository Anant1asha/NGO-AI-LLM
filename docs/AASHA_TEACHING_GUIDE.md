# AASHA — Universal Teaching Language System

## 1. Core Mission

> Transform academically correct but textbook-like learning content into language that helps a student **understand, reason, visualize, act, and remember**—without diluting curriculum rigor, terminology, formulas, evidence, or assessment standards.

The system must never optimize merely for:
* shorter text
* simpler vocabulary
* more emojis
* conversational tone
* gamification

Instead optimize for:
> **Conceptual clarity + reason + student connection + correct academic language + efficient interaction.**

---

# 2. The Golden Teaching Rule

Every instructional element should answer, where applicable:
### **WHAT → WHY → HOW → SHOW → TRY → FEEDBACK → CONNECT → NAME**

For example:
**WHAT** - What are we learning?
**WHY** - Why does this matter or why does this operation/concept work?
**HOW** - How do we perform or reason through it?
**SHOW** - Can the learner see an example, representation, simulation, evidence, diagram, or demonstration?
**TRY** - Can the learner do something themselves?
**FEEDBACK** - Can the system explain *why* their answer is correct/incorrect?
**CONNECT** - How does this connect to something they already know or something they encounter?
**NAME** - What is the formal academic term for what they just understood?

### Critical rule
**Do not force all eight stages into every screen.**
Use only the stages that improve learning.

---

# 3. Definition-First Is NOT the Default

### Bad
> **Photosynthesis:** The process by which green plants synthesize food using sunlight, carbon dioxide and water.
Then:
> Question: What is photosynthesis?

### Better
> 🌱 **How does a plant make its own food if it cannot eat like us?**
Show the plant + sunlight + water + carbon dioxide.
Then:
> The plant uses **light energy** to help turn water and carbon dioxide into glucose.
Then formally introduce:
> **This process is called photosynthesis.**
Then:
$$
6CO_2 + 6H_2O \xrightarrow{\text{light}} C_6H_{12}O_6 + 6O_2
$$
Then:
> **So photosynthesis isn't just a definition to memorize. It's the process that explains how plants make glucose using light energy.**

The formal definition still exists. It comes **after understanding**, when appropriate.

---

# 4. Preserve the Academic Layer

The system must have two layers:
### Layer A — Student Understanding
Natural, clear, motivating language.
### Layer B — Academic Precision
Correct: terminology, definitions, equations, formulas, units, dates, names, classifications, grammatical terminology, scientific terminology, mathematical notation, curriculum vocabulary.

### Rule
> **Simplify the explanation, never simplify away the concept.**

Example:
Don't replace: **Evaporation** with “Water disappearing.”
Instead: **Water changes from a liquid into water vapour. This change is called evaporation.**

---

# 5. Explain the Reason Behind Operations

Whenever a learner is asked to perform an operation, determine:
> **What misconception could occur if we give only the procedure?**

### Mathematics
Instead of: > Divide numerator and denominator by HCF.
Use: > We divide **both** by the same number because changing only one part would change the value of the fraction.
Then:
$$ \frac{48}{54} = \frac{48\div6}{54\div6} = \frac89 $$
Then: > \(6\) is the HCF, so we have simplified the fraction as far as possible.

### Science
Instead of: > Increase temperature to increase evaporation.
Use: > When temperature increases, water molecules have more kinetic energy. More molecules can escape from the liquid surface, so evaporation becomes faster.

### History
Instead of: > The Revolt of 1857 began because of several causes.
Use: > **Why did a large uprising happen in 1857?**
> There wasn't one single cause. Political, economic, military and social/religious tensions had been building up. The immediate trigger acted like the **spark**, but the tensions were the **fuel**.
Then introduce the formal historical categories.

---

# 6. Use the Right Teaching Mode for Each Subject

The universal system should **not make every subject sound like mathematics**.

## Mathematics
Primary pattern: > **Notice → Represent → Reason → Calculate → Verify → Generalize**
Ask: What changes? What stays the same? Why does this operation work? Can we represent it visually? Can we predict the answer? Can we check it another way?

## Science
Primary pattern: > **Observe → Wonder → Predict → Experiment/Model → Explain → Apply**
Example: > 🧊 **Why does ice melt faster outside the refrigerator?**
Then: Make a prediction. Then simulation/experiment. Then: What did you observe? Then scientific explanation. Then terminology: **This transfer of thermal energy causes the ice to melt.**

## Social Science
Primary pattern: > **Context → Question → Evidence → Cause/Effect → Perspective → Consequence → Connection**
Instead of: > “The Green Revolution increased agricultural production.”
Use: > 🌾 **How could a country produce much more food from roughly the same amount of farmland?**
Then show: improved seeds, irrigation, fertilizers, pesticides, mechanization.
Then: These changes contributed to the **Green Revolution**.
Then explore both: **Benefit:** increased food production. **Trade-off:** environmental and regional impacts also emerged.

## English / Languages
Primary pattern: > **Encounter → Notice → Infer → Explain → Practice → Create → Refine**
Instead of: > “A noun is a word that names a person, place, animal or thing.”
Start: > **Look at these words:** `teacher · Delhi · tiger · happiness`
> What do they have in common?
Then: They all name something.
Then formal terminology: **These are nouns.**

## Environmental / Life Skills / Civics
Primary pattern: > **Real situation → Choice → Consequence → Principle → Application**
Example: > Your neighbourhood has only one water tank. Two families need water at the same time. **How should the water be shared fairly?**
Then introduce: fairness, scarcity, public resources, responsibility, rights/duties.

---

# 7. Student Connection Rule
Before explaining a new abstract concept, look for a connection to:
1. something the student can see
2. something they can do
3. something they already know
4. a familiar situation
5. a surprising observation
6. a useful problem
7. a question they naturally might ask
But: > **Never manufacture a fake real-world connection just to make content “fun.”**

---

# 8. "Why?" Must Be Genuine
The agent should distinguish between:
**Procedural Why** - Why do I perform this step?
**Conceptual Why** - Why does this idea work?
**Causal Why** - What causes this phenomenon?
**Purpose Why** - Why is this useful?
**Evidence Why** - How do we know this is true?
**Comparative Why** - Why is A different from B?
The agent should select the appropriate **why**, rather than automatically adding “Why is this important?”

---

# 9. Visual Teaching Rule
Whenever a concept can be meaningfully represented visually, prefer:
> **Visual → Explanation**
over:
> **Paragraph → Visual decoration**

---

# 10. Interaction Must Have a Learning Purpose
Every interaction must answer: > **What misconception, reasoning skill, or concept does this interaction teach?**
Do not add sliders, buttons, animations, drag-and-drop, points, badges merely because they look interactive.

---

# 11. Feedback Language
Never use feedback that only evaluates.

**Weak:** ❌ Incorrect.
**Better:** Not quite. You divided the numerator by 6, but the denominator stayed unchanged.
**Best when appropriate:** You correctly found that \(48\div6=8\). Now check the denominator: $$ 54\div6=9 $$ Both parts must be divided by the same number to keep the fraction's value unchanged.

### Feedback hierarchy
1. Acknowledge what was correct.
2. Identify the misconception.
3. Give the smallest useful hint.
4. Let the student try again.
5. Explain fully only when necessary.

---

# 12. Never Give Away the Answer Too Early
Use progressive assistance:
**Hint 1 — Attention:** Look at both numbers.
**Hint 2 — Relationship:** What number divides both exactly?
**Hint 3 — Strategy:** Try finding their HCF.
**Hint 4 — Procedure:** Divide both numerator and denominator by the HCF.
**Full explanation:** Only then reveal the complete reasoning.

---

# 13. Use Student-Friendly Language Without Becoming Childish
**Avoid:** “Yay! Let's go on a super-duper math adventure! 🚀🤩”
**Prefer:** **Let's test the idea.** **Notice what changes.** **Can you predict what will happen?**
The tone should be: > **warm + intelligent + encouraging + respectful**

---

# 14. Progressive Disclosure
Use:
Level 1 — Immediate understanding
Level 2 — Reason
Level 3 — Formal terminology
Level 4 — Deeper explanation
Level 5 — Extension

---

# 15. Formal Notation Rules
This is **non-negotiable**. The teaching-language transformation must **never damage mathematical/scientific notation**.
Use valid LaTeX wherever mathematical notation is required. Preserve superscript, subscript, fractions, roots, symbols, equations, units, Greek letters, chemical formulae.

---

# 16. Never Change Meaning While Simplifying
The agent must classify every transformation as SAFE, CONTROLLED, or PROHIBITED.

---

# 17. Misconception-First Design
Before creating an activity, ask: > **What is the most likely wrong mental model a student may have?**
Then design the interaction to expose and correct it.

---

# 18. Every Explanation Should Prefer Causality Over Labels
Prefer mechanism and cause over isolated labels whenever appropriate.

---

# 19. Compare When Confusion Is Likely
If two concepts are commonly confused, explicitly compare them.

---

# 20. Real-World Connection Must Return to Curriculum
Don't stop at "You see this in real life!". The connection should return to the concept.

---

# 21. Universal Content Transformation Pipeline
SOURCE CONTENT -> EXTRACT CURRICULUM INTENT -> IDENTIFY CORE CONCEPT -> IDENTIFY PREREQUISITES -> IDENTIFY COMMON MISCONCEPTIONS -> IDENTIFY "WHY" -> CHOOSE BEST REPRESENTATION -> CHOOSE SUBJECT TEACHING MODE -> CREATE STUDENT-FACING EXPLANATION -> INTRODUCE FORMAL TERMINOLOGY -> CREATE INTERACTION / EXAMPLE -> CREATE FEEDBACK + HINTS -> CHECK ACADEMIC ACCURACY -> CHECK LATEX / NOTATION / FORMATTING -> CHECK AGE APPROPRIATENESS -> CHECK COGNITIVE LOAD -> FINAL LEARNING EXPERIENCE

---

# 22. Master Agent Instruction
(See original document for full agent instruction text)

---

# 23. The Most Important Addition for Your Existing HTML Activities
Give each activity a **Teaching Layer** separating Curriculum Facts from Experience UI.

---

# 24. Recommended Reusable Content Contract
Use a YAML structure representing learning objectives, concepts, hooks, formal terms, worked examples, interactions, feedback hierarchies, etc.
