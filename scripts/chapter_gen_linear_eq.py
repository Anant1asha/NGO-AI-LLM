"""AASHA AIOS — Class 8 Math Chapter 2: Linear Equations in One Variable Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "equation": {"h": "समीकरण", "p": "इक्वेशन"},
    "equations": {"h": "समीकरण", "p": "इक्वेशन्स"},
    "variable": {"h": "चर (अज्ञात राशि जैसे x)", "p": "वेरिएबल"},
    "constant": {"h": "अचर (स्थिर संख्या)", "p": "कॉन्स्टेंट"},
    "linear": {"h": "रैखिक (घात 1 वाला)", "p": "लीनियर"},
    "balance": {"h": "तराज़ू / संतुलन", "p": "बैलेंस"},
    "scale": {"h": "तराज़ू का पलड़ा", "p": "स्केल"},
    "transposition": {"h": "पक्षांतरण (पक्ष बदलना)", "p": "ट्रांसपोज़िशन"},
    "transpose": {"h": "पक्ष बदलना", "p": "ट्रांसपोज़"},
    "solution": {"h": "हल (समीकरण का मूल)", "p": "सॉल्यूशन"},
    "root": {"h": "मूल", "p": "रूट"},
    "equality": {"h": "समता / बराबरी (=)", "p": "इक्वलिटी"},
    "sides": {"h": "पक्ष (बायाँ और दायाँ)", "p": "साइड्स"},
    "left": {"h": "बायाँ पक्ष (LHS)", "p": "लेफ्ट"},
    "right": {"h": "दायाँ पक्ष (RHS)", "p": "राइट"},
    "isolate": {"h": "अलग करना", "p": "आइसोलेट"},
    "parentheses": {"h": "कोष्ठक (ब्रैकेट)", "p": "पैरेंथीसिस"},
    "cross-multiplication": {"h": "वज्र-गुणन (तिरछा गुणा)", "p": "क्रॉस-मल्टिप्लिकेशन"},
    "riddle": {"h": "पहेली", "p": "रिडल"},
}

EXTRA_PHRASES = {
    "Linear Equations in One Variable — Dynamic Balance Scale & Transposition": "एक चर वाले रैखिक समीकरण — गतिशील तराज़ू और पक्षांतरण",
    "Mathematics · Class 8 · Chapter 2": "गणित · कक्षा 8 · अध्याय 2",
    "An algebraic equation is like a vegetable vendor's traditional two-pan balance scale. The '=' sign means both pans are in perfect horizontal equilibrium.": "एक बीजीय समीकरण सब्ज़ी विक्रेता के पारंपरिक दो पलड़ों वाले तराज़ू जैसा होता है। '=' चिह्न का अर्थ है दोनों पलड़े पूर्ण क्षैतिज संतुलन में हैं।",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "Whatever you add, subtract, multiply, or divide on the left side, you must do to the right side to keep the scale balanced.": "बाएँ पक्ष में आप जो भी जोड़ते, घटाते, गुणा या भाग करते हैं, तराज़ू को संतुलित रखने के लिए आपको दाएँ पक्ष में भी वही करना होगा।",
    "What Makes an Equation 'Linear'?": "समीकरण को 'रैखिक' क्या बनाता है?",
    "An algebraic expression becomes an EQUATION when it contains an equality sign (=). It is LINEAR when the highest exponent (power) of the variable is strictly 1. 2x + 5 = 15 is linear; x² + 1 = 10 is not!": "एक बीजीय व्यंजक तब समीकरण (Equation) बनता है जब उसमें समता का चिह्न (=) हो। यह रैखिक (Linear) तब होता है जब चर की उच्चतम घात 1 हो। 2x + 5 = 15 रैखिक है; x² + 1 = 10 नहीं!",
    "The Golden Rule of the Balance Scale": "तराज़ू का स्वर्णिम नियम",
    "Imagine the '=' sign is the fulcrum of a balance scale. Left Hand Side (LHS) sits on the left pan, Right Hand Side (RHS) on the right pan. If 2x + 3 = 11, the pans balance horizontally.": "कल्पना कीजिए कि '=' चिह्न तराज़ू का केंद्रीय बिंदु है। बायाँ पक्ष (LHS) बाएँ पलड़े पर है, दायाँ पक्ष (RHS) दाएँ पलड़े पर। यदि 2x + 3 = 11 है, तो दोनों पलड़े क्षैतिज संतुलन में हैं।",
    "Try it: Balance the Scale": "करके देखें: तराज़ू को संतुलित करें",
    "Adjust the weight of x and watch the balance beam react. When the LHS exactly equals RHS, the beam levels out with a green equilibrium glow.": "x का मान बदलें और देखें कि तराज़ू का बीम कैसे प्रतिक्रिया करता है। जब LHS ठीक RHS के बराबर होता है, तो बीम हरी चमक के साथ संतुलित हो जाता है।",
    "The Method of Transposition (पक्षांतरण)": "पक्षांतरण की विधि",
    "Instead of adding or subtracting numbers on both sides, we can 'transpose' a term across the '=' sign. When a term crosses the border, its operation flips: + becomes -, and × becomes ÷!": "दोनों पक्षों में संख्याएँ जोड़ने या घटाने के बजाय, हम किसी पद को '=' के पार 'पक्षांतरित' कर सकते हैं। जब कोई पद सीमा पार करता है, तो उसका चिह्न बदल जाता है: + बनता है -, और × बनता है ÷!",
    "Solving: 2x - 3 = 7 Step-by-Step": "हल: 2x - 3 = 7 चरण-दर-चरण",
    "Step 1: Transpose -3 to the RHS as +3: 2x = 7 + 3 = 10. Step 2: Transpose multiplying 2 to division: x = 10 ÷ 2 = 5. Check: 2(5) - 3 = 7. Verified!": "स्टेप 1: -3 को RHS में +3 के रूप में ले जाएं: 2x = 7 + 3 = 10। स्टेप 2: गुणा वाले 2 को भाग में ले जाएं: x = 10 ÷ 2 = 5। जाँच: 2(5) - 3 = 7। सत्यापित!",
    "Variables on Both Sides": "दोनों पक्षों में चर (Variables)",
    "What if the unknown appears on both pans, like 5x - 3 = 3x + 7? Group all variable terms on the LHS and all numerical constants on the RHS! 5x - 3x = 7 + 3 -> 2x = 10 -> x = 5.": "यदि अज्ञात दोनों पलड़ों पर दिखाई दे, जैसे 5x - 3 = 3x + 7? सभी चर पदों को LHS में और सभी अचर संख्याओं को RHS में ले जाएं! 5x - 3x = 7 + 3 -> 2x = 10 -> x = 5।",
    "Equations with Parentheses (Brackets)": "कोष्ठक (Brackets) वाले समीकरण",
    "Always apply the Distributive Property before moving terms: a(b + c) = ab + ac. In 3(x - 2) + 5 = 20, first expand: 3x - 6 + 5 = 20 -> 3x - 1 = 20 -> 3x = 21 -> x = 7.": "पदों को हिलाने से पहले हमेशा वितरण नियम लागू करें: a(b + c) = ab + ac। 3(x - 2) + 5 = 20 में, पहले कोष्ठक खोलें: 3x - 6 + 5 = 20 -> 3x - 1 = 20 -> 3x = 21 -> x = 7।",
    "Cross-Multiplication for Fraction Forms": "भिन्न रूपों के लिए वज्र-गुणन (Cross-Multiplication)",
    "When an equation is in the fractional form (ax + b) / (cx + d) = p / q, multiply diagonally: q(ax + b) = p(cx + d). This instantly converts a fraction into a simple flat linear line!": "जब समीकरण (ax + b) / (cx + d) = p / q के भिन्न रूप में हो, तो तिरछा गुणा करें: q(ax + b) = p(cx + d)। यह तुरंत भिन्न को एक साधारण सपाट रैखिक रेखा में बदल देता है!",
    "Worked example — The Age Riddle": "हल किया गया उदाहरण — उम्र की पहेली",
    "Rahul's father is 3 times as old as Rahul. The sum of their ages is 56 years. Find Rahul's age.": "राहुल के पिता की आयु राहुल की आयु से 3 गुना है। उनकी आयु का योग 56 वर्ष है। राहुल की आयु ज्ञात कीजिए।",
    "Step 1: Let Rahul's age be x years. Father's age is 3x years.": "स्टेप 1: मान लीजिए राहुल की आयु x वर्ष है। पिता की आयु 3x वर्ष है।",
    "Step 2: Set up the equation: x + 3x = 56.": "स्टेप 2: समीकरण बनाएं: x + 3x = 56।",
    "Step 3: Combine like terms: 4x = 56.": "स्टेप 3: सजातीय पदों को जोड़ें: 4x = 56।",
    "Step 4: Divide both sides by 4: x = 56 ÷ 4 = 14.": "स्टेप 4: दोनों पक्षों को 4 से भाग दें: x = 56 ÷ 4 = 14।",
    "Rahul is 14 years old, and his father is 42 years old (14 × 3 = 42; 14 + 42 = 56).": "राहुल की आयु 14 वर्ष है, और उनके पिता की 42 वर्ष (14 × 3 = 42; 14 + 42 = 56)।",
    "Worked example — Solving with Brackets": "हल किया गया उदाहरण — कोष्ठक हल करना",
    "Solve: 8x + 4 = 3(x - 1) + 7.": "हल कीजिए: 8x + 4 = 3(x - 1) + 7।",
    "Step 1: Expand brackets on RHS: 8x + 4 = 3x - 3 + 7.": "स्टेप 1: RHS पर कोष्ठक खोलें: 8x + 4 = 3x - 3 + 7।",
    "Step 2: Simplify RHS constants: 8x + 4 = 3x + 4.": "स्टेप 2: RHS अचरों को सरल करें: 8x + 4 = 3x + 4।",
    "Step 3: Transpose 3x to LHS and 4 to RHS: 8x - 3x = 4 - 4.": "स्टेप 3: 3x को LHS और 4 को RHS में पक्षांतरित करें: 8x - 3x = 4 - 4।",
    "Step 4: 5x = 0 -> x = 0 ÷ 5 = 0.": "स्टेप 4: 5x = 0 -> x = 0 ÷ 5 = 0।",
    "Final solution is x = 0.": "अंतिम हल x = 0 है।",
    "Solve: 3x - 5 = 16. What is x?": "हल कीजिए: 3x - 5 = 16। x का मान क्या है?",
    "7": "7",
    "5": "5",
    "9": "9",
    "Transpose -5: 3x = 16 + 5 = 21. Divide by 3: x = 21 ÷ 3 = 7.": "-5 का पक्षांतरण करें: 3x = 16 + 5 = 21। 3 से भाग दें: x = 21 ÷ 3 = 7।",
    "What is the first step in solving (x + 1) / (2x + 3) = 3/8?": "(x + 1) / (2x + 3) = 3/8 को हल करने का पहला कदम क्या है?",
    "Cross-multiply diagonally: 8(x + 1) = 3(2x + 3)": "तिरछा (वज्र) गुणा करें: 8(x + 1) = 3(2x + 3)",
    "Add 8 to both sides": "दोनों पक्षों में 8 जोड़ें",
    "Subtract 3x from both sides": "दोनों पक्षों से 3x घटाएं",
    "Cross-multiplication removes the fractions instantly by multiplying each numerator by the opposite denominator.": "वज्र-गुणन प्रत्येक अंश को विपरीत हर से गुणा करके भिन्नों को तुरंत समाप्त कर देता है।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Forgetting to change signs": "चिह्न बदलना भूल जाना",
    "When a term moves across '=': + MUST become -, and - MUST become +. If you forget, your balance scale collapses!": "जब कोई पद '=' के पार जाता है: + को - और - को + बनना अनिवार्य है। यदि आप भूल गए, तो तराज़ू असंतुलित हो जाएगा!",
    "Partial bracket distribution": "अधूरा कोष्ठक विस्तार",
    "In 4(x - 3), multiplying only x gives 4x - 3 (WRONG!). You must multiply EVERY term: 4x - 12.": "4(x - 3) में, केवल x से गुणा करके 4x - 3 लिखना गलत है! प्रत्येक पद से गुणा करें: 4x - 12।",
    "Dividing only one term": "केवल एक पद को भाग देना",
    "In 2x + 6 = 14, dividing by 2 means dividing ALL terms: x + 3 = 7. Transposing 6 first (2x = 8 -> x = 4) is much safer.": "2x + 6 = 14 में, 2 से भाग देने का अर्थ सभी पदों को भाग देना है: x + 3 = 7। पहले 6 का पक्षांतरण करना अधिक सुरक्षित है।",
    "Where you meet it in real life": "दैनिक जीवन में समीकरण कहाँ मिलते हैं",
    "Auto Rickshaw Fares": "ऑटो रिक्शा का किराया",
    "Fixed base fare ₹30 + ₹12 per km. If total bill is ₹150, solve 30 + 12x = 150 to find you travelled exactly 10 km!": "निश्चित आधार किराया ₹30 + ₹12 प्रति किमी। यदि कुल बिल ₹150 है, तो 30 + 12x = 150 हल करके पता चलता है कि आपने 10 किमी यात्रा की!",
    "Budgeting Monthly Expenses": "मासिक घरेलू बजट",
    "Total salary ₹40,000. Rent is ₹15,000, food is ₹12,000. Equation: 15000 + 12000 + Savings = 40000. Savings = ₹13,000!": "कुल वेतन ₹40,000। किराया ₹15,000, भोजन ₹12,000। समीकरण: 15000 + 12000 + बचत = 40000। बचत = ₹13,000!",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Linear Equation": "रैखिक समीकरण",
    "ax + b = c (degree of variable is strictly 1)": "ax + b = c (चर की उच्चतम घात 1 होती है)",
    "Balance Principle": "संतुलन सिद्धांत",
    "Equality '=' behaves as a two-pan scale in equilibrium.": "समता '=' संतुलित दो पलड़ों वाले तराज़ू की तरह काम करती है।",
    "Transposition": "पक्षांतरण",
    "Cross border: + <-> -, and × <-> ÷. Keep terms grouped.": "सीमा पार करें: + <-> -, और × <-> ÷। सजातीय पदों को एक साथ रखें।",
    "Brackets First": "पहले कोष्ठक खोलें",
    "Distribute a(b + c) = ab + ac before grouping terms.": "पदों को समूहीकृत करने से पहले a(b + c) = ab + ac लागू करें।",
    "Cross-Multiply": "वज्र-गुणन",
    "(ax + b)/(cx + d) = p/q -> q(ax + b) = p(cx + d)": "(ax + b)/(cx + d) = p/q -> q(ax + b) = p(cx + d)",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Mastery unlocked! You have mastered the algebraic balance scale.": "मास्टरी अनलॉक! आपने बीजीय तराज़ू के सभी रहस्यों पर विजय प्राप्त कर ली है।",
    "Any linear riddle can now be translated into a clean equation and solved in seconds!": "अब किसी भी रैखिक पहेली को एक साफ़ समीकरण में बदलकर कुछ ही सेकंड में हल किया जा सकता है!",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Linear Equations in One Variable — Dynamic Balance Scale & Transposition",
        "s": "Mathematics · Class 8 · Chapter 2",
        "b": "An algebraic equation is like a vegetable vendor's traditional two-pan balance scale. The '=' sign means both pans are in perfect horizontal equilibrium.",
        "viz": "scale_balanced",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "Whatever you add, subtract, multiply, or divide on the left side, you must do to the right side to keep the scale balanced.",
        "mentor": "Namaste! I am Acharya. Think of x as a mystery treasure box on a balance scale. Our goal is to unpack it until x sits alone!",
        "viz": "scale_balanced",
    },
    {
        "kind": "text",
        "t": "What Makes an Equation 'Linear'?",
        "b": "An algebraic expression becomes an EQUATION when it contains an equality sign (=). It is LINEAR when the highest exponent (power) of the variable is strictly 1. 2x + 5 = 15 is linear; x² + 1 = 10 is not!",
        "viz": "linear_definition",
    },
    {
        "kind": "text",
        "t": "The Golden Rule of the Balance Scale",
        "b": "Imagine the '=' sign is the fulcrum of a balance scale. Left Hand Side (LHS) sits on the left pan, Right Hand Side (RHS) on the right pan. If 2x + 3 = 11, the pans balance horizontally.",
        "viz": "scale_balanced",
    },
    {
        "kind": "sim",
        "sim": "balance",
        "t": "Try it: Balance the Scale",
        "b": "Adjust the weight of x and watch the balance beam react. When the LHS exactly equals RHS, the beam levels out with a green equilibrium glow.",
        "hint": "When balanced, the scale beam is level (tilt = 0) and the equation is solved!",
    },
    {
        "kind": "text",
        "t": "The Method of Transposition (पक्षांतरण)",
        "b": "Instead of adding or subtracting numbers on both sides, we can 'transpose' a term across the '=' sign. When a term crosses the border, its operation flips: + becomes -, and × becomes ÷!",
        "mentor": "Crossing the '=' border is like crossing a country border: your currency flips to the opposite currency!",
        "viz": "transposition_flow",
    },
    {
        "kind": "text",
        "t": "Solving: 2x - 3 = 7 Step-by-Step",
        "b": "Step 1: Transpose -3 to the RHS as +3: 2x = 7 + 3 = 10. Step 2: Transpose multiplying 2 to division: x = 10 ÷ 2 = 5. Check: 2(5) - 3 = 7. Verified!",
        "viz": "step_card",
    },
    {
        "kind": "text",
        "t": "Variables on Both Sides",
        "b": "What if the unknown appears on both pans, like 5x - 3 = 3x + 7? Group all variable terms on the LHS and all numerical constants on the RHS! 5x - 3x = 7 + 3 -> 2x = 10 -> x = 5.",
        "viz": "both_sides_visual",
    },
    {
        "kind": "text",
        "t": "Equations with Parentheses (Brackets)",
        "b": "Always apply the Distributive Property before moving terms: a(b + c) = ab + ac. In 3(x - 2) + 5 = 20, first expand: 3x - 6 + 5 = 20 -> 3x - 1 = 20 -> 3x = 21 -> x = 7.",
        "viz": "distributive_visual",
    },
    {
        "kind": "text",
        "t": "Cross-Multiplication for Fraction Forms",
        "b": "When an equation is in the fractional form (ax + b) / (cx + d) = p / q, multiply diagonally: q(ax + b) = p(cx + d). This instantly converts a fraction into a simple flat linear line!",
        "viz": "cross_mult_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — The Age Riddle",
        "b": "Rahul's father is 3 times as old as Rahul. The sum of their ages is 56 years. Find Rahul's age.",
        "steps": [
            "Step 1: Let Rahul's age be x years. Father's age is 3x years.",
            "Step 2: Set up the equation: x + 3x = 56.",
            "Step 3: Combine like terms: 4x = 56.",
            "Step 4: Divide both sides by 4: x = 56 ÷ 4 = 14.",
            "Rahul is 14 years old, and his father is 42 years old (14 × 3 = 42; 14 + 42 = 56).",
        ],
        "viz": "scale_balanced",
    },
    {
        "kind": "steps",
        "t": "Worked example — Solving with Brackets",
        "b": "Solve: 8x + 4 = 3(x - 1) + 7.",
        "steps": [
            "Step 1: Expand brackets on RHS: 8x + 4 = 3x - 3 + 7.",
            "Step 2: Simplify RHS constants: 8x + 4 = 3x + 4.",
            "Step 3: Transpose 3x to LHS and 4 to RHS: 8x - 3x = 4 - 4.",
            "Step 4: 5x = 0 -> x = 0 ÷ 5 = 0.",
            "Final solution is x = 0.",
        ],
        "viz": "distributive_visual",
    },
    {
        "kind": "check",
        "q": "Solve: 3x - 5 = 16. What is x?",
        "opts": ["7", "5", "9"],
        "ans": 0,
        "why": "Transpose -5: 3x = 16 + 5 = 21. Divide by 3: x = 21 ÷ 3 = 7.",
    },
    {
        "kind": "check",
        "q": "What is the first step in solving (x + 1) / (2x + 3) = 3/8?",
        "opts": [
            "Cross-multiply diagonally: 8(x + 1) = 3(2x + 3)",
            "Add 8 to both sides",
            "Subtract 3x from both sides",
        ],
        "ans": 0,
        "why": "Cross-multiplication removes the fractions instantly by multiplying each numerator by the opposite denominator.",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Guard yourself against these common algebra exam pitfalls.",
        "items": [
            [
                "Forgetting to change signs",
                "When a term moves across '=': + MUST become -, and - MUST become +. If you forget, your balance scale collapses!",
            ],
            [
                "Partial bracket distribution",
                "In 4(x - 3), multiplying only x gives 4x - 3 (WRONG!). You must multiply EVERY term: 4x - 12.",
            ],
            [
                "Dividing only one term",
                "In 2x + 6 = 14, dividing by 2 means dividing ALL terms: x + 3 = 7. Transposing 6 first (2x = 8 -> x = 4) is much safer.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "Every time you plan a journey or calculate grocery change, linear equations are your silent helper.",
        "mentor": "Whenever you calculate remaining petrol, monthly phone bill data, or train arrival times, you are solving linear equations!",
        "viz": "scale_balanced",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "All linear equation principles captured on one reference card.",
        "items": [
            [
                "Linear Equation",
                "ax + b = c (degree of variable is strictly 1)",
            ],
            [
                "Balance Principle",
                "Equality '=' behaves as a two-pan scale in equilibrium.",
            ],
            [
                "Transposition",
                "Cross border: + <-> -, and × <-> ÷. Keep terms grouped.",
            ],
            [
                "Brackets First",
                "Distribute a(b + c) = ab + ac before grouping terms.",
            ],
            [
                "Cross-Multiply",
                "(ax + b)/(cx + d) = p/q -> q(ax + b) = p(cx + d)",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Mastery unlocked! You have mastered the algebraic balance scale.",
        "b": "Any linear riddle can now be translated into a clean equation and solved in seconds!",
    },
]

SVG_AND_SIMS_JS = """
<script>
const VB = 'viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet"';
function svgOpen(extra){ return '<svg '+VB+' font-family="system-ui,sans-serif" '+(extra||"")+'>'; }

function vizCard(type){
  let s = svgOpen();
  s += '<rect x="25" y="25" width="350" height="250" rx="16" fill="rgba(49,230,196,.04)" stroke="rgba(49,230,196,.2)"/>';
  s += '<circle cx="200" cy="150" r="70" fill="rgba(255,194,71,.08)"/>';
  s += '<text x="200" y="165" font-size="60" text-anchor="middle">⚖️</text>';
  return s + '</svg>';
}

function vizScale(xVal){
  let s = svgOpen();
  const lhs = 2 * xVal + 3;
  const rhs = 11;
  const diff = lhs - rhs;
  const tilt = Math.max(-18, Math.min(18, diff * 3));
  const isBalanced = diff === 0;

  // Stand
  s += '<line x1="200" y1="100" x2="200" y2="250" stroke="#5c7386" stroke-width="6"/>';
  s += '<polygon points="200,85 188,105 212,105" fill="#ffc247"/>';
  s += '<rect x="150" y="250" width="100" height="16" rx="6" fill="#122436" stroke="#5c7386" stroke-width="2"/>';

  // Tilting Beam
  const rad = (tilt * Math.PI) / 180;
  const lx = 200 - 110 * Math.cos(rad), ly = 95 - 110 * Math.sin(rad);
  const rx = 200 + 110 * Math.cos(rad), ry = 95 + 110 * Math.sin(rad);

  const beamCol = isBalanced ? '#31e6c4' : (Math.abs(tilt) > 10 ? '#ff5f78' : '#ffc247');
  s += '<line x1="'+lx+'" y1="'+ly+'" x2="'+rx+'" y2="'+ry+'" stroke="'+beamCol+'" stroke-width="5"/>';

  // Left Pan (2x + 3)
  s += '<line x1="'+lx+'" y1="'+ly+'" x2="'+(lx-25)+'" y2="'+(ly+65)+'" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<line x1="'+lx+'" y1="'+ly+'" x2="'+(lx+25)+'" y2="'+(ly+65)+'" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<path d="M '+(lx-32)+' '+(ly+65)+' Q '+lx+' '+(ly+80)+' '+(lx+32)+' '+(ly+65)+' Z" fill="#122436" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<rect x="'+(lx-18)+'" y="'+(ly+40)+'" width="36" height="24" rx="4" fill="#31e6c4" fill-opacity=".85"/>';
  s += '<text x="'+lx+'" y="'+(ly+56)+'" fill="#04201c" font-size="13" font-weight="900" text-anchor="middle">2x+3 ('+lhs+')</text>';

  // Right Pan (11)
  s += '<line x1="'+rx+'" y1="'+ry+'" x2="'+(rx-25)+'" y2="'+(ry+65)+'" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<line x1="'+rx+'" y1="'+ry+'" x2="'+(rx+25)+'" y2="'+(ry+65)+'" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<path d="M '+(rx-32)+' '+(ry+65)+' Q '+rx+' '+(ry+80)+' '+(rx+32)+' '+(ry+65)+' Z" fill="#122436" stroke="#8ba2b6" stroke-width="2"/>';
  s += '<rect x="'+(rx-18)+'" y="'+(ry+40)+'" width="36" height="24" rx="4" fill="#ffc247" fill-opacity=".85"/>';
  s += '<text x="'+rx+'" y="'+(ry+56)+'" fill="#2a1d00" font-size="13" font-weight="900" text-anchor="middle">11</text>';

  // Status text
  if(isBalanced){
    s += '<rect x="110" y="22" width="180" height="34" rx="8" fill="rgba(74,222,128,.15)" stroke="#4ade80" stroke-width="2"/>';
    s += '<text x="200" y="44" fill="#4ade80" font-size="16" font-weight="900" text-anchor="middle">EQUILIBRIUM: x = 4 ✓</text>';
  } else {
    s += '<text x="200" y="44" fill="#ffc247" font-size="15" font-weight="800" text-anchor="middle">'+(diff>0?'Left is heavier (tilt down)':'Right is heavier (tilt up)')+'</text>';
  }
  return s + '</svg>';
}

function vizTransposition(){
  let s = svgOpen();
  s += '<rect x="40" y="50" width="320" height="200" rx="14" fill="#0f1f2e" stroke="#1d4055" stroke-width="2"/>';
  s += '<line x1="200" y1="50" x2="200" y2="250" stroke="#ffc247" stroke-width="3" stroke-dasharray="6 4"/>';
  s += '<circle cx="200" cy="150" r="22" fill="#ffc247" stroke="#070c12" stroke-width="3"/>';
  s += '<text x="200" y="158" fill="#2a1d00" font-size="24" font-weight="900" text-anchor="middle">=</text>';

  s += '<rect x="60" y="80" width="100" height="42" rx="8" fill="#31e6c4" fill-opacity=".2" stroke="#31e6c4" stroke-width="2"/>';
  s += '<text x="110" y="106" fill="#31e6c4" font-size="16" font-weight="800" text-anchor="middle">+ 5</text>';

  s += '<path d="M 160 100 Q 200 60 240 100" fill="none" stroke="#ff5f78" stroke-width="3" stroke-dasharray="4 4"/>';
  s += '<polygon points="240,100 230,94 234,104" fill="#ff5f78"/>';

  s += '<rect x="240" y="80" width="100" height="42" rx="8" fill="#ff5f78" fill-opacity=".2" stroke="#ff5f78" stroke-width="2"/>';
  s += '<text x="290" y="106" fill="#ff5f78" font-size="16" font-weight="800" text-anchor="middle">- 5</text>';

  s += '<text x="200" y="210" fill="#8ba2b6" font-size="14" font-weight="700" text-anchor="middle">Border Rule: + flips to - when crossing =</text>';
  return s + '</svg>';
}

const VIZ = {
  scale_balanced: ()=> vizScale(4),
  linear_definition: ()=> vizTransposition(),
  transposition_flow: ()=> vizTransposition(),
  step_card: ()=> vizScale(4),
  both_sides_visual: ()=> vizScale(4),
  distributive_visual: ()=> vizTransposition(),
  cross_mult_visual: ()=> vizTransposition(),
};

const SIM = {
  balance: ()=>'<label style="font-size:13.5px;color:var(--muted)">Guess value of x (1 to 8): <b id="oX" style="color:var(--teal)">2</b></label>'+
    '<input type="range" id="sX" min="1" max="8" value="2">'+
    '<div class="readout"><span>LHS: 2('+ '<span id="oXval">2</span>' +') + 3 = <b id="oLhs">7</b></span>'+
    '<span>RHS: <b style="color:var(--gold)">11</b></span></div>'
};

function simViz(name, v){
  if(name === "balance") return vizScale(v);
  return vizScale(4);
}

function initSim(name){
  if(name === "balance") return 2;
  return 4;
}

function wireSim(name){
  if(name === "balance"){
    const s = document.getElementById("sX");
    const upd = ()=>{
      const x = +s.value;
      document.getElementById("oX").textContent = x;
      document.getElementById("oXval").textContent = x;
      document.getElementById("oLhs").textContent = (2 * x + 3);
      setVis(vizScale(x));
    };
    s.addEventListener("input", upd); upd();
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class8_math_ch02_linear_equations",
        title="Linear Equations in One Variable (Class 8 Math Ch 2)",
        grade_subject_sub="Class 8 Math · Chapter 2: Linear Equations",
        chapter_num_label="Chapter 2",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class8_math_ch02_linear_equations.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 2 Linear Equations to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
