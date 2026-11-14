"""AASHA AIOS — Class 6 Math Chapter 10: Integers Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "integers": {"h": "पूर्णांक", "p": "इन्टिजर्स"},
    "integer": {"h": "पूर्णांक संख्या", "p": "इन्टिजर"},
    "positive": {"h": "धनात्मक (+)", "p": "पॉज़िटिव"},
    "negative": {"h": "ऋणात्मक (-)", "p": "नेगेटिव"},
    "zero": {"h": "शून्य", "p": "ज़ीरो"},
    "numberline": {"h": "संख्या रेखा", "p": "नंबरलाइन"},
    "opposite": {"h": "विपरीत", "p": "ऑपोज़िट"},
    "additive": {"h": "योज्य", "p": "एडिटिव"},
    "inverse": {"h": "प्रतिलोम (उल्टा)", "p": "इन्वर्स"},
    "temperature": {"h": "तापमान", "p": "टेम्परेचर"},
    "degrees": {"h": "डिग्री", "p": "डिग्रीज़"},
    "celsius": {"h": "सेल्सियस", "p": "सेल्सियस"},
    "thermometer": {"h": "थर्मामीटर", "p": "थर्मामीटर"},
    "altitude": {"h": "ऊंचाई", "p": "एल्टीट्यूड"},
    "depth": {"h": "गहराई", "p": "डेप्थ"},
    "elevator": {"h": "लिफ्ट", "p": "एलीवेटर"},
    "basement": {"h": "तहखाना (नीचे का तल)", "p": "बेसमेंट"},
    "credit": {"h": "जमा (धनात्मक)", "p": "क्रेडिट"},
    "debit": {"h": "निकासी (ऋणात्मक)", "p": "डेबिट"},
    "absolute": {"h": "निरपेक्ष मान", "p": "एब्सोल्यूट"},
    "distance": {"h": "दूरी", "p": "डिस्टेंस"},
    "greater": {"h": "बड़ा", "p": "ग्रेटर"},
    "smaller": {"h": "छोटा", "p": "स्मॉलर"},
}

EXTRA_PHRASES = {
    "Integers — Positive and Negative Numbers on a Number Line": "पूर्णांक — संख्या रेखा पर धनात्मक और ऋणात्मक संख्याएँ",
    "Mathematics · Class 6 · Chapter 10": "गणित · कक्षा 6 · अध्याय 10",
    "Negative numbers are not monsters. They are simply numbers in the opposite direction — from Shimla snow to lift basements.": "ऋणात्मक संख्याएँ कोई भूत नहीं हैं। वे केवल विपरीत दिशा की संख्याएँ हैं — शिमला की बर्फ से लेकर मॉल के बेसमेंट तक।",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "Zero is the mirror center. Step right for positive gain, step left for negative loss. Every step has an exact opposite.": "शून्य दर्पण का केंद्र है। लाभ के लिए दाईं ओर कदम बढ़ाएं, हानि के लिए बाईं ओर। प्रत्येक कदम का एक सटीक विपरीत होता है।",
    "Why Do We Need Negative Numbers?": "हमें ऋणात्मक संख्याओं की आवश्यकता क्यों है?",
    "If profit of ₹500 is +500, how do you write a loss of ₹500? As -500! If 2000 m above sea level is +2000, a submarine 500 m under water is -500. Negative numbers describe opposite directions.": "यदि ₹500 का लाभ +500 है, तो ₹500 की हानि कैसे लिखेंगे? -500! यदि समुद्र तल से 2000 मीटर ऊपर +2000 है, तो 500 मीटर नीचे पनडुब्बी -500 है। ऋणात्मक संख्याएं विपरीत दिशा दर्शाती हैं।",
    "Meet the Family of Integers": "पूर्णांकों के परिवार से मिलिए",
    "The collection of all whole numbers (0, 1, 2, 3...) together with negative numbers (-1, -2, -3...) forms the set of INTEGERS. Zero is unique: it is neither positive nor negative!": "सभी पूर्ण संख्याओं (0, 1, 2, 3...) और ऋणात्मक संख्याओं (-1, -2, -3...) का समूह पूर्णांक (Integers) कहलाता है। शून्य अनोखा है: यह न तो धनात्मक है और न ही ऋणात्मक!",
    "Try it: Explore the Number Line": "करके देखें: संख्या रेखा का अन्वेषण करें",
    "Drag the slider between -10 and +10. Watch how positive numbers glow teal on the right and negative numbers glow rose on the left.": "-10 से +10 के बीच स्लाइडर खिसकाएं। देखें कि कैसे धनात्मक संख्याएं दाईं ओर नीली चमकती हैं और ऋणात्मक संख्याएं बाईं ओर गुलाबी चमकती हैं।",
    "Any number to the right is always strictly greater than any number to its left!": "संख्या रेखा पर दाईं ओर स्थित कोई भी संख्या बाईं ओर स्थित किसी भी संख्या से हमेशा बड़ी होती है!",
    "Comparing Integers: Don't Be Fooled": "पूर्णांकों की तुलना: धोखे में न आएं",
    "Which is bigger: -2 or -10? On a cold night, -2°C is cold, but -10°C is freezing colder! On the number line, -2 lies to the RIGHT of -10. Therefore, -2 > -10.": "कौन सा बड़ा है: -2 या -10? ठंड की रात में, -2°C ठंडा है, लेकिन -10°C जमा देने वाला ठंडा है! संख्या रेखा पर -2, -10 के दाईं ओर है। इसलिए, -2 > -10।",
    "Absolute Value: Distance from Zero": "निरपेक्ष मान: शून्य से दूरी",
    "The absolute value |x| is the physical distance of a number from zero, ignoring its sign. |-7| = 7 and |+7| = 7. Distance is never negative!": "निरपेक्ष मान |x| किसी संख्या की शून्य से वास्तविक दूरी है, जिसमें उसके चिह्न को अनदेखा किया जाता है। |-7| = 7 और |+7| = 7। दूरी कभी ऋणात्मक नहीं होती!",
    "Additive Inverse: The Perfect Opposite": "योज्य प्रतिलोम: पूर्ण विपरीत साथी",
    "Every integer has an additive inverse: the number that cancels it out to zero. The inverse of +6 is -6, because (+6) + (-6) = 0. The inverse of -15 is +15.": "प्रत्येक पूर्णांक का एक योज्य प्रतिलोम होता है: वह संख्या जो इसे शून्य कर देती है। +6 का प्रतिलोम -6 है, क्योंकि (+6) + (-6) = 0। -15 का प्रतिलोम +15 है।",
    "Adding Integers on the Number Line": "संख्या रेखा पर पूर्णांकों का जोड़",
    "To add a POSITIVE number, jump to the RIGHT. To add a NEGATIVE number, jump to the LEFT. Start at -2 and add +5: jump 5 steps right to land on +3!": "धनात्मक संख्या जोड़ने के लिए दाईं ओर कूदें। ऋणात्मक संख्या जोड़ने के लिए बाईं ओर कूदें। -2 से शुरू करें और +5 जोड़ें: 5 कदम दाएं कूदकर +3 पर पहुंचेंगे!",
    "Try it: Two-Jump Calculator": "करके देखें: दो-कदम जोड़ कैलकुलेटर",
    "Choose your starting number A and the jump B. Watch the animated jump arc across the zero boundary.": "अपनी प्रारंभिक संख्या A और छलांग B चुनें। शून्य की सीमा के पार एनिमेटेड छलांग चाप देखें।",
    "Rules of Signs for Addition": "जोड़ के लिए चिह्नों के नियम",
    "Rule 1: Same signs? Add the numerical values and keep the common sign (-3 + -5 = -8). Rule 2: Different signs? Subtract the smaller value from the larger, and attach the sign of the larger number (-9 + 4 = -5).": "नियम 1: समान चिह्न? मानों को जोड़ें और वही चिह्न लगाएं (-3 + -5 = -8)। नियम 2: अलग चिह्न? बड़े में से छोटा घटाएं और बड़ी संख्या का चिह्न लगाएं (-9 + 4 = -5)।",
    "Subtracting Integers: Adding the Opposite": "पूर्णांकों का घटाव: विपरीत को जोड़ना",
    "Subtracting a number is identical to adding its Additive Inverse: a - b = a + (-b). When you subtract a negative, the two minuses cancel into a plus: 7 - (-3) = 7 + 3 = 10!": "किसी संख्या को घटाना उसके योज्य प्रतिलोम को जोड़ने के समान है: a - b = a + (-b)। जब आप ऋणात्मक संख्या घटाते हैं, तो दोनों माइनस मिलकर प्लस बन जाते हैं: 7 - (-3) = 7 + 3 = 10!",
    "Worked example — Submarine Dive": "हल किया गया उदाहरण — पनडुब्बी की डुबकी",
    "A submarine floats at 180 m below sea level (-180 m). It dives another 70 m deeper. What is its new depth?": "एक पनडुब्बी समुद्र तल से 180 मीटर नीचे (-180 मीटर) तैर रही है। यह 70 मीटर और गहरी डुबकी लगाती है। इसकी नई गहराई क्या है?",
    "Step 1: Starting depth is -180 m.": "स्टेप 1: प्रारंभिक गहराई -180 मीटर है।",
    "Step 2: Diving deeper means adding a negative depth: -180 + (-70).": "स्टेप 2: और गहरा जाने का अर्थ ऋणात्मक गहराई जोड़ना है: -180 + (-70)।",
    "Step 3: Both signs are negative, so add values: 180 + 70 = 250, sign is negative: -250 m.": "स्टेप 3: दोनों चिह्न ऋणात्मक हैं, अतः मान जोड़ें: 180 + 70 = 250, चिह्न ऋणात्मक: -250 मीटर।",
    "The submarine is now 250 m below sea level.": "पनडुब्बी अब समुद्र तल से 250 मीटर नीचे स्थित है।",
    "Worked example — Double Minus": "हल किया गया उदाहरण — दोहरा माइनस",
    "Evaluate: (-15) - (-25).": "मान ज्ञात कीजिए: (-15) - (-25)।",
    "Step 1: Subtraction of -25 turns into addition of its opposite (+25).": "स्टेप 1: -25 का घटाव इसके विपरीत (+25) के जोड़ में बदल जाता है।",
    "Step 2: Expression becomes (-15) + 25.": "स्टेप 2: व्यंजक बनता है (-15) + 25।",
    "Step 3: Different signs: subtract 25 - 15 = 10. Larger number (+25) is positive, so result is +10.": "स्टेप 3: भिन्न चिह्न: 25 - 15 = 10 घटाएं। बड़ी संख्या (+25) धनात्मक है, इसलिए परिणाम +10 है।",
    "Final answer is +10.": "अंतिम उत्तर +10 है।",
    "Which integer is strictly greater?": "इनमें से कौन सा पूर्णांक बड़ा है?",
    "-3": "-3",
    "-12": "-12",
    "-20": "-20",
    "On the number line, -3 is furthest to the right compared to -12 and -20, so -3 is the largest.": "संख्या रेखा पर, -12 और -20 की तुलना में -3 सबसे दाईं ओर है, इसलिए -3 सबसे बड़ा है।",
    "What is (-8) + (-6)?": "(-8) + (-6) का मान क्या होगा?",
    "-14": "-14",
    "+14": "+14",
    "-2": "-2",
    "Same signs: add 8 + 6 = 14, and keep the negative sign -> -14.": "समान चिह्न: 8 + 6 = 14 जोड़ें, और ऋणात्मक चिह्न बनाए रखें -> -14।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Thinking -10 is bigger than -2": "यह सोचना कि -10, -2 से बड़ा है",
    "Don't confuse absolute size with value! In debt, owing ₹10 is worse than owing ₹2. -2 > -10.": "वास्तविक मान को परिमाण से न मिलाएं! कर्ज में, ₹10 का कर्ज ₹2 के कर्ज से बुरा है। -2 > -10।",
    "Multiplying minus rules in addition": "जोड़ में गुणा के नियम लगाना",
    "-3 + -4 is NOT +7! Two minuses make plus ONLY in multiplication. In addition, you move deeper negative: -7.": "-3 + -4 कभी +7 नहीं होता! दो माइनस केवल गुणा में प्लस बनते हैं। जोड़ में आप और गहरे ऋणात्मक में जाते हैं: -7।",
    "Forgetting sign of larger number": "बड़ी संख्या का चिह्न भूल जाना",
    "When adding different signs like -12 + 5, the answer must carry the minus because |-12| > |5|: -7.": "विभिन्न चिह्नों को जोड़ते समय जैसे -12 + 5, उत्तर में माइनस आएगा क्योंकि |-12| > |5| है: -7।",
    "Where you meet it in real life": "दैनिक जीवन में पूर्णांक कहाँ मिलते हैं",
    "Elevator Floors": "लिफ्ट और इमारत के तल",
    "Ground floor is 0. 1st, 2nd, 3rd floors are +1, +2, +3. Underground parking floors are -1 and -2.": "भूतल 0 है। पहली, दूसरी मंजिलें +1, +2, +3 हैं। भूमिगत पार्किंग तल -1 और -2 हैं।",
    "Bank Passbook": "बैंक पासबुक",
    "Salary deposited is +₹25,000 (credit). Electricity bill paid is -₹1,200 (debit).": "वेतन जमा +₹25,000 (क्रेडिट) है। बिजली बिल भुगतान -₹1,200 (डेबिट) है।",
    "Extreme Temperatures": "चरम तापमान",
    "Siachen Glacier reaches -40°C in winter, while Rajasthan hits +48°C in summer. Difference is 88°C!": "सियाचिन ग्लेशियर सर्दियों में -40°C तक पहुंच जाता है, जबकि राजस्थान में +48°C। अंतर 88°C का है!",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Integers Z": "पूर्णांक Z",
    "{... -3, -2, -1, 0, 1, 2, 3 ...} Zero is neutral.": "{... -3, -2, -1, 0, 1, 2, 3 ...} शून्य तटस्थ है।",
    "Ordering": "क्रम",
    "Right > Left. Always! Any positive > 0 > any negative.": "दायाँ > बायाँ। हमेशा! कोई भी धनात्मक > 0 > कोई भी ऋणात्मक।",
    "Addition Rule": "जोड़ का नियम",
    "Same sign: add & keep. Diff sign: subtract & take larger sign.": "समान चिह्न: जोड़ें और वही चिह्न रखें। भिन्न चिह्न: घटाएं और बड़े का चिह्न लें।",
    "Subtraction Rule": "घटाव का नियम",
    "a - b = a + (-b). Minus of minus is plus: a - (-b) = a + b.": "a - b = a + (-b)। माइनस का माइनस प्लस है: a - (-b) = a + b।",
    "Absolute Value": "निरपेक्ष मान",
    "|x| = positive distance from zero. |-8| = 8.": "|x| = शून्य से धनात्मक दूरी। |-8| = 8।",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Mastery unlocked! You hold complete command over the integer number line.": "मास्टरी अनलॉक! पूर्णांक संख्या रेखा पर आपका पूर्ण नियंत्रण हो चुका है।",
    "From sub-zero temperatures to bank debits, you know how negative numbers operate!": "शून्य से नीचे के तापमान से लेकर बैंक डेबिट तक, आप ऋणात्मक संख्याओं के नियम पूरी तरह समझ गए हैं!",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Integers — Positive and Negative Numbers on a Number Line",
        "s": "Mathematics · Class 6 · Chapter 10",
        "b": "Negative numbers are not monsters. They are simply numbers in the opposite direction — from Shimla snow to lift basements.",
        "viz": "numline_overview",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "Zero is the mirror center. Step right for positive gain, step left for negative loss. Every step has an exact opposite.",
        "mentor": "Namaste! I am Acharya. Have you ever noticed a lift go to Basement -1 or -2? That is mathematics giving directions!",
        "viz": "mirror_zero",
    },
    {
        "kind": "text",
        "t": "Why Do We Need Negative Numbers?",
        "b": "If profit of ₹500 is +500, how do you write a loss of ₹500? As -500! If 2000 m above sea level is +2000, a submarine 500 m under water is -500. Negative numbers describe opposite directions.",
        "viz": "altitude_depth",
    },
    {
        "kind": "text",
        "t": "Meet the Family of Integers",
        "b": "The collection of all whole numbers (0, 1, 2, 3...) together with negative numbers (-1, -2, -3...) forms the set of INTEGERS. Zero is unique: it is neither positive nor negative!",
        "mentor": "Zero is like the referee in cricket: neither on the batting team nor bowling team, but standing in the exact middle!",
        "viz": "integer_sets",
    },
    {
        "kind": "sim",
        "sim": "numberline",
        "t": "Try it: Explore the Number Line",
        "b": "Drag the slider between -10 and +10. Watch how positive numbers glow teal on the right and negative numbers glow rose on the left.",
        "hint": "Any number to the right is always strictly greater than any number to its left!",
    },
    {
        "kind": "text",
        "t": "Comparing Integers: Don't Be Fooled",
        "b": "Which is bigger: -2 or -10? On a cold night, -2°C is cold, but -10°C is freezing colder! On the number line, -2 lies to the RIGHT of -10. Therefore, -2 > -10.",
        "viz": "comparison_visual",
    },
    {
        "kind": "text",
        "t": "Absolute Value: Distance from Zero",
        "b": "The absolute value |x| is the physical distance of a number from zero, ignoring its sign. |-7| = 7 and |+7| = 7. Distance is never negative!",
        "viz": "absolute_visual",
    },
    {
        "kind": "text",
        "t": "Additive Inverse: The Perfect Opposite",
        "b": "Every integer has an additive inverse: the number that cancels it out to zero. The inverse of +6 is -6, because (+6) + (-6) = 0. The inverse of -15 is +15.",
        "mentor": "If you take 6 steps forward and then 6 steps backward, where do you end up? Right back at 0!",
        "viz": "inverse_visual",
    },
    {
        "kind": "text",
        "t": "Adding Integers on the Number Line",
        "b": "To add a POSITIVE number, jump to the RIGHT. To add a NEGATIVE number, jump to the LEFT. Start at -2 and add +5: jump 5 steps right to land on +3!",
        "viz": "jump_visual",
    },
    {
        "kind": "sim",
        "sim": "addition_jump",
        "t": "Try it: Two-Jump Calculator",
        "b": "Choose your starting number A and the jump B. Watch the animated jump arc across the zero boundary.",
        "hint": "Adding positive = jump Right (→). Adding negative = jump Left (←).",
    },
    {
        "kind": "text",
        "t": "Rules of Signs for Addition",
        "b": "Rule 1: Same signs? Add the numerical values and keep the common sign (-3 + -5 = -8). Rule 2: Different signs? Subtract the smaller value from the larger, and attach the sign of the larger number (-9 + 4 = -5).",
        "mentor": "Think of it as two teams in a tug-of-war: if both pull in the negative direction, the rope moves further negative!",
        "viz": "tug_of_war",
    },
    {
        "kind": "text",
        "t": "Subtracting Integers: Adding the Opposite",
        "b": "Subtracting a number is identical to adding its Additive Inverse: a - b = a + (-b). When you subtract a negative, the two minuses cancel into a plus: 7 - (-3) = 7 + 3 = 10!",
        "viz": "subtraction_rule",
    },
    {
        "kind": "steps",
        "t": "Worked example — Submarine Dive",
        "b": "A submarine floats at 180 m below sea level (-180 m). It dives another 70 m deeper. What is its new depth?",
        "steps": [
            "Step 1: Starting depth is -180 m.",
            "Step 2: Diving deeper means adding a negative depth: -180 + (-70).",
            "Step 3: Both signs are negative, so add values: 180 + 70 = 250, sign is negative: -250 m.",
            "The submarine is now 250 m below sea level.",
        ],
        "viz": "altitude_depth",
    },
    {
        "kind": "steps",
        "t": "Worked example — Double Minus",
        "b": "Evaluate: (-15) - (-25).",
        "steps": [
            "Step 1: Subtraction of -25 turns into addition of its opposite (+25).",
            "Step 2: Expression becomes (-15) + 25.",
            "Step 3: Different signs: subtract 25 - 15 = 10. Larger number (+25) is positive, so result is +10.",
            "Final answer is +10.",
        ],
        "viz": "subtraction_rule",
    },
    {
        "kind": "check",
        "q": "Which integer is strictly greater?",
        "opts": ["-3", "-12", "-20"],
        "ans": 0,
        "why": "On the number line, -3 is furthest to the right compared to -12 and -20, so -3 is the largest.",
    },
    {
        "kind": "check",
        "q": "What is (-8) + (-6)?",
        "opts": ["-14", "+14", "-2"],
        "ans": 0,
        "why": "Same signs: add 8 + 6 = 14, and keep the negative sign -> -14.",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Avoid these classic student traps when solving integer problems.",
        "items": [
            [
                "Thinking -10 is bigger than -2",
                "Don't confuse absolute size with value! In debt, owing ₹10 is worse than owing ₹2. -2 > -10.",
            ],
            [
                "Multiplying minus rules in addition",
                "-3 + -4 is NOT +7! Two minuses make plus ONLY in multiplication. In addition, you move deeper negative: -7.",
            ],
            [
                "Forgetting sign of larger number",
                "When adding different signs like -12 + 5, the answer must carry the minus because |-12| > |5|: -7.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "From lifts to weather reports, integers are at work all around India.",
        "mentor": "Whenever you check cricket run-rate comparisons or winter weather in Himachal, integers make it simple!",
        "viz": "real_life_integers",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "The entire system of integers summarized in five golden rules.",
        "items": [
            [
                "Integers Z",
                "{... -3, -2, -1, 0, 1, 2, 3 ...} Zero is neutral.",
            ],
            [
                "Ordering",
                "Right > Left. Always! Any positive > 0 > any negative.",
            ],
            [
                "Addition Rule",
                "Same sign: add & keep. Diff sign: subtract & take larger sign.",
            ],
            [
                "Subtraction Rule",
                "a - b = a + (-b). Minus of minus is plus: a - (-b) = a + b.",
            ],
            [
                "Absolute Value",
                "|x| = positive distance from zero. |-8| = 8.",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Mastery unlocked! You hold complete command over the integer number line.",
        "b": "From sub-zero temperatures to bank debits, you know how negative numbers operate!",
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
  s += '<text x="200" y="165" font-size="60" text-anchor="middle">🔢</text>';
  return s + '</svg>';
}

function vizLineInt(val){
  let s = svgOpen();
  const y = 150, x1 = 40, x2 = 360, len = x2 - x1;
  s += '<line x1="'+x1+'" y1="'+y+'" x2="'+x2+'" y2="'+y+'" stroke="#5c7386" stroke-width="3"/>';
  s += '<polygon points="'+(x1-8)+','+y+' '+x1+','+(y-6)+' '+x1+','+(y+6)+'" fill="#ff5f78"/>';
  s += '<polygon points="'+(x2+8)+','+y+' '+x2+','+(y-6)+' '+x2+','+(y+6)+'" fill="#31e6c4"/>';
  for(let v = -10; v <= 10; v+=2){
    const tx = x1 + ((v + 10) / 20) * len;
    const isZero = v === 0;
    const col = v < 0 ? '#ff5f78' : (v > 0 ? '#31e6c4' : '#ffc247');
    s += '<line x1="'+tx+'" y1="'+(y-(isZero?16:10))+'" x2="'+tx+'" y2="'+(y+(isZero?16:10))+'" stroke="'+col+'" stroke-width="'+(isZero?3:1.5)+'"/>';
    s += '<text x="'+tx+'" y="'+(y+32)+'" fill="'+col+'" font-size="'+(isZero?15:12)+'" font-weight="'+(isZero?900:700)+'" text-anchor="middle">'+v+'</text>';
  }
  const curX = x1 + ((val + 10) / 20) * len;
  const colCur = val < 0 ? '#ff5f78' : (val > 0 ? '#31e6c4' : '#ffc247');
  s += '<circle cx="'+curX+'" cy="'+y+'" r="11" fill="'+colCur+'" stroke="#070c12" stroke-width="3"/>';
  s += '<text x="'+curX+'" y="'+(y-22)+'" fill="'+colCur+'" font-size="20" font-weight="900" text-anchor="middle">'+(val>0?'+'+val:val)+'</text>';
  return s + '</svg>';
}

function vizJumpArc(a, b){
  let s = svgOpen();
  const y = 170, x1 = 40, x2 = 360, len = x2 - x1;
  s += '<line x1="'+x1+'" y1="'+y+'" x2="'+x2+'" y2="'+y+'" stroke="#5c7386" stroke-width="3"/>';
  for(let v = -8; v <= 8; v+=2){
    const tx = x1 + ((v + 8) / 16) * len;
    const isZero = v === 0;
    s += '<line x1="'+tx+'" y1="'+(y-(isZero?14:8))+'" x2="'+tx+'" y2="'+(y+(isZero?14:8))+'" stroke="#8ba2b6" stroke-width="'+(isZero?3:1.5)+'"/>';
    s += '<text x="'+tx+'" y="'+(y+26)+'" fill="#8ba2b6" font-size="12" font-weight="700" text-anchor="middle">'+v+'</text>';
  }
  const ax = x1 + ((a + 8) / 16) * len;
  const res = Math.max(-8, Math.min(8, a + b));
  const bx = x1 + ((res + 8) / 16) * len;
  const midX = (ax + bx) / 2;
  const arcH = y - 60;
  const col = b >= 0 ? '#31e6c4' : '#ff5f78';
  s += '<circle cx="'+ax+'" cy="'+y+'" r="8" fill="#8ba2b6"/>';
  s += '<path d="M '+ax+' '+y+' Q '+midX+' '+arcH+' '+bx+' '+y+'" fill="none" stroke="'+col+'" stroke-width="3.5" stroke-dasharray="6 4"/>';
  s += '<circle cx="'+bx+'" cy="'+y+'" r="10" fill="'+col+'" stroke="#070c12" stroke-width="2.5"/>';
  s += '<text x="'+midX+'" y="'+(arcH-10)+'" fill="'+col+'" font-size="16" font-weight="800" text-anchor="middle">Jump '+(b>=0?'+'+b:b)+'</text>';
  s += '<text x="200" y="50" fill="#fff" font-size="18" font-weight="800" text-anchor="middle">'+a+' + ('+b+') = '+res+'</text>';
  return s + '</svg>';
}

const VIZ = {
  numline_overview: ()=> vizLineInt(4),
  mirror_zero: ()=> vizLineInt(0),
  altitude_depth: ()=> vizLineInt(-5),
  integer_sets: ()=> vizLineInt(6),
  comparison_visual: ()=> vizLineInt(-2),
  absolute_visual: ()=> vizLineInt(-7),
  inverse_visual: ()=> vizLineInt(6),
  jump_visual: ()=> vizJumpArc(-2, 5),
  tug_of_war: ()=> vizLineInt(-8),
  subtraction_rule: ()=> vizJumpArc(3, -5),
  real_life_integers: ()=> vizLineInt(-4),
};

const SIM = {
  numberline: ()=>'<label style="font-size:13.5px;color:var(--muted)">Position Slider: <b id="oVal" style="color:var(--teal)">0</b></label>'+
    '<input type="range" id="sVal" min="-10" max="10" value="0">'+
    '<div class="readout"><span>Direction: <b id="oDir">Zero (Center)</b></span><span>Absolute Value: <b id="oAbs">0</b></span></div>',

  addition_jump: ()=>'<label style="font-size:13.5px;color:var(--muted)">Start Number (A): <b id="oA" style="color:var(--teal)">-2</b></label>'+
    '<input type="range" id="sA" min="-6" max="6" value="-2">'+
    '<label style="font-size:13.5px;color:var(--muted)">Jump Amount (B): <b id="oB" style="color:var(--gold)">+5</b></label>'+
    '<input type="range" id="sB" min="-6" max="6" value="5">'+
    '<div class="readout"><span>Equation: <b id="oEq">-2 + 5 = 3</b></span></div>'
};

function simViz(name, v){
  if(name === "numberline") return vizLineInt(v);
  if(name === "addition_jump") return vizJumpArc(v.a, v.b);
  return vizLineInt(0);
}

function initSim(name){
  if(name === "numberline") return 0;
  if(name === "addition_jump") return {a: -2, b: 5};
  return 0;
}

function wireSim(name){
  if(name === "numberline"){
    const s = document.getElementById("sVal");
    const upd = ()=>{
      const v = +s.value;
      document.getElementById("oVal").textContent = v > 0 ? "+" + v : v;
      document.getElementById("oAbs").textContent = Math.abs(v);
      const oDir = document.getElementById("oDir");
      if(v > 0) oDir.innerHTML = "<span style='color:var(--teal)'>Positive (+ Right)</span>";
      else if(v < 0) oDir.innerHTML = "<span style='color:var(--red)'>Negative (- Left)</span>";
      else oDir.innerHTML = "<span style='color:var(--gold)'>Neutral Zero (Center)</span>";
      setVis(vizLineInt(v));
    };
    s.addEventListener("input", upd); upd();
  }
  if(name === "addition_jump"){
    const sA = document.getElementById("sA"), sB = document.getElementById("sB");
    const upd = ()=>{
      const a = +sA.value, b = +sB.value;
      document.getElementById("oA").textContent = a > 0 ? "+" + a : a;
      document.getElementById("oB").textContent = b > 0 ? "+" + b : b;
      document.getElementById("oEq").textContent = a + " + (" + b + ") = " + (a + b);
      setVis(vizJumpArc(a, b));
    };
    sA.addEventListener("input", upd); sB.addEventListener("input", upd); upd();
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class6_math_ch10_integers",
        title="Integers (Class 6 Math Ch 10)",
        grade_subject_sub="Class 6 Math · Chapter 10: Integers",
        chapter_num_label="Chapter 10",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class6_math_ch10_integers.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 10 Integers to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
