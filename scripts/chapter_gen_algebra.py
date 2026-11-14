"""AASHA AIOS — Class 8 Math Chapter 9: Algebraic Expressions and Identities Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "algebra": {"h": "बीजगणित", "p": "अलजेब्रा"},
    "algebraic": {"h": "बीजीय", "p": "अलजेब्राइक"},
    "expression": {"h": "बीजीय व्यंजक", "p": "एक्सप्रेशन"},
    "expressions": {"h": "व्यंजक", "p": "एक्सप्रेशन्स"},
    "identity": {"h": "सर्वसमिका (सदा सत्य समीकरण)", "p": "आइडेंटिटी"},
    "identities": {"h": "सर्वसमिकाएँ", "p": "आइडेंटिटीज़"},
    "term": {"h": "पद", "p": "टर्म"},
    "terms": {"h": "पद", "p": "टर्म्स"},
    "factor": {"h": "गुणनखंड", "p": "फ़ैक्टर"},
    "factors": {"h": "गुणनखंड", "p": "फ़ैक्टर्स"},
    "coefficient": {"h": "गुणांक (संख्यात्मक मान)", "p": "कोएफ़िशिएंट"},
    "monomial": {"h": "एकपदी (1 पद)", "p": "मोनोमियल"},
    "binomial": {"h": "द्विपदी (2 पद)", "p": "बाइनोमियल"},
    "trinomial": {"h": "त्रिपदी (3 पद)", "p": "ट्राइनोमियल"},
    "polynomial": {"h": "बहुपद", "p": "पॉलीनोमियल"},
    "like": {"h": "सजातीय पद (एक जैसे चर)", "p": "लाइक"},
    "unlike": {"h": "विजातीय पद (अलग चर)", "p": "अनलाइक"},
    "area": {"h": "क्षेत्रफल", "p": "एरिया"},
    "square": {"h": "वर्ग / वर्गफल", "p": "स्क्वायर"},
    "rectangle": {"h": "आयत", "p": "रेक्टेंगल"},
    "product": {"h": "गुणनफल", "p": "प्रोडक्ट"},
}

EXTRA_PHRASES = {
    "Algebraic Expressions & Identities — Geometric Tiles & Area Model": "बीजीय व्यंजक और सर्वसमिकाएँ — ज्यामितीय टाइलें और क्षेत्रफल मॉडल",
    "Mathematics · Class 8 · Chapter 9": "गणित · कक्षा 8 · अध्याय 9",
    "Algebra is geometry in disguise. See (a + b)² not as a dry formula, but as a square agricultural field split into four colored plots.": "बीजगणित वास्तव में रूप बदलकर आई ज्यामिति है। (a + b)² को किसी सूखे सूत्र के रूप में नहीं, बल्कि चार रंगीन भूखंडों में बंटे एक वर्गाकार खेत के रूप में देखें।",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "An algebraic identity is an equality that holds true for every possible numerical value of its variables.": "बीजीय सर्वसमिका एक ऐसी समता है जो अपने चरों के प्रत्येक संभव संख्यात्मक मान के लिए सत्य होती है।",
    "What is an Algebraic Expression?": "बीजीय व्यंजक क्या होता है?",
    "An expression is built from variables (x, y, z) and constants (numbers) combined using addition, subtraction, multiplication, and division. In 4x² - 3xy + 7, there are 3 distinct terms separated by + and - signs.": "व्यंजक चरों (x, y, z) और अचरों (संख्याओं) को जोड़, घटाव, गुणा और भाग द्वारा मिलाकर बनाया जाता है। 4x² - 3xy + 7 में, + और - चिह्नों द्वारा अलग किए गए 3 अलग-अलग पद हैं।",
    "Anatomy of a Term: Factors & Coefficients": "पद की संरचना: गुणनखंड और गुणांक",
    "Take the term -7x²y. Its factors are -7, x, x, and y. The numerical factor (-7) is called the COEFFICIENT. In the term x, the coefficient is silently 1!": "पद -7x²y को लें। इसके गुणनखंड -7, x, x और y हैं। संख्यात्मक गुणनखंड (-7) को गुणांक (Coefficient) कहा जाता है। पद x में, गुणांक अदृश्य रूप से 1 होता है!",
    "Classification: From Monomial to Polynomial": "वर्गीकरण: एकपदी से बहुपद तक",
    "Monomial has 1 term (e.g. 7xy). Binomial has 2 terms (e.g. 2x + 3y). Trinomial has 3 terms (e.g. a + b + c). Any expression with one or more terms is broadly called a POLYNOMIAL.": "एकपदी (Monomial) में 1 पद होता है (जैसे 7xy)। द्विपदी (Binomial) में 2 पद होते हैं (जैसे 2x + 3y)। त्रिपदी (Trinomial) में 3 पद होते हैं (जैसे a + b + c)। एक या अधिक पदों वाले किसी भी व्यंजक को बहुपद (Polynomial) कहा जाता है।",
    "Like Terms vs Unlike Terms": "सजातीय पद बनाम विजातीय पद",
    "LIKE TERMS have the exact same algebraic variable factors: 7x and -12x are like; 5x²y and 3yx² are like! UNLIKE TERMS have different variables: 7x and 7y cannot be merged. You can only add apples to apples!": "सजातीय पदों (Like Terms) में बिल्कुल समान बीजीय चर गुणनखंड होते हैं: 7x और -12x सजातीय हैं; 5x²y और 3yx² सजातीय हैं! विजातीय पदों में अलग चर होते हैं: 7x और 7y को मिलाया नहीं जा सकता। केवल सेब में सेब जोड़े जा सकते हैं!",
    "Standard Identity I: (a + b)²": "मानक सर्वसमिका I: (a + b)²",
    "(a + b)² = a² + 2ab + b². Look at a square of side (a + b). Its total area splits into four zones: a square of area a², another square of area b², and two identical rectangles each of area ab!": "(a + b)² = a² + 2ab + b²। (a + b) भुजा वाले वर्ग को देखें। इसका कुल क्षेत्रफल चार क्षेत्रों में बंटता है: a² क्षेत्रफल का वर्ग, b² क्षेत्रफल का दूसरा वर्ग, और ab क्षेत्रफल के दो समान आयत!",
    "Try it: The Geometric Tile Area Model": "करके देखें: ज्यामितीय टाइल क्षेत्रफल मॉडल",
    "Drag sliders for a and b. Watch the four colored sub-rectangles resize and sum up live. Notice how a² + ab + ba + b² perfectly fills the entire (a + b)² square!": "a और b के लिए स्लाइडर खींचें। देखें कि चार रंगीन उप-आयत कैसे आकार बदलते हैं और उनका योग होता है। ध्यान दें कि a² + ab + ba + b² पूरे (a + b)² वर्ग को कैसे पूरी तरह भरता है!",
    "Standard Identity II: (a - b)²": "मानक सर्वसमिका II: (a - b)²",
    "(a - b)² = a² - 2ab + b². From the large square a², subtracting two strips of area ab removes the corner square b² twice! So we must add back b² to restore balance.": "(a - b)² = a² - 2ab + b²। बड़े वर्ग a² में से, ab क्षेत्रफल की दो पट्टियाँ घटाने पर कोने का वर्ग b² दो बार घट जाता है! इसलिए संतुलन के लिए हमें b² को वापस जोड़ना पड़ता है।",
    "Standard Identity III: a² - b²": "मानक सर्वसमिका III: a² - b²",
    "Difference of two squares: a² - b² = (a + b)(a - b). Cut out a small square b² from a large square a². The remaining L-shaped region rearranges into a single rectangle of sides (a + b) and (a - b)!": "दो वर्गों का अंतर: a² - b² = (a + b)(a - b)। एक बड़े वर्ग a² से एक छोटा वर्ग b² काटें। शेष L-आकार का क्षेत्र (a + b) और (a - b) भुजाओं वाले एक आयत में पुनर्व्यवस्थित हो जाता है!",
    "Mental Arithmetic Superpower": "मानसिक गणना की महाशक्ति",
    "Identities let you multiply huge numbers in your head! 103 × 97 = (100 + 3)(100 - 3) = 100² - 3² = 10,000 - 9 = 9,991. Instant answer in 2 seconds without a calculator!": "सर्वसमिकाएँ आपको बिना पेन के बड़ी संख्याओं का गुणा करने देती हैं! 103 × 97 = (100 + 3)(100 - 3) = 100² - 3² = 10,000 - 9 = 9,991। कैलकुलेटर के बिना 2 सेकंड में उत्तर!",
    "Worked example — Expanding (2x + 3y)²": "हल किया गया उदाहरण — (2x + 3y)² का प्रसार",
    "Use Identity I with a = 2x and b = 3y.": "सर्वसमिका I का प्रयोग करें जहाँ a = 2x और b = 3y है।",
    "Step 1: Formula is (a + b)² = a² + 2ab + b².": "स्टेप 1: सूत्र है (a + b)² = a² + 2ab + b²।",
    "Step 2: Substitute: (2x)² + 2(2x)(3y) + (3y)².": "स्टेप 2: मान रखें: (2x)² + 2(2x)(3y) + (3y)²।",
    "Step 3: Square each term carefully: (2x)² = 4x², and (3y)² = 9y².": "स्टेप 3: प्रत्येक पद का वर्ग करें: (2x)² = 4x², और (3y)² = 9y²।",
    "Step 4: Middle cross-term: 2 × 2x × 3y = 12xy.": "स्टेप 4: मध्य पद: 2 × 2x × 3y = 12xy।",
    "Final expanded answer is 4x² + 12xy + 9y².": "अंतिम उत्तर 4x² + 12xy + 9y² है।",
    "Worked example — Fast Calculation of 98²": "हल किया गया उदाहरण — 98² की त्वरित गणना",
    "Evaluate 98² without vertical multiplication.": "बिना लंबे गुणा के 98² का मान ज्ञात कीजिए।",
    "Step 1: Write 98 as (100 - 2).": "स्टेप 1: 98 को (100 - 2) के रूप में लिखें।",
    "Step 2: Apply (a - b)² = a² - 2ab + b² with a = 100, b = 2.": "स्टेप 2: (a - b)² = a² - 2ab + b² लागू करें जहाँ a = 100, b = 2 है।",
    "Step 3: 100² - 2(100)(2) + 2² = 10,000 - 400 + 4.": "स्टेप 3: 100² - 2(100)(2) + 2² = 10,000 - 400 + 4।",
    "Step 4: 9,600 + 4 = 9,604. Done!": "स्टेप 4: 9,600 + 4 = 9,604। हल हो गया!",
    "Expand (x + 5)(x + 5). What is the middle term?": "(x + 5)(x + 5) का प्रसार करें। मध्य पद क्या होगा?",
    "10x": "10x",
    "5x": "5x",
    "25x": "25x",
    "Middle term is 2ab = 2(x)(5) = 10x.": "मध्य पद 2ab = 2(x)(5) = 10x होता है।",
    "Evaluate: 52 × 48 using identities.": "सर्वसमिका का उपयोग करके 52 × 48 का मान ज्ञात कीजिए।",
    "2496": "2496",
    "2500": "2500",
    "2484": "2484",
    "52 × 48 = (50 + 2)(50 - 2) = 50² - 2² = 2500 - 4 = 2496.": "52 × 48 = (50 + 2)(50 - 2) = 50² - 2² = 2500 - 4 = 2496।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Forgetting the middle 2ab term": "मध्य पद 2ab को भूल जाना",
    "(a + b)² is NEVER just a² + b²! If you omit 2ab, you throw away two entire rectangular areas of the geometric tile!": "(a + b)² कभी केवल a² + b² नहीं होता! यदि आप 2ab छोड़ देते हैं, तो आप ज्यामितीय टाइल के दो पूरे आयताकार क्षेत्रों को फेंक देते हैं!",
    "Squaring coefficients incorrectly": "गुणांकों का गलत वर्ग करना",
    "(3x)² is 9x², NOT 3x²! The exponent 2 applies to both the number 3 and the variable x.": "(3x)² का मान 9x² होता है, 3x² नहीं! घात 2 संख्या 3 और चर x दोनों पर लागू होती है।",
    "Sign error in Identity II": "सर्वसमिका II में चिह्न की गलती",
    "In (a - b)², the last term is ALWAYS positive +b² because (-b)² = +b². Only the middle term is negative: a² - 2ab + b².": "(a - b)² में, अंतिम पद हमेशा धनात्मक +b² होता है क्योंकि (-b)² = +b²। केवल मध्य पद ऋणात्मक होता है: a² - 2ab + b²।",
    "Where you meet it in real life": "दैनिक जीवन में सर्वसमिकाएँ कहाँ मिलती हैं",
    "Flooring and Tile Layouts": "फर्श और टाइल की बिछाई",
    "When a mason tiles a square hall of 12m × 12m by dividing it into (10 + 2)², they calculate 100m² + 40m² + 4m² = 144m² without measuring individual small cuts.": "जब कोई राजमिस्त्री 12m × 12m के वर्गाकार हॉल को (10 + 2)² में बांटकर टाइल लगाता है, तो वह बिना हर टुकड़े को नापे 144m² का सटीक हिसाब लगाता है।",
    "Computer Graphics & 3D Shaders": "कंप्यूटर ग्राफिक्स और 3D शेडर्स",
    "Every video game physics engine uses polynomial expressions and identities to compute surface areas, light bounces, and player collisions 60 times a second!": "प्रत्येक वीडियो गेम भौतिकी इंजन सतह क्षेत्रफल, प्रकाश परावर्तन और टकराव की गणना करने के लिए बीजीय सर्वसमिकाओं का उपयोग करता है!",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Identity I": "सर्वसमिका I",
    "(a + b)² = a² + 2ab + b²": "(a + b)² = a² + 2ab + b²",
    "Identity II": "सर्वसमिका II",
    "(a - b)² = a² - 2ab + b²": "(a - b)² = a² - 2ab + b²",
    "Identity III": "सर्वसमिका III",
    "a² - b² = (a + b)(a - b)": "a² - b² = (a + b)(a - b)",
    "Identity IV": "सर्वसमिका IV",
    "(x + a)(x + b) = x² + (a + b)x + ab": "(x + a)(x + b) = x² + (a + b)x + ab",
    "Like Terms": "सजातीय पद",
    "Add/subtract only terms with identical variable factors.": "केवल समान चर गुणनखंड वाले पदों को जोड़ें/घटाएं।",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Mastery unlocked! You now possess algebraic visual insight and computational speed.": "मास्टरी अनलॉक! अब आपके पास बीजीय दृश्य अंतर्दृष्टि और गणना की तीव्र गति है।",
    "You have completed all conceptual tiles, geometric proofs, and mental math shortcuts.": "आपने सभी वैचारिक टाइलें, ज्यामितीय प्रमाण और मानसिक गणित शॉर्टकट पूरे कर लिए हैं।",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Algebraic Expressions & Identities — Geometric Tiles & Area Model",
        "s": "Mathematics · Class 8 · Chapter 9",
        "b": "Algebra is geometry in disguise. See (a + b)² not as a dry formula, but as a square agricultural field split into four colored plots.",
        "viz": "tile_square",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "An algebraic identity is an equality that holds true for every possible numerical value of its variables.",
        "mentor": "Namaste! I am Acharya. Don't just memorize formulas. When you can see the shapes behind algebra, you will never forget them!",
        "viz": "tile_square",
    },
    {
        "kind": "text",
        "t": "What is an Algebraic Expression?",
        "b": "An expression is built from variables (x, y, z) and constants (numbers) combined using addition, subtraction, multiplication, and division. In 4x² - 3xy + 7, there are 3 distinct terms separated by + and - signs.",
        "viz": "terms_visual",
    },
    {
        "kind": "text",
        "t": "Anatomy of a Term: Factors & Coefficients",
        "b": "Take the term -7x²y. Its factors are -7, x, x, and y. The numerical factor (-7) is called the COEFFICIENT. In the term x, the coefficient is silently 1!",
        "viz": "coefficient_visual",
    },
    {
        "kind": "text",
        "t": "Classification: From Monomial to Polynomial",
        "b": "Monomial has 1 term (e.g. 7xy). Binomial has 2 terms (e.g. 2x + 3y). Trinomial has 3 terms (e.g. a + b + c). Any expression with one or more terms is broadly called a POLYNOMIAL.",
        "viz": "polynomial_types",
    },
    {
        "kind": "text",
        "t": "Like Terms vs Unlike Terms",
        "b": "LIKE TERMS have the exact same algebraic variable factors: 7x and -12x are like; 5x²y and 3yx² are like! UNLIKE TERMS have different variables: 7x and 7y cannot be merged. You can only add apples to apples!",
        "mentor": "3 rotis + 2 rotis = 5 rotis (3r + 2r = 5r). But 3 rotis + 2 samosas cannot become 5 samosas! Unlike terms stay separate.",
        "viz": "like_terms_visual",
    },
    {
        "kind": "text",
        "t": "Standard Identity I: (a + b)²",
        "b": "(a + b)² = a² + 2ab + b². Look at a square of side (a + b). Its total area splits into four zones: a square of area a², another square of area b², and two identical rectangles each of area ab!",
        "viz": "tile_square",
    },
    {
        "kind": "sim",
        "sim": "tiles",
        "t": "Try it: The Geometric Tile Area Model",
        "b": "Drag sliders for a and b. Watch the four colored sub-rectangles resize and sum up live. Notice how a² + ab + ba + b² perfectly fills the entire (a + b)² square!",
        "hint": "The middle term 2ab comes from the two golden rectangular strips!",
    },
    {
        "kind": "text",
        "t": "Standard Identity II: (a - b)²",
        "b": "(a - b)² = a² - 2ab + b². From the large square a², subtracting two strips of area ab removes the corner square b² twice! So we must add back b² to restore balance.",
        "viz": "identity_two_visual",
    },
    {
        "kind": "text",
        "t": "Standard Identity III: a² - b²",
        "b": "Difference of two squares: a² - b² = (a + b)(a - b). Cut out a small square b² from a large square a². The remaining L-shaped region rearranges into a single rectangle of sides (a + b) and (a - b)!",
        "viz": "identity_three_visual",
    },
    {
        "kind": "text",
        "t": "Mental Arithmetic Superpower",
        "b": "Identities let you multiply huge numbers in your head! 103 × 97 = (100 + 3)(100 - 3) = 100² - 3² = 10,000 - 9 = 9,991. Instant answer in 2 seconds without a calculator!",
        "mentor": "Practice this at the grocery shop: 52 × 48 = (50+2)(50-2) = 2500 - 4 = 2496. Impress your friends with lightning mental maths!",
        "viz": "mental_math_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — Expanding (2x + 3y)²",
        "b": "Use Identity I with a = 2x and b = 3y.",
        "steps": [
            "Step 1: Formula is (a + b)² = a² + 2ab + b².",
            "Step 2: Substitute: (2x)² + 2(2x)(3y) + (3y)².",
            "Step 3: Square each term carefully: (2x)² = 4x², and (3y)² = 9y².",
            "Step 4: Middle cross-term: 2 × 2x × 3y = 12xy.",
            "Final expanded answer is 4x² + 12xy + 9y².",
        ],
        "viz": "tile_square",
    },
    {
        "kind": "steps",
        "t": "Worked example — Fast Calculation of 98²",
        "b": "Evaluate 98² without vertical multiplication.",
        "steps": [
            "Step 1: Write 98 as (100 - 2).",
            "Step 2: Apply (a - b)² = a² - 2ab + b² with a = 100, b = 2.",
            "Step 3: 100² - 2(100)(2) + 2² = 10,000 - 400 + 4.",
            "Step 4: 9,600 + 4 = 9,604. Done!",
        ],
        "viz": "identity_two_visual",
    },
    {
        "kind": "check",
        "q": "Expand (x + 5)(x + 5). What is the middle term?",
        "opts": ["10x", "5x", "25x"],
        "ans": 0,
        "why": "Middle term is 2ab = 2(x)(5) = 10x.",
    },
    {
        "kind": "check",
        "q": "Evaluate: 52 × 48 using identities.",
        "opts": ["2496", "2500", "2484"],
        "ans": 0,
        "why": "52 × 48 = (50 + 2)(50 - 2) = 50² - 2² = 2500 - 4 = 2496.",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Guard yourself against these classic algebraic identity traps.",
        "items": [
            [
                "Forgetting the middle 2ab term",
                "(a + b)² is NEVER just a² + b²! If you omit 2ab, you throw away two entire rectangular areas of the geometric tile!",
            ],
            [
                "Squaring coefficients incorrectly",
                "(3x)² is 9x², NOT 3x²! The exponent 2 applies to both the number 3 and the variable x.",
            ],
            [
                "Sign error in Identity II",
                "In (a - b)², the last term is ALWAYS positive +b² because (-b)² = +b². Only the middle term is negative: a² - 2ab + b².",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "Identities form the bedrock of architectural engineering and computing.",
        "mentor": "Whether you are designing mobile apps or constructing a home, algebraic area expansions ensure precision!",
        "viz": "tile_square",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "All four canonical algebraic identities in one unified reference.",
        "items": [
            [
                "Identity I",
                "(a + b)² = a² + 2ab + b²",
            ],
            [
                "Identity II",
                "(a - b)² = a² - 2ab + b²",
            ],
            [
                "Identity III",
                "a² - b² = (a + b)(a - b)",
            ],
            [
                "Identity IV",
                "(x + a)(x + b) = x² + (a + b)x + ab",
            ],
            [
                "Like Terms",
                "Add/subtract only terms with identical variable factors.",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Mastery unlocked! You now possess algebraic visual insight and computational speed.",
        "b": "You have completed all conceptual tiles, geometric proofs, and mental math shortcuts.",
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
  s += '<text x="200" y="165" font-size="60" text-anchor="middle">📐</text>';
  return s + '</svg>';
}

function vizTile(a, b){
  let s = svgOpen();
  const ox = 70, oy = 40, maxSz = 220;
  const tot = a + b;
  const wa = (a / tot) * maxSz;
  const wb = (b / tot) * maxSz;

  // Region 1: a^2 (Teal square)
  s += '<rect x="'+ox+'" y="'+oy+'" width="'+wa+'" height="'+wa+'" fill="#31e6c4" fill-opacity=".7" stroke="#1d4055" stroke-width="2"/>';
  s += '<text x="'+(ox + wa/2)+'" y="'+(oy + wa/2 + 6)+'" fill="#04201c" font-size="16" font-weight="900" text-anchor="middle">a² ('+(a*a)+')</text>';

  // Region 2: ab top-right (Gold rectangle)
  s += '<rect x="'+(ox + wa)+'" y="'+oy+'" width="'+wb+'" height="'+wa+'" fill="#ffc247" fill-opacity=".7" stroke="#1d4055" stroke-width="2"/>';
  s += '<text x="'+(ox + wa + wb/2)+'" y="'+(oy + wa/2 + 5)+'" fill="#2a1d00" font-size="13" font-weight="900" text-anchor="middle">ab ('+(a*b)+')</text>';

  // Region 3: ba bottom-left (Gold rectangle)
  s += '<rect x="'+ox+'" y="'+(oy + wa)+'" width="'+wa+'" height="'+wb+'" fill="#ffc247" fill-opacity=".7" stroke="#1d4055" stroke-width="2"/>';
  s += '<text x="'+(ox + wa/2)+'" y="'+(oy + wa + wb/2 + 5)+'" fill="#2a1d00" font-size="13" font-weight="900" text-anchor="middle">ba ('+(b*a)+')</text>';

  // Region 4: b^2 bottom-right (Rose square)
  s += '<rect x="'+(ox + wa)+'" y="'+(oy + wa)+'" width="'+wb+'" height="'+wb+'" fill="#ff5f78" fill-opacity=".7" stroke="#1d4055" stroke-width="2"/>';
  s += '<text x="'+(ox + wa + wb/2)+'" y="'+(oy + wa + wb/2 + 5)+'" fill="#2a0009" font-size="13" font-weight="900" text-anchor="middle">b² ('+(b*b)+')</text>';

  // Outer border
  s += '<rect x="'+ox+'" y="'+oy+'" width="'+maxSz+'" height="'+maxSz+'" fill="none" stroke="#eef5fa" stroke-width="3"/>';

  // Dimension labels
  s += '<text x="'+(ox + wa/2)+'" y="'+(oy - 8)+'" fill="#31e6c4" font-size="14" font-weight="800" text-anchor="middle">a = '+a+'</text>';
  s += '<text x="'+(ox + wa + wb/2)+'" y="'+(oy - 8)+'" fill="#ffc247" font-size="14" font-weight="800" text-anchor="middle">b = '+b+'</text>';
  s += '<text x="'+(ox - 10)+'" y="'+(oy + wa/2 + 5)+'" fill="#31e6c4" font-size="14" font-weight="800" text-anchor="end">a</text>';
  s += '<text x="'+(ox - 10)+'" y="'+(oy + wa + wb/2 + 5)+'" fill="#ffc247" font-size="14" font-weight="800" text-anchor="end">b</text>';

  s += '<text x="200" y="285" fill="#4ade80" font-size="15" font-weight="800" text-anchor="middle">(a+b)² = '+(tot*tot)+' = '+(a*a)+' + '+(2*a*b)+' + '+(b*b)+' ✓</text>';
  return s + '</svg>';
}

const VIZ = {
  tile_square: ()=> vizTile(3, 2),
  terms_visual: ()=> vizTile(4, 2),
  coefficient_visual: ()=> vizTile(3, 2),
  polynomial_types: ()=> vizTile(3, 3),
  like_terms_visual: ()=> vizTile(4, 2),
  identity_two_visual: ()=> vizTile(4, 1),
  identity_three_visual: ()=> vizTile(3, 2),
  mental_math_visual: ()=> vizTile(5, 2),
};

const SIM = {
  tiles: ()=>'<label style="font-size:13.5px;color:var(--muted)">Side a: <b id="oA" style="color:var(--teal)">3</b></label>'+
    '<input type="range" id="sA" min="1" max="6" value="3">'+
    '<label style="font-size:13.5px;color:var(--muted)">Side b: <b id="oB" style="color:var(--gold)">2</b></label>'+
    '<input type="range" id="sB" min="1" max="6" value="2">'+
    '<div class="readout"><span>Total side (a+b): <b id="oTot">5</b></span><span>Total Area: <b id="oArea">25</b></span></div>'
};

function simViz(name, v){
  if(name === "tiles") return vizTile(v.a, v.b);
  return vizTile(3, 2);
}

function initSim(name){
  if(name === "tiles") return {a: 3, b: 2};
  return 0;
}

function wireSim(name){
  if(name === "tiles"){
    const sA = document.getElementById("sA"), sB = document.getElementById("sB");
    const upd = ()=>{
      const a = +sA.value, b = +sB.value;
      document.getElementById("oA").textContent = a;
      document.getElementById("oB").textContent = b;
      document.getElementById("oTot").textContent = (a + b);
      document.getElementById("oArea").textContent = (a + b) * (a + b);
      setVis(vizTile(a, b));
    };
    sA.addEventListener("input", upd); sB.addEventListener("input", upd); upd();
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class8_math_ch09_algebraic_expressions",
        title="Algebraic Expressions & Identities (Class 8 Math Ch 9)",
        grade_subject_sub="Class 8 Math · Chapter 9: Algebraic Expressions",
        chapter_num_label="Chapter 9",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class8_math_ch09_algebraic_expressions.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 9 Algebraic Expressions to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
