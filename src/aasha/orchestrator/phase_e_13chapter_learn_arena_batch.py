"""Batch Compiler for the 10-Chapter NCERT + NCVET/PSSCIVE Curriculum & 3 Vocational Job Roles.

Compiles every canonical chapter and NCVET job role into dual self-contained offline HTML5 modules:
  - <chapter_id>_Learning.html (Aasha Learn: action-gated SLIDES, live SVG visualizers/sliders, WM2/PH/CONN/EMO)
  - <chapter_id>_Arena.html    (Aasha Arena: PixiJS v8.6.6 WebGL + Canvas2D fallback, SPR sprites, guide + choice questions)

Certifies all 26 generated HTML5 modules with `qa/run_qa.js` (with bounded 2-attempt self-healing repair),
updates `teas_content.db` / `teas_content.db.gz`, and updates `Aasha-AI/aasha-student-pwa/src/sw_cache_manifest.json`
and `Aasha-AI/experience_registry/registry.json`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json"
PIPELINE_SRC = PIPELINE_ROOT / "src"

if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))
if "aasha" in sys.modules and hasattr(sys.modules["aasha"], "__path__"):
    _pkg = str(PIPELINE_SRC / "aasha")
    if _pkg not in sys.modules["aasha"].__path__:
        sys.modules["aasha"].__path__.append(_pkg)

from aasha.assemble.learn_arena_assembler import LearnArenaAssembler
from aasha.pipeline.orchestrator import Orchestrator


CANONICAL_13_CHAPTER_BATCH: list[dict[str, Any]] = [
    {
        "chapter_id": "NCERT-G06-MATH-CH07-FRACTIONS",
        "pack_dir": "g3_10chapter_pack",
        "grade": 6,
        "subject": "math",
        "title": "Fractions on the Number Line & Equivalent Ratios",
        "subtitle_hi": "संख्या रेखा पर भिन्न और समतुल्य अनुपात",
        "concepts": [
            {
                "title": "Proper, Improper & Mixed Fractions on the Number Line",
                "emoji": "📏",
                "body": "A fraction represents equal parts of a whole. On a number line between 0 and 1, dividing the segment into b equal parts places 1/b at the first mark.",
                "sim_mult": 3,
                "we_q": "Plot 3/4 on a number line and find an equivalent fraction with denominator 12.",
                "we_steps": [
                    "Divide the interval from 0 to 1 into 4 equal parts; the 3rd mark is 3/4.",
                    "Multiply numerator and denominator by 3: (3 × 3) / (4 × 3).",
                    "Verified equivalent fraction: 9/12 represents the exact same point.",
                ],
                "quiz_q": "Which fraction is equivalent to 3/4 on the number line?",
                "opts": [
                    {"t": "9/12", "c": True, "m": ""},
                    {"t": "6/12", "c": False, "m": "6/12 simplifies to 1/2, not 3/4."},
                    {"t": "7/8", "c": False, "m": "Adding the same number to top and bottom changes the ratio."},
                ],
            },
            {
                "title": "Equivalent Fractions & Simplest Form",
                "emoji": "⚖️",
                "body": "Multiplying or dividing both the numerator and denominator by the same non-zero number keeps the value of the fraction unchanged.",
                "sim_mult": 4,
                "we_q": "Reduce 18/24 to its simplest form.",
                "we_steps": [
                    "Find the highest common factor (HCF) of 18 and 24, which is 6.",
                    "Divide both numerator and denominator by 6: (18 ÷ 6) / (24 ÷ 6).",
                    "Simplest form is 3/4.",
                ],
                "quiz_q": "What is the simplest form of 15/25?",
                "opts": [
                    {"t": "3/5", "c": True, "m": ""},
                    {"t": "5/3", "c": False, "m": "Do not invert the numerator and denominator."},
                    {"t": "1/5", "c": False, "m": "Divide 15 by 5 to get 3 in the numerator."},
                ],
            },
            {
                "title": "Adding & Subtracting Fractions in Jal Seva Tank Audits",
                "emoji": "💧",
                "body": "To add or subtract unlike fractions, first convert them to like fractions using the least common multiple (LCM) of their denominators.",
                "sim_mult": 5,
                "we_q": "A rainwater tank is 2/5 full in the morning and gains 3/10 more. What fraction is full now?",
                "we_steps": [
                    "Find the LCM of denominators 5 and 10, which is 10.",
                    "Convert 2/5 to 4/10 so both fractions have denominator 10.",
                    "Add numerators: 4/10 + 3/10 = 7/10 of the tank is full.",
                ],
                "quiz_q": "What is 1/3 + 1/6?",
                "opts": [
                    {"t": "1/2", "c": True, "m": ""},
                    {"t": "2/9", "c": False, "m": "Never add denominators directly; find the common denominator 6 first."},
                    {"t": "2/6", "c": False, "m": "Convert 1/3 to 2/6 before adding 1/6."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G07-MATH-CH11-PERIMETER-AREA",
        "pack_dir": "g3_10chapter_pack",
        "grade": 7,
        "subject": "math",
        "title": "Perimeter and Area of Polygons & Community Gardens",
        "subtitle_hi": "बहुभुज और सामुदायिक उद्यानों का परिमाप और क्षेत्रफल",
        "concepts": [
            {
                "title": "Perimeter & Area of Rectangles and Squares",
                "emoji": "📐",
                "body": "Perimeter is the total boundary distance around a closed figure (P = 2(l + b)), while area measures the surface enclosed inside (A = l × b).",
                "sim_mult": 4,
                "we_q": "An Eco Seva garden bed is 8 m long and 5 m wide. Find its fencing perimeter and soil area.",
                "we_steps": [
                    "Calculate perimeter: P = 2 × (8 + 5) = 2 × 13 = 26 m.",
                    "Calculate area: A = 8 × 5 = 40 sq m.",
                    "The bed needs 26 m of boundary fencing and covers 40 m².",
                ],
                "quiz_q": "If a rectangular plot has length 10 m and breadth 4 m, what is its perimeter?",
                "opts": [
                    {"t": "28 m", "c": True, "m": ""},
                    {"t": "40 m", "c": False, "m": "40 m² is the area (l × b), not the boundary perimeter."},
                    {"t": "14 m", "c": False, "m": "14 m is only l + b; double it for all four sides."},
                ],
            },
            {
                "title": "Area of Parallelograms & Triangles",
                "emoji": "🔺",
                "body": "Every parallelogram with base b and perpendicular height h has area A = b × h, and a triangle with the same base and height has half that area: A = ½ × b × h.",
                "sim_mult": 3,
                "we_q": "Find the area of a triangular solar-panel support frame with base 6 m and height 4 m.",
                "we_steps": [
                    "Identify base b = 6 m and perpendicular height h = 4 m.",
                    "Apply the triangle area formula: A = ½ × b × h.",
                    "Compute A = 0.5 × 6 × 4 = 12 m².",
                ],
                "quiz_q": "What is the area of a parallelogram with base 9 cm and perpendicular height 5 cm?",
                "opts": [
                    {"t": "45 cm²", "c": True, "m": ""},
                    {"t": "22.5 cm²", "c": False, "m": "Do not divide by 2 for a parallelogram; ½ × b × h is for triangles."},
                    {"t": "28 cm²", "c": False, "m": "Multiply base by perpendicular height."},
                ],
            },
            {
                "title": "Circumference & Area of Circular Water Tanks",
                "emoji": "⭕",
                "body": "For a circle of radius r, the circumference is C = 2πr and the enclosed area is A = πr² (where π ≈ 22/7).",
                "sim_mult": 6,
                "we_q": "Find the circumference of a circular tank cover of radius 7 m (use π = 22/7).",
                "we_steps": [
                    "Write the circumference formula: C = 2 × π × r.",
                    "Substitute r = 7 m and π = 22/7: C = 2 × (22/7) × 7.",
                    "Cancel 7 to obtain C = 44 m.",
                ],
                "quiz_q": "If the radius of a circle doubles, how does its area change?",
                "opts": [
                    {"t": "It becomes 4 times as large", "c": True, "m": ""},
                    {"t": "It doubles", "c": False, "m": "Area depends on r², so doubling r multiplies area by 2²."},
                    {"t": "It stays the same", "c": False, "m": "Area scales with the square of the radius."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G08-MATH-CH08-COMPARING-QUANTITIES",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "math",
        "title": "Comparing Quantities, Percentages & Cooperative Micro-Savings",
        "subtitle_hi": "राशियों की तुलना, प्रतिशत और सहकारी बचत",
        "concepts": [
            {
                "title": "Ratios, Percentages & Percentage Change",
                "emoji": "📊",
                "body": "A percentage is a ratio with denominator 100. Percentage increase or decrease is always calculated on the original base value.",
                "sim_mult": 5,
                "we_q": "Solar pump output rose from 40 L/min to 50 L/min. Find the percentage increase.",
                "we_steps": [
                    "Find the change in output: ΔV = 50 − 40 = 10 L/min.",
                    "Divide by the original value 40: 10 / 40 = 1/4.",
                    "Multiply by 100%: (1/4) × 100% = 25% increase.",
                ],
                "quiz_q": "A price drops from ₹200 to ₹160. What is the discount percentage?",
                "opts": [
                    {"t": "20%", "c": True, "m": ""},
                    {"t": "40%", "c": False, "m": "₹40 is the rupee discount; divide ₹40 by the original ₹200."},
                    {"t": "25%", "c": False, "m": "Divide by the original price ₹200, not the new price ₹160."},
                ],
            },
            {
                "title": "Profit, Loss, Discount & GST",
                "emoji": "🪙",
                "body": "Profit or loss is measured on Cost Price (CP), whereas discount is subtracted from Marked Price (MP) before applying GST.",
                "sim_mult": 4,
                "we_q": "A cooperative buys solar lanterns at ₹400 and sells them at ₹460. Find the profit percentage.",
                "we_steps": [
                    "Compute profit: SP − CP = 460 − 400 = ₹60.",
                    "Use Cost Price ₹400 as the base: Profit% = (60 / 400) × 100.",
                    "Simplify: 60 / 4 = 15% profit.",
                ],
                "quiz_q": "Profit percentage is always calculated with respect to which value?",
                "opts": [
                    {"t": "Cost Price (CP)", "c": True, "m": ""},
                    {"t": "Selling Price (SP)", "c": False, "m": "Using SP instead of CP is a classic exam trap."},
                    {"t": "Marked Price (MP)", "c": False, "m": "Marked Price is used for discount%, not profit%."},
                ],
            },
            {
                "title": "Simple & Compound Interest for Self-Help Groups",
                "emoji": "🏦",
                "body": "Under compound interest, interest earned each period is added to the principal: A = P(1 + R/100)^n.",
                "sim_mult": 3,
                "we_q": "Find the amount on ₹1,000 for 2 years at 10% per annum compounded annually.",
                "we_steps": [
                    "After Year 1: A₁ = 1000 × (1 + 10/100) = ₹1,100.",
                    "After Year 2: A₂ = 1100 × (1 + 10/100) = ₹1,210.",
                    "Compound interest earned = 1210 − 1000 = ₹210.",
                ],
                "quiz_q": "Why is compound interest for 2 years greater than simple interest at the same rate?",
                "opts": [
                    {"t": "Year 2 interest is also earned on Year 1's interest", "c": True, "m": ""},
                    {"t": "The interest rate doubles in Year 2", "c": False, "m": "The rate stays the same; the principal base grows."},
                    {"t": "Simple interest subtracts principal each year", "c": False, "m": "Simple interest uses the original principal every year."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G09-SCI-CH08-FORCE-MOTION",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "science",
        "title": "Force, Newton's Laws of Motion & Momentum Conservation",
        "subtitle_hi": "बल, न्यूटन के गति के नियम और संवेग संरक्षण",
        "concepts": [
            {
                "title": "Balanced vs Unbalanced Forces & Inertia (First Law)",
                "emoji": "🛸",
                "body": "An object stays at rest or in uniform straight-line motion unless acted upon by an unbalanced external force. Mass is the measure of inertia.",
                "sim_mult": 3,
                "we_q": "Why does a passenger lean forward when a moving bus brakes suddenly?",
                "we_steps": [
                    "Before braking, both passenger and bus move forward at the same velocity.",
                    "Brakes apply a backward force to the bus floor, slowing the feet immediately.",
                    "By inertia of motion, the upper body continues moving forward.",
                ],
                "quiz_q": "Which object has greater inertia?",
                "opts": [
                    {"t": "A loaded 50 kg grain sack", "c": True, "m": ""},
                    {"t": "An empty 2 kg basket", "c": False, "m": "Inertia increases directly with mass."},
                    {"t": "Both have equal inertia", "c": False, "m": "Higher mass always means greater inertia."},
                ],
            },
            {
                "title": "Momentum & Newton's Second Law (F = ma)",
                "emoji": "🚀",
                "body": "Momentum is p = m × v. The rate of change of momentum is directly proportional to net applied force: F = m × a (in Newtons).",
                "sim_mult": 4,
                "we_q": "What net force is required to accelerate a 5 kg cart at 3 m/s²?",
                "we_steps": [
                    "Given mass m = 5 kg and acceleration a = 3 m/s².",
                    "Apply Newton's Second Law: F = m × a.",
                    "Compute F = 5 × 3 = 15 N.",
                ],
                "quiz_q": "Why does a cricketer pull their hands back while catching a fast ball?",
                "opts": [
                    {"t": "To increase stopping time and reduce impact force", "c": True, "m": ""},
                    {"t": "To increase the ball's momentum", "c": False, "m": "The momentum change is fixed by initial velocity."},
                    {"t": "To decrease stopping time", "c": False, "m": "Shorter stopping time causes a larger painful force."},
                ],
            },
            {
                "title": "Action-Reaction Pairs & Conservation of Momentum",
                "emoji": "⚖️",
                "body": "To every action there is an equal and opposite reaction acting on two different bodies, so total momentum of an isolated system stays constant.",
                "sim_mult": 5,
                "we_q": "Why do action and reaction forces never cancel each other out?",
                "we_steps": [
                    "Action force is exerted by Body A on Body B.",
                    "Reaction force is exerted by Body B on Body A.",
                    "Because they act on two different objects, they do not cancel on a single object.",
                ],
                "quiz_q": "In an isolated collision between two carts, what remains conserved?",
                "opts": [
                    {"t": "Total linear momentum of the system", "c": True, "m": ""},
                    {"t": "Velocity of each individual cart", "c": False, "m": "Individual velocities change during collision."},
                    {"t": "Acceleration of the heavier cart", "c": False, "m": "Total momentum m₁u₁ + m₂u₂ is conserved."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G09-SCI-CH10-WORK-ENERGY",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "science",
        "title": "Work, Kinetic & Potential Energy in Renewable Micro-Grids",
        "subtitle_hi": "नवीकरणीय माइक्रोग्रिड में कार्य, गतिज और स्थितिज ऊर्जा",
        "concepts": [
            {
                "title": "Scientific Definition of Work (W = F × s)",
                "emoji": "⚙️",
                "body": "Work is done when a force acts on an object and displaces it in the direction of the force: W = F × s (measured in Joules).",
                "sim_mult": 4,
                "we_q": "A student lifts a 20 N water bucket vertically by 3 m. How much work is done?",
                "we_steps": [
                    "Identify upward force F = 20 N and vertical displacement s = 3 m.",
                    "Apply W = F × s since force and displacement are in the same direction.",
                    "Compute W = 20 × 3 = 60 J.",
                ],
                "quiz_q": "If a person pushes a wall hard for 10 minutes but the wall does not move, how much scientific work is done?",
                "opts": [
                    {"t": "Zero Joules (displacement is 0)", "c": True, "m": ""},
                    {"t": "100 Joules", "c": False, "m": "Without displacement (s = 0), scientific work W = F × 0 = 0."},
                    {"t": "Depends on muscular tiredness", "c": False, "m": "Physics work requires non-zero displacement."},
                ],
            },
            {
                "title": "Kinetic Energy (½mv²) & Potential Energy (mgh)",
                "emoji": "🔋",
                "body": "Moving objects possess kinetic energy Ek = ½mv², while elevated water in an overhead Jal Seva tank stores gravitational potential energy Ep = mgh.",
                "sim_mult": 5,
                "we_q": "Find the potential energy of 10 kg of water stored 5 m high (take g = 10 m/s²).",
                "we_steps": [
                    "Given mass m = 10 kg, gravity g = 10 m/s², height h = 5 m.",
                    "Apply Ep = m × g × h.",
                    "Compute Ep = 10 × 10 × 5 = 500 J.",
                ],
                "quiz_q": "If the speed of a moving bicycle doubles, its kinetic energy becomes:",
                "opts": [
                    {"t": "4 times its original value", "c": True, "m": ""},
                    {"t": "2 times its original value", "c": False, "m": "Kinetic energy is proportional to v², so doubling v gives 2² = 4."},
                    {"t": "Half its original value", "c": False, "m": "Higher speed increases kinetic energy quadratically."},
                ],
            },
            {
                "title": "Law of Conservation of Energy & Power (P = W/t)",
                "emoji": "☀️",
                "body": "Energy can neither be created nor destroyed; it only transforms from one form to another. Power is the rate of doing work: P = W / t (in Watts).",
                "sim_mult": 3,
                "we_q": "A solar water pump performs 1,200 J of work in 20 seconds. What is its power output?",
                "we_steps": [
                    "Given work W = 1,200 J and time t = 20 s.",
                    "Apply the power formula: P = W ÷ t.",
                    "Compute P = 1200 ÷ 20 = 60 W.",
                ],
                "quiz_q": "What is the commercial unit of electrical energy used in household meters?",
                "opts": [
                    {"t": "Kilowatt-hour (kWh)", "c": True, "m": ""},
                    {"t": "Kilowatt (kW)", "c": False, "m": "Kilowatt is a unit of power, whereas kWh (power × time) measures energy."},
                    {"t": "Joule per second", "c": False, "m": "Joule per second is a Watt (power)."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G10-MATH-CH02-POLYNOMIALS",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "math",
        "title": "Polynomial Zeros, Parabolic Graphs & Quadratic Modeling",
        "subtitle_hi": "बहुपद के शून्यक, परवलयिक ग्राफ और द्विघात मॉडलिंग",
        "concepts": [
            {
                "title": "Degree of a Polynomial & Geometrical Meaning of Zeros",
                "emoji": "📈",
                "body": "The degree of a polynomial p(x) is the highest power of x. Geometrically, the real zeros of p(x) are the x-coordinates where the graph y = p(x) intersects the x-axis.",
                "sim_mult": 3,
                "we_q": "If the parabola y = p(x) crosses the x-axis at x = −2 and x = 3, what are its zeros?",
                "we_steps": [
                    "Zeros occur where y = p(x) = 0, which means points on the x-axis.",
                    "Read the x-coordinates of the x-axis intersections: (−2, 0) and (3, 0).",
                    "Therefore, the two zeros of p(x) are −2 and 3.",
                ],
                "quiz_q": "At most how many real zeros can a quadratic polynomial (degree 2) have?",
                "opts": [
                    {"t": "At most 2", "c": True, "m": ""},
                    {"t": "At most 3", "c": False, "m": "A degree-n polynomial can cross the x-axis at most n times."},
                    {"t": "Always exactly 1", "c": False, "m": "A linear polynomial has 1 zero; a quadratic has 0, 1, or 2 real zeros."},
                ],
            },
            {
                "title": "Sum & Product of Zeros (α + β = −b/a, αβ = c/a)",
                "emoji": "🧮",
                "body": "For a quadratic polynomial ax² + bx + c with zeros α and β, the sum of zeros is α + β = −b/a and the product of zeros is αβ = c/a.",
                "sim_mult": 4,
                "we_q": "Find the sum and product of the zeros of p(x) = x² − 5x + 6.",
                "we_steps": [
                    "Compare x² − 5x + 6 with ax² + bx + c: here a = 1, b = −5, c = 6.",
                    "Sum of zeros: α + β = −b/a = −(−5)/1 = 5.",
                    "Product of zeros: αβ = c/a = 6/1 = 6 (zeros are 2 and 3).",
                ],
                "quiz_q": "For 2x² + 8x + 6, what is the sum of its zeros?",
                "opts": [
                    {"t": "−4", "c": True, "m": ""},
                    {"t": "4", "c": False, "m": "Do not forget the minus sign in −b/a = −8/2 = −4."},
                    {"t": "3", "c": False, "m": "3 is the product of zeros (c/a = 6/2), not the sum."},
                ],
            },
            {
                "title": "Forming a Quadratic Polynomial from Given Zeros",
                "emoji": "🎯",
                "body": "Given the sum S = α + β and product P = αβ of zeros, a quadratic polynomial is formed by p(x) = x² − Sx + P.",
                "sim_mult": 5,
                "we_q": "Write a quadratic polynomial whose zeros have sum 4 and product 3.",
                "we_steps": [
                    "Given sum S = 4 and product P = 3.",
                    "Substitute into the template x² − (sum)x + (product).",
                    "Resulting polynomial: x² − 4x + 3.",
                ],
                "quiz_q": "Which quadratic polynomial has sum of zeros = 7 and product of zeros = 10?",
                "opts": [
                    {"t": "x² − 7x + 10", "c": True, "m": ""},
                    {"t": "x² + 7x + 10", "c": False, "m": "The middle term uses minus the sum: x² − (α+β)x + αβ."},
                    {"t": "x² − 10x + 7", "c": False, "m": "Keep sum as the coefficient of −x and product as the constant term."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G10-SCI-CH06-LIFE-PROCESSES-PHOTOSYNTHESIS",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "science",
        "title": "Life Processes, Stomatal Transpiration & Cellular Nutrition",
        "subtitle_hi": "जैव प्रक्रम, रंध्रीय वाष्पोत्सर्जन और कोशिकीय पोषण",
        "concepts": [
            {
                "title": "Autotrophic Nutrition & Stages of Photosynthesis",
                "emoji": "🌿",
                "body": "Green plants synthesize glucose using sunlight, chlorophyll, carbon dioxide, and water: 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂.",
                "sim_mult": 6,
                "we_q": "List the three core events that occur during photosynthesis in a leaf.",
                "we_steps": [
                    "Step 1: Absorption of light energy by chlorophyll in chloroplasts.",
                    "Step 2: Conversion of light energy into chemical energy and splitting of water (H₂O) into hydrogen and oxygen.",
                    "Step 3: Reduction of carbon dioxide (CO₂) to carbohydrates (glucose).",
                ],
                "quiz_q": "From which molecule does the oxygen gas released during photosynthesis come?",
                "opts": [
                    {"t": "Splitting of water (H₂O)", "c": True, "m": ""},
                    {"t": "Carbon dioxide (CO₂)", "c": False, "m": "Photolysis splits water molecules to release O₂."},
                    {"t": "Soil minerals", "c": False, "m": "Oxygen gas comes from water absorbed by roots."},
                ],
            },
            {
                "title": "Stomata, Guard Cells & Eco Seva Mulching",
                "emoji": "🍃",
                "body": "Tiny pores called stomata on leaf surfaces control gas exchange and transpiration. Guard cells swell with water to open the pore and shrink to close it.",
                "sim_mult": 4,
                "we_q": "How does mulching around native saplings conserve soil water in summer?",
                "we_steps": [
                    "Direct sun heats bare topsoil and accelerates evaporation.",
                    "A dry-leaf mulch layer shades the root zone and cools the soil.",
                    "Reduced evaporation keeps water available for guard cells and root uptake.",
                ],
                "quiz_q": "What causes stomatal pores to open during the day?",
                "opts": [
                    {"t": "Water flows into guard cells, making them turgid", "c": True, "m": ""},
                    {"t": "Guard cells lose all water and shrink", "c": False, "m": "Shrinking (flaccid) guard cells close the stomatal pore."},
                    {"t": "Roots stop absorbing water", "c": False, "m": "Turgor pressure inside guard cells opens the pore."},
                ],
            },
            {
                "title": "Aerobic vs Anaerobic Cellular Respiration",
                "emoji": "🫁",
                "body": "Glucose (6-carbon) breaks down into pyruvate (3-carbon) in the cytoplasm. With oxygen in mitochondria, pyruvate yields CO₂, H₂O, and 38 ATP.",
                "sim_mult": 3,
                "we_q": "Why do muscle cramps occur during sudden heavy exercise?",
                "we_steps": [
                    "During sprint exercise, oxygen supply to muscle cells falls short.",
                    "Pyruvate is converted anaerobically into 3-carbon lactic acid.",
                    "Accumulation of lactic acid in muscle tissue causes temporary cramps.",
                ],
                "quiz_q": "Where does the complete aerobic breakdown of pyruvate take place?",
                "opts": [
                    {"t": "Mitochondria", "c": True, "m": ""},
                    {"t": "Cytoplasm only", "c": False, "m": "Glycolysis happens in the cytoplasm; aerobic oxidation occurs in mitochondria."},
                    {"t": "Vacuole", "c": False, "m": "Mitochondria are the powerhouses of aerobic ATP synthesis."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "science",
        "title": "Electric Potential, Ohm's Law & Series-Parallel Solar Circuits",
        "subtitle_hi": "विद्युत विभव, ओम का नियम और सौर परिपथ",
        "concepts": [
            {
                "title": "Electric Current, Potential Difference & Ohm's Law (V = IR)",
                "emoji": "⚡",
                "body": "At constant temperature, the potential difference V across a conductor is directly proportional to current I flowing through it: V = I × R.",
                "sim_mult": 4,
                "we_q": "A 12 V solar battery is connected across a 4 Ω LED lamp resistor. Find the current.",
                "we_steps": [
                    "Given voltage V = 12 V and resistance R = 4 Ω.",
                    "Rearrange Ohm's Law: I = V ÷ R.",
                    "Compute I = 12 ÷ 4 = 3 A.",
                ],
                "quiz_q": "If resistance R is doubled while voltage V stays constant, what happens to the current I?",
                "opts": [
                    {"t": "It becomes half", "c": True, "m": ""},
                    {"t": "It doubles", "c": False, "m": "Current I = V/R is inversely proportional to resistance."},
                    {"t": "It stays unchanged", "c": False, "m": "Higher resistance reduces current flow for a fixed voltage."},
                ],
            },
            {
                "title": "Series vs Parallel Resistor Networks",
                "emoji": "🔌",
                "body": "In series, total resistance adds up (Rs = R₁ + R₂). In parallel, reciprocals add (1/Rp = 1/R₁ + 1/R₂) and each appliance gets full supply voltage.",
                "sim_mult": 3,
                "we_q": "Two 6 Ω solar classroom fans are wired in parallel. Find their equivalent resistance.",
                "we_steps": [
                    "Use the parallel formula: 1/Rp = 1/6 + 1/6 = 2/6 = 1/3.",
                    "Invert both sides to find Rp.",
                    "Equivalent resistance Rp = 3 Ω (less than either individual resistor).",
                ],
                "quiz_q": "Why are classroom lights and fans wired in parallel rather than series?",
                "opts": [
                    {"t": "Each appliance operates independently at full voltage", "c": True, "m": ""},
                    {"t": "If one bulb fails, all other appliances turn off", "c": False, "m": "That is a drawback of series wiring, not parallel."},
                    {"t": "Parallel wiring increases total resistance", "c": False, "m": "Parallel wiring reduces total equivalent resistance."},
                ],
            },
            {
                "title": "Joule's Law of Heating (H = I²Rt) & Electric Power (P = VI)",
                "emoji": "💡",
                "body": "Electrical power is P = V × I = I²R, and heat dissipated in a resistor over time t is H = I²Rt.",
                "sim_mult": 5,
                "we_q": "Find the power consumed by a 12 V, 2 A solar DC study lamp.",
                "we_steps": [
                    "Given potential difference V = 12 V and current I = 2 A.",
                    "Apply the electric power formula: P = V × I.",
                    "Compute P = 12 × 2 = 24 W.",
                ],
                "quiz_q": "According to Joule's law H = I²Rt, if current I triples, heat produced becomes:",
                "opts": [
                    {"t": "9 times as much", "c": True, "m": ""},
                    {"t": "3 times as much", "c": False, "m": "Heat scales with I², so 3² = 9 times."},
                    {"t": "One-third as much", "c": False, "m": "Heat increases with the square of current."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCVET-PSSCIVE-L3-IT-DIGITAL-VILLAGE-LEDGER",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "math",
        "title": "Offline-First Community Data Ledgers & Verifiable Impact Tables",
        "subtitle_hi": "ऑफ़लाइन-प्रथम सामुदायिक डेटा खाता और सत्यापन योग्य प्रभाव तालिका",
        "concepts": [
            {
                "title": "Structured Rows, Columns & Validation Rules",
                "emoji": "📋",
                "body": "In NCVET Level-3 Domestic Data Entry (SSC/Q0101), every village ledger row must have a unique ID, validated numeric fields, and zero blank mandatory cells.",
                "sim_mult": 4,
                "we_q": "Audit a 5-row Jal Seva water log where Row 3 has a negative litre reading (−40 L).",
                "we_steps": [
                    "Check range constraint: water saved must be ≥ 0 L.",
                    "Flag Row 3 (−40 L) as a sign-entry error against the paper receipt (40 L).",
                    "Correct Row 3 to +40 L and recompute the column sum.",
                ],
                "quiz_q": "Which check prevents a typist from entering text inside a 'Litres Saved' numeric column?",
                "opts": [
                    {"t": "Data-type and range validation rule", "c": True, "m": ""},
                    {"t": "Font color formatting", "c": False, "m": "Visual styling does not block invalid data entry."},
                    {"t": "Page margin setup", "c": False, "m": "Use field validation rules to enforce numeric input."},
                ],
            },
            {
                "title": "Checksum Totals & Cross-Foot Balancing",
                "emoji": "🧮",
                "body": "A ledger table is cross-balanced when the sum of row totals equals the sum of column totals.",
                "sim_mult": 5,
                "we_q": "Three cohorts saved 120 L, 150 L, and 130 L of water. Verify the batch total.",
                "we_steps": [
                    "Add Cohort A + Cohort B: 120 + 150 = 270 L.",
                    "Add Cohort C: 270 + 130 = 400 L.",
                    "Confirm that the summary row matches 400 L before syncing.",
                ],
                "quiz_q": "What does a mismatch between the row-sum and column-sum in a spreadsheet indicate?",
                "opts": [
                    {"t": "A formula range or data-entry error in at least one cell", "c": True, "m": ""},
                    {"t": "The computer screen needs cleaning", "c": False, "m": "Row and column sums must always be mathematically identical."},
                    {"t": "The file size is too small", "c": False, "m": "Cross-foot mismatches always signal a calculation or range omission."},
                ],
            },
            {
                "title": "Tamper-Evident Offline Sync & Receipt Hashing",
                "emoji": "🔒",
                "body": "When rural centres operate offline, each batch export records a cryptographic SHA-256 digest so any accidental edit during USB or LAN sync is detected immediately.",
                "sim_mult": 3,
                "we_q": "Why do we store a SHA-256 hash alongside each offline cohort export pack?",
                "we_steps": [
                    "Compute the hash of the JSON payload before saving to local storage.",
                    "Recompute the hash on the Centre Server upon upload.",
                    "If both hashes match, the ledger batch is verified intact.",
                ],
                "quiz_q": "If even one digit in a ledger file changes, what happens to its SHA-256 hash?",
                "opts": [
                    {"t": "The hash changes completely, alerting the verifier", "c": True, "m": ""},
                    {"t": "The hash stays 99% identical", "c": False, "m": "Cryptographic hashes exhibit the avalanche effect."},
                    {"t": "Nothing changes", "c": False, "m": "Any byte change produces a completely different SHA-256 digest."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCVET-PSSCIVE-L4-AGRI-PRECISION-DRIP-JAL-SEVA",
        "pack_dir": "g3_10chapter_pack",
        "grade": 8,
        "subject": "science",
        "title": "Precision Drip Irrigation Hydraulics & Soil Moisture Budgeting",
        "subtitle_hi": "सटीक ड्रिप सिंचाई हाइड्रोलिक्स और मृदा नमी बजट",
        "concepts": [
            {
                "title": "Emitter Discharge Rate & Irrigation Duty Cycle",
                "emoji": "🚿",
                "body": "In NCVET Level-4 Micro-Irrigation (AGR/Q4301), total water delivered equals emitter flow rate (L/hr) multiplied by number of emitters and operating hours.",
                "sim_mult": 4,
                "we_q": "A sapling bed has 10 emitters rated at 2 L/hr each, run for 3 hours. Find total water used.",
                "we_steps": [
                    "Calculate hourly bed flow: 10 emitters × 2 L/hr = 20 L/hr.",
                    "Multiply by 3 operating hours: 20 L/hr × 3 hr.",
                    "Total root-zone delivery = 60 L with minimal evaporation loss.",
                ],
                "quiz_q": "If 8 emitters each deliver 4 L/hr for 2 hours, how much water is supplied?",
                "opts": [
                    {"t": "64 L", "c": True, "m": ""},
                    {"t": "32 L", "c": False, "m": "32 L is for 1 hour; multiply by 2 hours to get 64 L."},
                    {"t": "14 L", "c": False, "m": "Multiply emitters × flow rate × hours (8 × 4 × 2)."},
                ],
            },
            {
                "title": "Head Loss, Filter Cleaning & Pressure Uniformity",
                "emoji": "🔧",
                "body": "Clogged screen or disc filters cause a pressure drop across the mainline, starving tail-end drippers of uniform flow.",
                "sim_mult": 3,
                "we_q": "Inlet pressure before the filter is 2.0 bar and outlet pressure drops to 1.1 bar. What should the technician do?",
                "we_steps": [
                    "Compute pressure differential: ΔP = 2.0 − 1.1 = 0.9 bar (> 0.5 bar threshold).",
                    "Shut off the solar pump valve and open the filter flush port.",
                    "Rinse the filter mesh until ΔP returns below 0.2 bar.",
                ],
                "quiz_q": "What does a large pressure drop between the filter inlet and outlet gauges indicate?",
                "opts": [
                    {"t": "The filter mesh is clogged and needs flushing", "c": True, "m": ""},
                    {"t": "The water tank is overflowing", "c": False, "m": "A high ΔP across a filter is the classic sign of sediment clogging."},
                    {"t": "The solar panel is dirty", "c": False, "m": "Inlet pressure is already 2.0 bar; the obstruction is inside the filter."},
                ],
            },
            {
                "title": "Water-Use Efficiency vs Flood Irrigation (Jal Seva)",
                "emoji": "🌱",
                "body": "Flood irrigation loses 50–60% of water to runoff and evaporation, whereas root-zone drip irrigation achieves 85–95% water application efficiency.",
                "sim_mult": 5,
                "we_q": "Flooding a plot takes 500 L, while precision drip needs only 200 L. How much Jal Seva water is saved?",
                "we_steps": [
                    "Subtract drip usage from flood usage: 500 L − 200 L = 300 L saved.",
                    "Compute percentage saved: (300 / 500) × 100%.",
                    "Result: 60% water conserved per irrigation cycle.",
                ],
                "quiz_q": "Why does drip irrigation reduce weed growth between crop rows?",
                "opts": [
                    {"t": "Water is delivered only to the crop root zone, keeping inter-row soil dry", "c": True, "m": ""},
                    {"t": "Drip emitters spray herbicide automatically", "c": False, "m": "Targeted root-zone moisture starves inter-row weeds naturally."},
                    {"t": "Drip water is boiling hot", "c": False, "m": "Water temperature is ambient; targeted placement stops weeds."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCVET_PSSCIVE_L3_IT_DataEntry_v5",
        "pack_dir": "g36_ncvet_psscive_pack",
        "grade": 8,
        "subject": "math",
        "title": "NCVET Level 3 — Domestic Data Entry & Digital Village Ledger",
        "subtitle_hi": "एनसीवीईटी स्तर 3 — घरेलू डेटा एंट्री और डिजिटल ग्राम बहीखाता",
        "concepts": [
            {
                "title": "Keyboard Ergonomics, Accuracy & Net Typing Speed",
                "emoji": "⌨️",
                "body": "Net WPM deducts error penalties from Gross WPM. In community ledger entry, 100% numeric accuracy is more important than raw speed.",
                "sim_mult": 4,
                "we_q": "A student types 200 words in 5 minutes with 0 errors. Find the WPM.",
                "we_steps": [
                    "Given total words = 200 and duration = 5 minutes.",
                    "Divide words by minutes: 200 ÷ 5.",
                    "Verified typing speed = 40 WPM at 100% accuracy.",
                ],
                "quiz_q": "Before submitting a village scholarship table, how should numeric ID columns be verified?",
                "opts": [
                    {"t": "Cross-check digit count and checksum totals against source forms", "c": True, "m": ""},
                    {"t": "Skip verification to save time", "c": False, "m": "Single-digit ID errors block student scholarship disbursements."},
                    {"t": "Sort rows randomly", "c": False, "m": "Always validate against source records."},
                ],
            },
            {
                "title": "Spreadsheet Formulas: SUM, AVERAGE & COUNTIF",
                "emoji": "📊",
                "body": "Spreadsheet functions automate cohort reporting: =SUM(B2:B11) totals values, while =AVERAGE(B2:B11) computes the arithmetic mean.",
                "sim_mult": 5,
                "we_q": "Five learners scored 18, 20, 16, 22, and 24 coins. Find the sum and average.",
                "we_steps": [
                    "Compute SUM: 18 + 20 + 16 + 22 + 24 = 100 coins.",
                    "Divide by count (5 learners): 100 ÷ 5.",
                    "Average score = 20 coins per learner.",
                ],
                "quiz_q": "Every formula in a standard spreadsheet cell must begin with which symbol?",
                "opts": [
                    {"t": "Equals sign (=)", "c": True, "m": ""},
                    {"t": "Hash sign (#)", "c": False, "m": "Without '=', the cell treats the text as a plain label."},
                    {"t": "Question mark (?)", "c": False, "m": "Formulas always start with '='."},
                ],
            },
            {
                "title": "Offline Backup & PIN-Guarded Store Reconciliation",
                "emoji": "🔐",
                "body": "Centre facilitators reconcile student reward redemptions using PIN-guarded logs and daily SQLite/JSON backups.",
                "sim_mult": 3,
                "we_q": "A student has 80 Aasha Coins and redeems a notebook worth 50 Coins. What balance remains?",
                "we_steps": [
                    "Verify initial wallet balance = 80 Coins ≥ item cost (50 Coins).",
                    "Deduct item cost: 80 − 50 = 30 Coins.",
                    "Record transaction in the append-only store ledger.",
                ],
                "quiz_q": "Why must wallet redemptions check `balance >= cost` before deducting coins?",
                "opts": [
                    {"t": "To enforce coin conservation and prevent negative balances", "c": True, "m": ""},
                    {"t": "To make the screen brighter", "c": False, "m": "Ledger conservation prevents double-spending."},
                    {"t": "To delete student progress", "c": False, "m": "XP and mastery stay intact; only spendable coins are deducted."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCVET_PSSCIVE_L4_Agri_SolarDrip_v5",
        "pack_dir": "g36_ncvet_psscive_pack",
        "grade": 8,
        "subject": "science",
        "title": "NCVET Level 4 — Solar Micro-Irrigation & Jal Seva Technician",
        "subtitle_hi": "एनसीवीईटी स्तर 4 — सौर सूक्ष्म सिंचाई और जल सेवा तकनीशियन",
        "concepts": [
            {
                "title": "Solar PV Array Tilt & Pump Flow Matching",
                "emoji": "☀️",
                "body": "Setting the solar panel tilt angle equal to the local latitude maximizes midday irradiance and DC water pump discharge.",
                "sim_mult": 4,
                "we_q": "A 500 W solar pump delivers 30 L/min at peak sun. How much water is pumped in 40 minutes?",
                "we_steps": [
                    "Identify flow rate Q = 30 L/min and time t = 40 min.",
                    "Multiply Q × t: 30 × 40.",
                    "Total water pumped = 1,200 L.",
                ],
                "quiz_q": "What happens to solar pump flow if dust covers 30% of the PV panel surface?",
                "opts": [
                    {"t": "Current output drops, reducing pump flow rate", "c": True, "m": ""},
                    {"t": "Pump speed increases", "c": False, "m": "Shading or dust reduces photovoltaic current."},
                    {"t": "Water pressure doubles", "c": False, "m": "Regular panel wiping restores rated pump discharge."},
                ],
            },
            {
                "title": "Lateral Line Layout & Emitter Spacing",
                "emoji": "📏",
                "body": "Matching emitter spacing to crop root-zone diameter ensures continuous wetted strips without deep percolation waste.",
                "sim_mult": 3,
                "we_q": "How many emitters spaced every 0.5 m fit along a 15 m vegetable lateral line?",
                "we_steps": [
                    "Given lateral length L = 15 m and spacing s = 0.5 m.",
                    "Divide length by spacing: 15 ÷ 0.5.",
                    "Result: 30 emitters along the lateral.",
                ],
                "quiz_q": "Sandy soil drains faster than clay soil. How should emitter flow rate be chosen for sandy soil?",
                "opts": [
                    {"t": "Higher discharge rate with shorter, more frequent pulses", "c": True, "m": ""},
                    {"t": "Once a month flood watering", "c": False, "m": "Long single floods sink below sandy root zones."},
                    {"t": "Zero water needed", "c": False, "m": "Pulse irrigation keeps moisture within the root zone."},
                ],
            },
            {
                "title": "Jal Seva Water Audit & Community Maintenance Log",
                "emoji": "💧",
                "body": "Weekly inspection of lateral end-caps, flush valves, and moisture sensors keeps community micro-irrigation efficiency above 90%.",
                "sim_mult": 5,
                "we_q": "Why do technicians open lateral end-caps for 30 seconds each week?",
                "we_steps": [
                    "Fine silt that passes the main filter settles at the far end of lateral pipes.",
                    "Opening the end-cap flushes accumulated silt out with water velocity.",
                    "Closing the cap restores uniform pressure to all emitters.",
                ],
                "quiz_q": "Which tool directly measures root-zone soil moisture tension?",
                "opts": [
                    {"t": "Tensiometer", "c": True, "m": ""},
                    {"t": "Thermometer", "c": False, "m": "A thermometer measures temperature, not soil moisture tension."},
                    {"t": "Ammeter", "c": False, "m": "An ammeter measures electric current."},
                ],
            },
        ],
    },
    {
        "chapter_id": "NCVET_PSSCIVE_L4_Food_SolarDehydrator_v5",
        "pack_dir": "g36_ncvet_psscive_pack",
        "grade": 8,
        "subject": "science",
        "title": "NCVET Level 4 — Rural Solar Food Dehydrator Unit Operator",
        "subtitle_hi": "एनसीवीईटी स्तर 4 — ग्रामीण सौर खाद्य निर्जलीकरण इकाई ऑपरेटर",
        "concepts": [
            {
                "title": "Moisture Content Reduction & Safe Water Activity",
                "emoji": "🥭",
                "body": "Solar dehydration removes moisture from fresh produce (80–90% water) down to 10–15% so spoilage microbes cannot grow.",
                "sim_mult": 3,
                "we_q": "A 15 kg batch of fresh mango slices loses 12 kg of water during solar drying. What is the dry yield weight?",
                "we_steps": [
                    "Given initial fresh weight = 15 kg and water evaporated = 12 kg.",
                    "Subtract evaporated water: 15 kg − 12 kg.",
                    "Final dried mango yield = 3 kg (20% of fresh weight).",
                ],
                "quiz_q": "Why must warm humid air be continuously vented out of a solar dehydrator cabinet?",
                "opts": [
                    {"t": "So saturated air is replaced by dry warm air to keep evaporation going", "c": True, "m": ""},
                    {"t": "To let rain enter the trays", "c": False, "m": "Vents are hooded against rain while exhausting humid air."},
                    {"t": "To freeze the fruit slices", "c": False, "m": "Stagnant humid air halts dehydration and causes mold."},
                ],
            },
            {
                "title": "Temperature Control & Preventing Case Hardening",
                "emoji": "🌡️",
                "body": "Maintaining cabinet temperature between 50 °C and 60 °C dries produce evenly without scorching vitamins or sealing the outer skin (case hardening).",
                "sim_mult": 4,
                "we_q": "What happens if drying temperature spikes above 80 °C on the first hour?",
                "we_steps": [
                    "Excessive surface heat rapidly forms a hard, dry crust on the fruit slice.",
                    "Internal moisture becomes trapped behind the sealed crust (case hardening).",
                    "Trapped internal moisture later causes spoilage during storage.",
                ],
                "quiz_q": "What is the ideal tray-loading practice for uniform airflow?",
                "opts": [
                    {"t": "Single layer of uniform-thickness slices with small gaps between pieces", "c": True, "m": ""},
                    {"t": "Piling slices 10 cm deep in a heap", "c": False, "m": "Deep heaps block airflow and rot in the center."},
                    {"t": "Mixing whole uncut fruits with thin slices", "c": False, "m": "Uniform slice thickness ensures all pieces finish drying together."},
                ],
            },
            {
                "title": "Hygienic Packaging & Cooperative Unit Economics",
                "emoji": "📦",
                "body": "Cooling dried produce before sealing in food-grade moisture-barrier pouches prevents condensation and extends shelf life to 6–12 months.",
                "sim_mult": 5,
                "we_q": "Why must dried slices cool to room temperature before sealing in pouches?",
                "we_steps": [
                    "Warm slices still release trace water vapor.",
                    "Sealing warm slices traps vapor that condenses into liquid droplets on the pouch wall.",
                    "Cooling in a clean dry chamber prevents condensation and mold.",
                ],
                "quiz_q": "If a cooperative spends ₹600 on fresh produce and sells 20 pouches at ₹45 each, what is the net surplus?",
                "opts": [
                    {"t": "₹300", "c": True, "m": ""},
                    {"t": "₹900", "c": False, "m": "₹900 is total revenue (20 × 45); subtract the ₹600 cost to get ₹300."},
                    {"t": "₹150", "c": False, "m": "Revenue is 20 × ₹45 = ₹900, minus ₹600 cost = ₹300."},
                ],
            },
        ],
    },
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_spec_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    cid = entry["chapter_id"]
    slug = "".join(ch for ch in cid.lower() if ch.isalnum())[:16]
    we_dict: dict[str, Any] = {}
    solve_dict: dict[str, Any] = {}
    nodes: list[dict[str, Any]] = []

    for idx, c in enumerate(entry["concepts"], 1):
        wkey = f"w{idx}"
        skey = f"s{idx}"
        we_dict[wkey] = {
            "title": f"Worked Example {idx}: {c['title']}",
            "question": c["we_q"],
            "steps": [
                {"text": st, "c": "green" if s_i == len(c["we_steps"]) - 1 else "blue", "final": s_i == len(c["we_steps"]) - 1}
                for s_i, st in enumerate(c["we_steps"])
            ],
            "check": {
                "q": c["quiz_q"],
                "opts": c["opts"],
            },
        }
        solve_dict[skey] = {
            "title": f"Guided Solve {idx}: {c['title']}",
            "question": c["we_q"],
            "steps": [
                {"prompt": st, "type": "input", "answer": "Verified"}
                for st in c["we_steps"]
            ],
        }
        nodes.append({
            "title": c["title"],
            "emoji": c["emoji"],
            "steps": [
                {"t": "text", "title": c["title"], "body": c["body"], "xp": 5},
                {
                    "t": "ix_slider",
                    "title": f"Interactive Lab: {c['title']}",
                    "instruction": f"Move the slider to test how {c['title']} scales.",
                    "parts": idx + 1,
                    "target_num": c["sim_mult"],
                    "xp": 10,
                },
                {"t": "worked", "we": f"WE.{wkey}", "xp": 10},
                {"t": "solve", "sl": f"SOLVE.{skey}", "xp": 10},
                {
                    "t": "quiz",
                    "q": {"q": c["quiz_q"], "opts": c["opts"]},
                    "xp": 15,
                },
            ],
        })

    return {
        "chapter": {
            "title": entry["title"],
            "subject": entry["subject"],
            "grade": entry["grade"],
            "storage_key": f"aasha_{slug}_v5",
            "emoji": "📘",
        },
        "BADGES": [
            {"id": "b1", "name": "Explorer", "ic": "🧭", "desc": f"Completed {entry['title']} concepts"},
            {"id": "b2", "name": "Simulator", "ic": "⚙️", "desc": "Tested all interactive sliders"},
            {"id": "b3", "name": "Arena Champion", "ic": "🏆", "desc": "Cleared Aasha Arena"},
        ],
        "WE": we_dict,
        "SOLVE": solve_dict,
        "NODES": nodes,
    }


def compile_and_certify_13_chapter_learn_arena_batch() -> dict[str, Any]:
    tpl_dir = PIPELINE_ROOT / "template"
    cfg_dir = PIPELINE_ROOT / "config"
    qa_runner = PIPELINE_ROOT / "qa" / "run_qa.js"

    assembler = LearnArenaAssembler(
        learn_template_path=tpl_dir / "aasha-learn-template.html",
        arena_template_path=tpl_dir / "aasha-arena-template.html",
        master_pack_path=cfg_dir / "lle_master_pack.json",
        defaults_path=cfg_dir / "defaults_expanded_v2.json",
    )

    results: list[dict[str, Any]] = []
    total_qa_checks = 0
    total_qa_passed = 0

    for entry in CANONICAL_13_CHAPTER_BATCH:
        cid = entry["chapter_id"]
        out_dir = PIPELINE_ROOT / "output" / entry["pack_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        spec = build_spec_from_entry(entry)
        learn_html, arena_html = assembler.assemble(spec, {})

        base_stem = cid.replace("_v5", "")
        learn_path = out_dir / f"{base_stem}_Learning.html"
        arena_path = out_dir / f"{base_stem}_Arena.html"
        spec_path = out_dir / f"{base_stem}_spec.json"

        learn_path.write_text(learn_html, encoding="utf-8")
        arena_path.write_text(arena_html, encoding="utf-8")
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        pair_audit: dict[str, Any] = {"chapter_id": cid, "title": entry["title"]}
        for mode, hpath in [("learn", learn_path), ("arena", arena_path)]:
            for attempt in range(3):
                proc = subprocess.run(
                    ["node", str(qa_runner), str(hpath), mode],
                    capture_output=True, text=True, check=True,
                )
                rep = json.loads(proc.stdout)
                if rep.get("passed"):
                    total_qa_checks += rep["checks_total"]
                    total_qa_passed += rep["checks_passed"]
                    pair_audit[f"{mode}_file"] = str(hpath.relative_to(REPO_ROOT))
                    pair_audit[f"{mode}_size_bytes"] = hpath.stat().st_size
                    pair_audit[f"{mode}_sha256"] = _sha256_file(hpath)
                    pair_audit[f"{mode}_qa"] = f"{rep['checks_passed']}/{rep['checks_total']}"
                    break
                if attempt < 2 and Orchestrator._self_heal_html(hpath):
                    continue
                raise RuntimeError(f"QA failed for {hpath.name} ({mode}): {rep.get('failures')}")

        results.append(pair_audit)

    # Update SQLite catalogue teas_content.db + teas_content.db.gz with Learn & Arena columns
    db_path = PIPELINE_ROOT / "output" / "g3_10chapter_pack" / "teas_content.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(chapters)").fetchall()}
    for col_def in [
        ("learn_file", "TEXT DEFAULT ''"),
        ("arena_file", "TEXT DEFAULT ''"),
        ("learn_sha256", "TEXT DEFAULT ''"),
        ("arena_sha256", "TEXT DEFAULT ''"),
        ("learn_size_bytes", "INTEGER DEFAULT 0"),
        ("arena_size_bytes", "INTEGER DEFAULT 0"),
    ]:
        if col_def[0] not in existing_cols:
            cur.execute(f"ALTER TABLE chapters ADD COLUMN {col_def[0]} {col_def[1]}")

    for r in results:
        cur.execute(
            """
            UPDATE chapters
               SET learn_file = ?, arena_file = ?, learn_sha256 = ?, arena_sha256 = ?,
                   learn_size_bytes = ?, arena_size_bytes = ?
             WHERE chapter_id = ? OR file_name LIKE ?
            """,
            (
                r["learn_file"],
                r["arena_file"],
                r["learn_sha256"],
                r["arena_sha256"],
                r["learn_size_bytes"],
                r["arena_size_bytes"],
                r["chapter_id"],
                f"%{r['chapter_id']}%",
            ),
        )
    conn.commit()
    conn.close()

    gz_path = PIPELINE_ROOT / "output" / "g3_10chapter_pack" / "teas_content.db.gz"
    with open(db_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    # Update PWA sw_cache_manifest.json with the 26 Learn & Arena modules
    sw_manifest_path = REPO_ROOT / "Aasha-AI" / "aasha-student-pwa" / "src" / "sw_cache_manifest.json"
    if sw_manifest_path.exists():
        sw_data = json.loads(sw_manifest_path.read_text(encoding="utf-8"))
        sw_data["learn_arena_modules"] = results
        sw_data["learn_arena_count"] = len(results) * 2
        sw_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        sw_manifest_path.write_text(json.dumps(sw_data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "chapters_compiled": len(results),
        "total_html5_modules_generated": len(results) * 2,
        "total_qa_checks_passed": f"{total_qa_passed}/{total_qa_checks}",
        "sqlite_db_bytes": db_path.stat().st_size,
        "sqlite_gz_bytes": gz_path.stat().st_size,
        "modules": results,
    }
    manifest_out = REPO_ROOT / "PHASE_E_13CHAPTER_LEARN_ARENA_BATCH_MANIFEST.json"
    manifest_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    out = compile_and_certify_13_chapter_learn_arena_batch()
    print(json.dumps({k: v for k, v in out.items() if k != "modules"}, indent=2))
