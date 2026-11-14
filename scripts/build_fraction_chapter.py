"""AASHA AIOS — Class 6 Math Chapter 7: Fractions Master Luxury Module."""

import json
from pathlib import Path
from build_gold_standard_chapters import get_base_css, build_lle_script, MASTER_WORDS, MASTER_PHRASES, CHAPTERS_DIR

# Chapter 7 Fractions specific words & phrases
CH7_WORDS = {
    "fraction": {"h": "भिन्न", "p": "फ़राक्शन"},
    "fractions": {"h": "भिन्न", "p": "फ़राक्शन्स"},
    "numerator": {"h": "अंश (ऊपर की संख्या)", "p": "न्युमरेटर"},
    "denominator": {"h": "हर (नीचे की कुल संख्या)", "p": "डिनोमिनेटर"},
    "equivalent": {"h": "समतुल्य (बराबर मान)", "p": "इक्विवेलेंट"},
    "proper": {"h": "उचित भिन्न", "p": "प्रॉपर"},
    "improper": {"h": "विषम भिन्न", "p": "इम्प्रॉपर"},
    "mixed": {"h": "मिश्रित भिन्न", "p": "मिक्स्ड"},
    "whole": {"h": "पूर्ण (पूरा हिस्सा)", "p": "होल"},
    "equal": {"h": "बराबर", "p": "इक्वल"},
    "parts": {"h": "हिस्से / भाग", "p": "पार्ट्स"},
    "slice": {"h": "टुकड़ा", "p": "स्लाइस"},
    "slices": {"h": "टुकड़े", "p": "स्लाइसेस"},
    "strip": {"h": "पट्टी", "p": "स्ट्रिप"},
    "divide": {"h": "बांटना / भाग देना", "p": "डिवाइड"},
    "divided": {"h": "बांटा गया", "p": "डिवाइडेड"},
    "simplest": {"h": "सरलतम रूप", "p": "सिम्प्लेस्ट"},
    "addition": {"h": "जोड़", "p": "एडिशन"},
    "subtraction": {"h": "घटाव", "p": "सब्ट्रैक्शन"},
    "multiply": {"h": "गुणा करना", "p": "मल्टिप्लाई"},
    "roti": {"h": "रोटी", "p": "रोटी"},
    "pizza": {"h": "पिज़्ज़ा", "p": "पिज़्ज़ा"},
    "shaded": {"h": "रंगा हुआ", "p": "शेडेड"},
    "unshaded": {"h": "बिना रंगा हुआ", "p": "अनशेडेड"},
}
WORDS = {**MASTER_WORDS, **CH7_WORDS}

CH7_PHRASES = {
    "Fractions — Understanding Parts, Slices and Equivalency": "भिन्न — हिस्सों, टुकड़ों और समतुल्यता की समझ",
    "Mathematics · Class 6 · Chapter 7": "गणित · कक्षा 6 · अध्याय 7",
    "Never fear fractions again. See them as warm roti slices, cricket overs, and sharing fairly with friends.": "भिन्नों से कभी न डरें। इन्हें गर्म रोटी के टुकड़ों, क्रिकेट ओवरों और दोस्तों में बराबर बांटने के रूप में देखें।",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "A fraction is simply a fair share: how many equal parts you take out of the total parts made.": "भिन्न वास्तव में एक निष्पक्ष हिस्सा है: कुल किए गए बराबर हिस्सों में से आपने कितने हिस्से लिए हैं।",
    "What is a Fraction?": "भिन्न क्या है?",
    "When a single whole object is divided into equal parts, each part is called a fraction. In a fraction a/b, the top number 'a' is the Numerator (अंश) and bottom 'b' is the Denominator (हर).": "जब किसी एक पूरी वस्तु को बराबर भागों में बांटा जाता है, तो प्रत्येक भाग भिन्न कहलाता है। भिन्न a/b में, ऊपर की संख्या 'a' अंश (Numerator) और नीचे की 'b' हर (Denominator) कहलाती है।",
    "Meet the Numerator and Denominator": "मिलिए अंश और हर से",
    "The Denominator (हर) tells you how many EQUAL pieces the whole was sliced into. The Numerator (अंश) tells you how many of those pieces you have in your hand.": "हर (Denominator) बताता है कि पूरे को कितने बराबर टुकड़ों में काटा गया था। अंश (Numerator) बताता है कि उन टुकड़ों में से कितने आपके हाथ में हैं।",
    "Try it: Slice the Roti": "करके देखें: रोटी के टुकड़े करें",
    "Move the slider to choose the total slices (Denominator) and slices taken (Numerator). Watch the pie chart update in real time.": "कुल टुकड़े (हर) और लिए गए टुकड़े (अंश) चुनने के लिए स्लाइडर चलाएं। देखें कि पाई चार्ट तुरंत कैसे बदलता है।",
    "Notice that all parts MUST be strictly equal in size for it to be a valid fraction.": "ध्यान दें कि एक मान्य भिन्न होने के लिए सभी हिस्सों का आकार बिल्कुल बराबर होना आवश्यक है।",
    "Proper Fractions: Less than a Whole": "उचित भिन्न: पूरे से कम",
    "When the Numerator is strictly smaller than the Denominator (like 1/2, 3/4, 5/8), it is called a PROPER FRACTION. It always represents less than 1 whole item.": "जब अंश, हर से छोटा होता है (जैसे 1/2, 3/4, 5/8), तो इसे उचित भिन्न (Proper Fraction) कहते हैं। यह हमेशा 1 पूरे से कम को दर्शाता है।",
    "Improper and Mixed Fractions": "विषम और मिश्रित भिन्न",
    "When you have 7 quarter-slices of roti, you write 7/4. The numerator is bigger! This is an IMPROPER FRACTION. Write it as 1 whole and 3/4, and it is a MIXED FRACTION: 1 3/4.": "जब आपके पास रोटी के 7 चौथाई टुकड़े हों, तो आप 7/4 लिखते हैं। यहाँ अंश बड़ा है! इसे विषम भिन्न (Improper Fraction) कहते हैं। इसे 1 पूरा और 3/4 लिखें, तो यह मिश्रित भिन्न है: 1 3/4।",
    "Equivalent Fractions: Different Look, Same Value": "समतुल्य भिन्न: अलग रूप, समान मान",
    "Eating 1 slice out of a 2-slice roti is the exact same amount of food as eating 2 slices out of a 4-slice roti! 1/2 = 2/4 = 3/6 = 4/8. These are EQUIVALENT FRACTIONS.": "2 टुकड़ों वाली रोटी में से 1 टुकड़ा खाना, 4 टुकड़ों वाली रोटी में से 2 टुकड़े खाने के बिल्कुल बराबर है! 1/2 = 2/4 = 3/6 = 4/8। इन्हें समतुल्य भिन्न (Equivalent Fractions) कहते हैं।",
    "Try it: Equivalent Fraction Multiplier": "करके देखें: समतुल्य भिन्न गुणक",
    "Slide the multiplier m. Notice that multiplying both top and bottom by m never changes the total shaded length.": "गुणक m को स्लाइड करें। ध्यान दें कि ऊपर और नीचे दोनों को m से गुणा करने पर कुल रंगे हुए हिस्से की लंबाई कभी नहीं बदलती।",
    "To make an equivalent fraction, multiply or divide BOTH numerator and denominator by the exact same non-zero number.": "समतुल्य भिन्न बनाने के लिए, अंश और हर दोनों को एक ही गैर-शून्य संख्या से गुणा या भाग करें।",
    "Simplest Form (Lowest Terms)": "सरलतम रूप (न्यूनतम पद)",
    "A fraction is in its simplest form when the only common factor between numerator and denominator is 1. To simplify 12/16, divide both by 4 to get 3/4.": "एक भिन्न अपने सरलतम रूप में तब होती है जब अंश और हर के बीच केवल 1 ही उभयनिष्ठ गुणनखंड हो। 12/16 को सरल करने के लिए दोनों को 4 से भाग देकर 3/4 प्राप्त करें।",
    "Fractions on the Number Line": "संख्या रेखा पर भिन्न",
    "Draw 0 and 1. If the denominator is 4, divide the space between 0 and 1 into 4 equal steps: 0/4, 1/4, 2/4, 3/4, 4/4. Each step is 1/4 of a unit!": "0 और 1 बनाएं। यदि हर 4 है, तो 0 और 1 के बीच की दूरी को 4 बराबर कदमों में बांटें: 0/4, 1/4, 2/4, 3/4, 4/4। प्रत्येक कदम इकाई का 1/4 है!",
    "Try it: Walk the Number Line": "करके देखें: संख्या रेखा पर चलें",
    "Move the slider to take fraction steps between 0 and 1. Watch where the marker lands.": "0 और 1 के बीच भिन्न कदम उठाने के लिए स्लाइडर खिसकाएं। देखें कि मार्कर कहाँ रुकता है।",
    "Like and Unlike Fractions": "समान और असमान भिन्न",
    "Fractions with the EXACT SAME denominator (like 2/7, 5/7, 6/7) are called LIKE FRACTIONS. Comparing and adding them is as simple as adding standard numbers.": "समान हर वाले भिन्नों (जैसे 2/7, 5/7, 6/7) को समान भिन्न (Like Fractions) कहते हैं। इनकी तुलना और जोड़ करना सामान्य संख्याओं जितना आसान है।",
    "Adding Like Fractions": "समान भिन्नों का जोड़",
    "When denominators match, DO NOT add the denominators! Keep the denominator the same and simply add the numerators: 2/7 + 3/7 = (2+3)/7 = 5/7.": "जब हर समान हों, तो हरों को कभी न जोड़ें! हर को वही रहने दें और केवल अंशों को जोड़ें: 2/7 + 3/7 = (2+3)/7 = 5/7।",
    "Worked example — Roti Sharing": "हल किया गया उदाहरण — रोटी का बंटवारा",
    "A plate has a paratha cut into 8 equal wedges. Kabir eats 3 wedges and Priya eats 2 wedges. What fraction of the paratha did they eat together?": "एक प्लेट में पराठे को 8 बराबर टुकड़ों में काटा गया है। कबीर 3 टुकड़े और प्रिया 2 टुकड़े खाती है। दोनों ने मिलकर पराठे का कुल कितना हिस्सा खाया?",
    "Step 1: Kabir ate 3/8 of the paratha.": "स्टेप 1: कबीर ने पराठे का 3/8 हिस्सा खाया।",
    "Step 2: Priya ate 2/8 of the paratha.": "स्टेप 2: प्रिया ने पराठे का 2/8 हिस्सा खाया।",
    "Step 3: Both denominators are 8, so add numerators: 3/8 + 2/8 = 5/8.": "स्टेप 3: दोनों के हर 8 हैं, इसलिए अंशों को जोड़ें: 3/8 + 2/8 = 5/8।",
    "Together they ate 5/8 of the paratha, leaving 3/8 on the plate.": "दोनों ने मिलकर 5/8 पराठा खाया, और प्लेट में 3/8 बचा रहा।",
    "Worked example — Finding Equivalent Fraction": "हल किया गया उदाहरण — समतुल्य भिन्न ज्ञात करना",
    "Find an equivalent fraction of 2/5 with denominator 20.": "2/5 के समतुल्य वह भिन्न ज्ञात कीजिए जिसका हर 20 हो।",
    "Step 1: Check how 5 becomes 20: 20 ÷ 5 = 4.": "स्टेप 1: देखें कि 5 से 20 कैसे बनता है: 20 ÷ 5 = 4।",
    "Step 2: Multiply both numerator and denominator by 4: (2 × 4) / (5 × 4) = 8/20.": "स्टेप 2: अंश और हर दोनों को 4 से गुणा करें: (2 × 4) / (5 × 4) = 8/20।",
    "So 8/20 is the equivalent fraction.": "अतः 8/20 अभीष्ट समतुल्य भिन्न है।",
    "Worked example — Mixed Fraction Conversion": "हल किया गया उदाहरण — मिश्रित भिन्न में बदलना",
    "Express 17/5 as a mixed fraction.": "17/5 को मिश्रित भिन्न के रूप में व्यक्त कीजिए।",
    "Step 1: Divide 17 by 5: 17 ÷ 5 gives quotient 3 with remainder 2.": "स्टेप 1: 17 को 5 से भाग दें: 17 ÷ 5 भागफल 3 और शेषफल 2 देता है।",
    "Step 2: The quotient 3 becomes the whole number part.": "स्टेप 2: भागफल 3 पूरा (पूर्णांक) हिस्सा बनता है।",
    "Step 3: The remainder 2 becomes the new numerator over 5: 3 2/5.": "स्टेप 3: शेषफल 2 हर 5 के ऊपर नया अंश बनता है: 3 2/5।",
    "So 17/5 equals 3 wholes and 2/5.": "अतः 17/5 का मान 3 पूर्णांक 2/5 है।",
    "Which of these is a Proper Fraction?": "इनमें से कौन सी एक उचित भिन्न (Proper Fraction) है?",
    "3/4": "3/4",
    "7/5": "7/5",
    "9/9": "9/9",
    "In 3/4, numerator 3 is strictly less than denominator 4, so it is a proper fraction (less than 1).": "3/4 में, अंश 3 हर 4 से छोटा है, इसलिए यह उचित भिन्न है (1 से कम)।",
    "What is the simplest form of 18/24?": "18/24 का सरलतम रूप क्या है?",
    "3/4": "3/4",
    "6/8": "6/8",
    "9/12": "9/12",
    "Divide both 18 and 24 by their Highest Common Factor (6): 18÷6 = 3, and 24÷6 = 4. Simplest form is 3/4.": "18 और 24 दोनों को उनके महत्तम समापवर्तक (6) से भाग दें: 18÷6 = 3, और 24÷6 = 4। सरलतम रूप 3/4 है।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Adding denominators": "हरों को आपस में जोड़ देना",
    "Never add denominators! 1/4 + 2/4 is 3/4, NOT 3/8. The slice size did not change.": "हरों को कभी न जोड़ें! 1/4 + 2/4 का मान 3/4 होता है, 3/8 नहीं। टुकड़ों का आकार नहीं बदला है।",
    "Unequal parts": "असमान हिस्से कर देना",
    "Fractions ONLY work if every single part is exactly the same size. 3 unequal pieces are not thirds!": "भिन्न केवल तभी मान्य होते हैं जब प्रत्येक हिस्सा बिल्कुल बराबर आकार का हो। 3 असमान टुकड़े 1/3 नहीं होते!",
    "Multiplying only the top": "केवल अंश को गुणा करना",
    "To keep equivalence, you must multiply or divide BOTH the numerator and denominator by the exact same number.": "समतुल्यता बनाए रखने के लिए, अंश और हर दोनों को एक ही संख्या से गुणा या भाग करना अनिवार्य है।",
    "Where you meet it in real life": "दैनिक जीवन में भिन्न कहाँ मिलते हैं",
    "Cricket Overs": "क्रिकेट के ओवर",
    "When a bowler bowls 3 balls in an over, they have bowled 3/6 (or 1/2) of that over.": "जब कोई गेंदबाज ओवर में 3 गेंदें फेंकता है, तो उसने उस ओवर का 3/6 (या 1/2) हिस्सा पूरा कर लिया होता है।",
    "Kitchen Recipes": "रसोई के नुस्खे और नाप",
    "A tea recipe calling for 1/2 cup milk and 1/4 teaspoon cardamom uses fractions to keep the flavor balanced.": "चाय की विधि में 1/2 कप दूध और 1/4 चम्मच इलायची का उपयोग स्वाद को संतुलित रखने के लिए भिन्न का उपयोग करता है।",
    "Time and Clocks": "समय और घड़ियाँ",
    "Quarter past four is 1/4 of an hour past 4 (15 minutes). Half past four is 1/2 of an hour (30 minutes).": "सवा चार का अर्थ 4 बजकर 1/4 घंटा (15 मिनट) है। साढ़े चार का अर्थ 1/2 घंटा (30 मिनट) है।",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Fraction a/b": "भिन्न a/b",
    "a = Numerator (parts taken), b = Denominator (total equal parts)": "a = अंश (लिए गए भाग), b = हर (कुल बराबर भाग)",
    "Proper Fraction": "उचित भिन्न",
    "a < b (value strictly less than 1, e.g. 3/5)": "a < b (मान 1 से कम, जैसे 3/5)",
    "Improper & Mixed": "विषम और मिश्रित भिन्न",
    "a >= b (value >= 1, e.g. 7/4 = 1 3/4)": "a >= b (मान 1 या अधिक, जैसे 7/4 = 1 3/4)",
    "Equivalent Rule": "समतुल्य नियम",
    "Multiply or divide top and bottom by same number (1/2 = 2/4 = 3/6)": "अंश और हर दोनों को एक ही संख्या से गुणा या भाग करें (1/2 = 2/4 = 3/6)",
    "Like Addition": "समान भिन्नों का जोड़",
    "Keep denominator, add numerators: a/c + b/c = (a+b)/c": "हर को वही रखें, अंशों को जोड़ें: a/c + b/c = (a+b)/c",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Mastery unlocked! You understand the foundational architecture of fractions.": "मास्टरी अनलॉक! आप भिन्नों की आधारभूत संरचना को पूरी तरह समझ चुके हैं।",
    "You have completed all conceptual slides, interactive simulations, and worked examples.": "आपने सभी वैचारिक स्लाइड्स, इंटरैक्टिव सिमुलेशन और हल किए गए उदाहरण पूरे कर लिए हैं।",
}
PHRASES = {**MASTER_PHRASES, **CH7_PHRASES}

SLIDES = [
    {
        "kind": "title",
        "t": "Fractions — Understanding Parts, Slices and Equivalency",
        "s": "Mathematics · Class 6 · Chapter 7",
        "b": "Never fear fractions again. See them as warm roti slices, cricket overs, and sharing fairly with friends.",
        "viz": "pie_half",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "A fraction is simply a fair share: how many equal parts you take out of the total parts made.",
        "mentor": "Namaste! I am Acharya. Whenever you share a paratha equally with your sister, you are doing fraction maths! Let's explore together.",
        "viz": "roti_slices",
    },
    {
        "kind": "text",
        "t": "What is a Fraction?",
        "b": "When a single whole object is divided into equal parts, each part is called a fraction. In a fraction a/b, the top number 'a' is the Numerator (अंश) and bottom 'b' is the Denominator (हर).",
        "viz": "fraction_def",
    },
    {
        "kind": "text",
        "t": "Meet the Numerator and Denominator",
        "b": "The Denominator (हर) tells you how many EQUAL pieces the whole was sliced into. The Numerator (अंश) tells you how many of those pieces you have in your hand.",
        "mentor": "Remember: Denominator is Down (नीचे = कुल टुकड़े), Numerator is North (ऊपर = आपके हाथ में टुकड़े)!",
        "viz": "num_den_visual",
    },
    {
        "kind": "sim",
        "sim": "slices",
        "t": "Try it: Slice the Roti",
        "b": "Move the slider to choose the total slices (Denominator) and slices taken (Numerator). Watch the pie chart update in real time.",
        "hint": "Notice that all parts MUST be strictly equal in size for it to be a valid fraction.",
    },
    {
        "kind": "text",
        "t": "Proper Fractions: Less than a Whole",
        "b": "When the Numerator is strictly smaller than the Denominator (like 1/2, 3/4, 5/8), it is called a PROPER FRACTION. It always represents less than 1 whole item.",
        "viz": "proper_fractions",
    },
    {
        "kind": "text",
        "t": "Improper and Mixed Fractions",
        "b": "When you have 7 quarter-slices of roti, you write 7/4. The numerator is bigger! This is an IMPROPER FRACTION. Write it as 1 whole and 3/4, and it is a MIXED FRACTION: 1 3/4.",
        "mentor": "7 quarter-slices = 4 slices (1 full roti) + 3 extra slices = 1 3/4 rotis! Exactly the same amount of food.",
        "viz": "improper_visual",
    },
    {
        "kind": "text",
        "t": "Equivalent Fractions: Different Look, Same Value",
        "b": "Eating 1 slice out of a 2-slice roti is the exact same amount of food as eating 2 slices out of a 4-slice roti! 1/2 = 2/4 = 3/6 = 4/8. These are EQUIVALENT FRACTIONS.",
        "viz": "equivalent_bars",
    },
    {
        "kind": "sim",
        "sim": "equivalent",
        "t": "Try it: Equivalent Fraction Multiplier",
        "b": "Slide the multiplier m. Notice that multiplying both top and bottom by m never changes the total shaded length.",
        "hint": "To make an equivalent fraction, multiply or divide BOTH numerator and denominator by the exact same non-zero number.",
    },
    {
        "kind": "text",
        "t": "Simplest Form (Lowest Terms)",
        "b": "A fraction is in its simplest form when the only common factor between numerator and denominator is 1. To simplify 12/16, divide both by 4 to get 3/4.",
        "viz": "simplify_visual",
    },
    {
        "kind": "text",
        "t": "Fractions on the Number Line",
        "b": "Draw 0 and 1. If the denominator is 4, divide the space between 0 and 1 into 4 equal steps: 0/4, 1/4, 2/4, 3/4, 4/4. Each step is 1/4 of a unit!",
        "viz": "numberline_static",
    },
    {
        "kind": "sim",
        "sim": "numberline",
        "t": "Try it: Walk the Number Line",
        "b": "Move the slider to take fraction steps between 0 and 1. Watch where the marker lands.",
        "hint": "Between any two whole numbers, there are infinite fraction points waiting to be discovered!",
    },
    {
        "kind": "text",
        "t": "Like and Unlike Fractions",
        "b": "Fractions with the EXACT SAME denominator (like 2/7, 5/7, 6/7) are called LIKE FRACTIONS. Comparing and adding them is as simple as adding standard numbers.",
        "viz": "like_fractions",
    },
    {
        "kind": "text",
        "t": "Adding Like Fractions",
        "b": "When denominators match, DO NOT add the denominators! Keep the denominator the same and simply add the numerators: 2/7 + 3/7 = (2+3)/7 = 5/7.",
        "mentor": "If you have 2 slices of a 7-slice pizza and get 3 more, you have 5 slices of a 7-slice pizza! The pizza size didn't turn into 14 slices!",
        "viz": "add_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — Roti Sharing",
        "b": "A plate has a paratha cut into 8 equal wedges. Kabir eats 3 wedges and Priya eats 2 wedges. What fraction of the paratha did they eat together?",
        "steps": [
            "Step 1: Kabir ate 3/8 of the paratha.",
            "Step 2: Priya ate 2/8 of the paratha.",
            "Step 3: Both denominators are 8, so add numerators: 3/8 + 2/8 = 5/8.",
            "Together they ate 5/8 of the paratha, leaving 3/8 on the plate.",
        ],
        "viz": "roti_slices",
    },
    {
        "kind": "steps",
        "t": "Worked example — Finding Equivalent Fraction",
        "b": "Find an equivalent fraction of 2/5 with denominator 20.",
        "steps": [
            "Step 1: Check how 5 becomes 20: 20 ÷ 5 = 4.",
            "Step 2: Multiply both numerator and denominator by 4: (2 × 4) / (5 × 4) = 8/20.",
            "So 8/20 is the equivalent fraction.",
        ],
        "viz": "equivalent_bars",
    },
    {
        "kind": "steps",
        "t": "Worked example — Mixed Fraction Conversion",
        "b": "Express 17/5 as a mixed fraction.",
        "steps": [
            "Step 1: Divide 17 by 5: 17 ÷ 5 gives quotient 3 with remainder 2.",
            "Step 2: The quotient 3 becomes the whole number part.",
            "Step 3: The remainder 2 becomes the new numerator over 5: 3 2/5.",
            "So 17/5 equals 3 wholes and 2/5.",
        ],
        "viz": "improper_visual",
    },
    {
        "kind": "check",
        "q": "Which of these is a Proper Fraction?",
        "opts": ["3/4", "7/5", "9/9"],
        "ans": 0,
        "why": "In 3/4, numerator 3 is strictly less than denominator 4, so it is a proper fraction (less than 1).",
    },
    {
        "kind": "check",
        "q": "What is the simplest form of 18/24?",
        "opts": ["3/4", "6/8", "9/12"],
        "ans": 0,
        "why": "Divide both 18 and 24 by their Highest Common Factor (6): 18÷6 = 3, and 24÷6 = 4. Simplest form is 3/4.",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Watch out for these common blunders before taking your school exam.",
        "items": [
            [
                "Adding denominators",
                "Never add denominators! 1/4 + 2/4 is 3/4, NOT 3/8. The slice size did not change.",
            ],
            [
                "Unequal parts",
                "Fractions ONLY work if every single part is exactly the same size. 3 unequal pieces are not thirds!",
            ],
            [
                "Multiplying only the top",
                "To keep equivalence, you must multiply or divide BOTH the numerator and denominator by the exact same number.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "Fractions are everywhere around you every single day in India.",
        "mentor": "From the cricket pitch to your mother's chai, fractions are the heartbeat of precise measurement!",
        "viz": "real_life_visual",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "The core rules of fractions, crystal clear in one glance.",
        "items": [
            [
                "Fraction a/b",
                "a = Numerator (parts taken), b = Denominator (total equal parts)",
            ],
            [
                "Proper Fraction",
                "a < b (value strictly less than 1, e.g. 3/5)",
            ],
            [
                "Improper & Mixed",
                "a >= b (value >= 1, e.g. 7/4 = 1 3/4)",
            ],
            [
                "Equivalent Rule",
                "Multiply or divide top and bottom by same number (1/2 = 2/4 = 3/6)",
            ],
            [
                "Like Addition",
                "Keep denominator, add numerators: a/c + b/c = (a+b)/c",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Mastery unlocked! You understand the foundational architecture of fractions.",
        "b": "You have completed all conceptual slides, interactive simulations, and worked examples.",
    },
]


def get_ch7_svg_and_sims() -> str:
    return """
<script>
const VB = 'viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet"';
function svgOpen(extra){ return '<svg '+VB+' font-family="system-ui,sans-serif" '+(extra||"")+'>'; }

/* Visual 1: Pie slice generator */
function vizPie(num, den){
  let s = svgOpen();
  const cx = 200, cy = 140, r = 100;
  s += '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="#122436" stroke="#1d4055" stroke-width="3"/>';
  const sliceAngle = (2 * Math.PI) / den;
  for(let i=0; i<den; i++){
    const a1 = i * sliceAngle - Math.PI/2;
    const a2 = (i + 1) * sliceAngle - Math.PI/2;
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const largeArc = sliceAngle > Math.PI ? 1 : 0;
    const isShaded = i < num;
    const fill = isShaded ? 'url(#gTeal)' : 'rgba(255,255,255,.03)';
    const stroke = '#234a66';
    const d = 'M '+cx+' '+cy+' L '+x1+' '+y1+' A '+r+' '+r+' 0 '+largeArc+' 1 '+x2+' '+y2+' Z';
    s += '<path d="'+d+'" fill="'+fill+'" stroke="'+stroke+'" stroke-width="2"/>';
  }
  s += '<defs><linearGradient id="gTeal" x1="0" y1="0" x2="1" y2="1">'+
       '<stop offset="0%" stop-color="#31e6c4"/><stop offset="100%" stop-color="#19b79e"/></linearGradient></defs>';
  s += '<rect x="120" y="255" width="160" height="36" rx="8" fill="#122436" stroke="rgba(49,230,196,.3)"/>';
  s += '<text x="200" y="279" fill="#31e6c4" font-size="19" font-weight="800" text-anchor="middle">'+num+' / '+den+' Shaded</text>';
  return s + '</svg>';
}

/* Visual 2: Fraction Strip */
function vizStrip(num, den){
  let s = svgOpen();
  const x = 30, y = 110, w = 340, h = 60;
  const boxW = w / den;
  s += '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="10" fill="#0e1f2e" stroke="#1f445e" stroke-width="2.5"/>';
  for(let i=0; i<den; i++){
    const bx = x + i * boxW;
    const isShaded = i < num;
    const fill = isShaded ? '#31e6c4' : 'transparent';
    const fillOp = isShaded ? '.85' : '0';
    s += '<rect x="'+bx+'" y="'+y+'" width="'+boxW+'" height="'+h+'" fill="'+fill+'" fill-opacity="'+fillOp+'" stroke="#1f445e" stroke-width="2"/>';
    s += '<text x="'+(bx+boxW/2)+'" y="'+(y+h/2+6)+'" fill="'+(isShaded?'#04201c':'#8ba2b6')+'" font-size="14" font-weight="800" text-anchor="middle">1/'+den+'</text>';
  }
  s += '<text x="200" y="215" fill="#ffc247" font-size="17" font-weight="800" text-anchor="middle">'+num+' of '+den+' equal parts = '+num+'/'+den+'</text>';
  return s + '</svg>';
}

/* Visual 3: Equivalent Bars comparison */
function vizEquivalent(m){
  let s = svgOpen();
  const x = 40, w = 320, h = 42;
  // Bar 1: 1/2
  s += '<text x="'+x+'" y="45" fill="#8ba2b6" font-size="14" font-weight="700">1 / 2 (Original)</text>';
  s += '<rect x="'+x+'" y="55" width="'+w+'" height="'+h+'" rx="8" fill="#0e1f2e" stroke="#1f445e" stroke-width="2"/>';
  s += '<rect x="'+x+'" y="55" width="'+(w/2)+'" height="'+h+'" rx="8" fill="#31e6c4" fill-opacity=".8"/>';
  s += '<text x="'+(x+w/4)+'" y="82" fill="#04201c" font-size="16" font-weight="900" text-anchor="middle">1 / 2</text>';

  // Bar 2: (1*m)/(2*m)
  const num2 = 1 * m, den2 = 2 * m;
  const boxW = w / den2;
  s += '<text x="'+x+'" y="145" fill="#ffc247" font-size="14" font-weight="700">'+num2+' / '+den2+' (Multiplied by '+m+')</text>';
  s += '<rect x="'+x+'" y="155" width="'+w+'" height="'+h+'" rx="8" fill="#0e1f2e" stroke="#1f445e" stroke-width="2"/>';
  for(let i=0; i<den2; i++){
    const bx = x + i * boxW;
    const isShaded = i < num2;
    s += '<rect x="'+bx+'" y="155" width="'+boxW+'" height="'+h+'" fill="'+(isShaded?'#ffc247':'transparent')+'" fill-opacity="'+(isShaded?'.85':'0')+'" stroke="#1f445e" stroke-width="1.5"/>';
  }
  s += '<line x1="'+(x+w/2)+'" y1="55" x2="'+(x+w/2)+'" y2="200" stroke="#ff5f78" stroke-width="2.5" stroke-dasharray="5 5"/>';
  s += '<text x="200" y="245" fill="#4ade80" font-size="16" font-weight="800" text-anchor="middle">Same shaded length: 1/2 = '+num2+'/'+den2+' ✓</text>';
  return s + '</svg>';
}

/* Visual 4: Number line with fraction marker */
function vizNumLine(step, den){
  let s = svgOpen();
  const y = 140, x1 = 40, x2 = 360, len = x2 - x1;
  s += '<line x1="'+x1+'" y1="'+y+'" x2="'+x2+'" y2="'+y+'" stroke="#5c7386" stroke-width="3"/>';
  // Arrow heads
  s += '<polygon points="'+(x1-8)+','+y+' '+x1+','+(y-6)+' '+x1+','+(y+6)+'" fill="#5c7386"/>';
  s += '<polygon points="'+(x2+8)+','+y+' '+x2+','+(y-6)+' '+x2+','+(y+6)+'" fill="#5c7386"/>';

  for(let i=0; i<=den; i++){
    const tx = x1 + (i / den) * len;
    s += '<line x1="'+tx+'" y1="'+(y-12)+'" x2="'+tx+'" y2="'+(y+12)+'" stroke="#8ba2b6" stroke-width="2"/>';
    s += '<text x="'+tx+'" y="'+(y+32)+'" fill="#8ba2b6" font-size="13" font-weight="700" text-anchor="middle">'+i+'/'+den+'</text>';
  }
  const curX = x1 + (step / den) * len;
  s += '<circle cx="'+curX+'" cy="'+y+'" r="9" fill="#ffc247" stroke="#070c12" stroke-width="3"/>';
  s += '<path d="M '+x1+' '+y+' Q '+((x1+curX)/2)+' '+(y-65)+' '+curX+' '+y+'" fill="none" stroke="#31e6c4" stroke-width="3" stroke-dasharray="6 4"/>';
  s += '<text x="'+curX+'" y="'+(y-22)+'" fill="#ffc247" font-size="16" font-weight="900" text-anchor="middle">'+step+'/'+den+'</text>';
  return s + '</svg>';
}

/* Named visuals */
const VIZ = {
  pie_half: ()=> vizPie(1, 2),
  roti_slices: ()=> vizPie(3, 8),
  fraction_def: ()=> vizStrip(3, 4),
  num_den_visual: ()=> vizStrip(2, 5),
  proper_fractions: ()=> vizStrip(3, 5),
  improper_visual: ()=> vizStrip(7, 4),
  equivalent_bars: ()=> vizEquivalent(2),
  simplify_visual: ()=> vizEquivalent(3),
  numberline_static: ()=> vizNumLine(3, 4),
  like_fractions: ()=> vizStrip(4, 7),
  add_visual: ()=> vizStrip(5, 8),
  real_life_visual: ()=> vizPie(4, 6),
};

/* Interactive Sim Controllers */
const SIM = {
  slices: ()=>'<label style="font-size:13.5px;color:var(--muted)">Denominator (Total Slices): <b id="oDen" style="color:var(--teal)">4</b></label>'+
    '<input type="range" id="sDen" min="2" max="10" value="4">'+
    '<label style="font-size:13.5px;color:var(--muted)">Numerator (Slices Taken): <b id="oNum" style="color:var(--gold)">3</b></label>'+
    '<input type="range" id="sNum" min="0" max="4" value="3">'+
    '<div class="readout"><span>Fraction: <b id="oFrac">3 / 4</b></span><span id="oType" style="color:var(--gold)">Proper fraction</span></div>',

  equivalent: ()=>'<label style="font-size:13.5px;color:var(--muted)">Multiplier (m): <b id="oM" style="color:var(--gold)">2</b></label>'+
    '<input type="range" id="sM" min="1" max="5" value="2">'+
    '<div class="readout"><span>1 / 2 = <b id="oEq">2 / 4</b></span><span style="color:var(--green)">100% Equivalent</span></div>',

  numberline: ()=>'<label style="font-size:13.5px;color:var(--muted)">Steps on 4ths: <b id="oStep" style="color:var(--gold)">2 / 4</b></label>'+
    '<input type="range" id="sStep" min="0" max="4" value="2">'+
    '<div class="readout"><span>Position: <b id="oPos">0.50 (Halfway)</b></span></div>'
};

function simViz(name, v){
  if(name === "slices") return vizPie(v.n, v.d);
  if(name === "equivalent") return vizEquivalent(v);
  if(name === "numberline") return vizNumLine(v, 4);
  return vizPie(1, 2);
}

function initSim(name){
  if(name === "slices") return {n: 3, d: 4};
  if(name === "equivalent") return 2;
  if(name === "numberline") return 2;
  return 0;
}

function wireSim(name){
  if(name === "slices"){
    const sD = document.getElementById("sDen"), sN = document.getElementById("sNum");
    const upd = ()=>{
      const d = +sD.value;
      sN.max = d;
      const n = Math.min(+sN.value, d);
      document.getElementById("oDen").textContent = d;
      document.getElementById("oNum").textContent = n;
      document.getElementById("oFrac").textContent = n + " / " + d;
      const oT = document.getElementById("oType");
      if(n === d) oT.textContent = "1 Whole (4/4 = 1)";
      else if(n === 0) oT.textContent = "Zero pieces (0)";
      else oT.textContent = "Proper fraction (< 1)";
      setVis(vizPie(n, d));
    };
    sD.addEventListener("input", upd); sN.addEventListener("input", upd); upd();
  }
  if(name === "equivalent"){
    const s = document.getElementById("sM");
    const upd = ()=>{
      const m = +s.value;
      document.getElementById("oM").textContent = m;
      document.getElementById("oEq").textContent = (1*m) + " / " + (2*m);
      setVis(vizEquivalent(m));
    };
    s.addEventListener("input", upd); upd();
  }
  if(name === "numberline"){
    const s = document.getElementById("sStep");
    const upd = ()=>{
      const step = +s.value;
      document.getElementById("oStep").textContent = step + " / 4";
      document.getElementById("oPos").textContent = (step/4).toFixed(2);
      setVis(vizNumLine(step, 4));
    };
    s.addEventListener("input", upd); upd();
  }
}
</script>
"""


def build_render_engine(slides: list[dict], chapter_subtitle: str) -> str:
    slides_json = json.dumps(slides, ensure_ascii=False)
    return f"""
<script>
const SLIDES = {slides_json};
const card = document.getElementById("card");
const prog = document.getElementById("prog");
const prevB = document.getElementById("prev");
const nextB = document.getElementById("next");
const hiAll = document.getElementById("hiAll");
let i = 0, allHi = false;

const T = (s)=>'<span data-lang>'+esc(s)+'</span>';

function setVis(html){{ const v=document.getElementById("vis"); if(v) v.innerHTML = html; }}

function render(){{
  const s = SLIDES[i];
  const hasSim = s.kind === "sim";
  card.className = "card" + (s.kind === "end" ? "" : " split");
  let title="", txt="", vis="", ctl="";

  switch(s.kind){{
    case "title":
      title = '<div class="kindrow"><span class="kind">Chapter 7</span></div><h1 data-lang>'+esc(s.t)+'</h1>';
      txt = '<p class="sub" data-lang>'+esc(s.s||"")+'</p><p class="b" data-lang>'+esc(s.b||"")+'</p>';
      vis = vizPie(3, 4);
      break;
    case "text":
      title = '<div class="kindrow"><span class="kind">Concept</span></div><h2 data-lang>'+esc(s.t)+'</h2>';
      txt = '<p class="b" data-lang>'+esc(s.b)+'</p>';
      if(s.mentor){{
        txt += '<div class="mentor-bubble"><div class="mentor-av">आ</div><div class="mentor-content">'+
               '<div class="mentor-name">आचार्य (Acharya)</div><div class="mentor-msg" data-lang>'+esc(s.mentor)+'</div></div></div>';
      }}
      vis = s.viz && VIZ[s.viz] ? VIZ[s.viz]() : vizPie(1, 2);
      break;
    case "sim":
      title = '<div class="kindrow"><span class="kind">Interactive Lab</span></div><h2 data-lang>'+esc(s.t)+'</h2>';
      txt = '<p class="b" data-lang>'+esc(s.b)+'</p>'+(s.hint?'<div class="hint" data-lang>'+esc(s.hint)+'</div>':'');
      ctl = '<div class="simctl">'+SIM[s.sim]()+'</div>';
      break;
    case "steps":
      title = '<div class="kindrow"><span class="kind">Worked Example</span></div><h2 data-lang>'+esc(s.t)+'</h2>';
      txt = '<p class="b" data-lang>'+esc(s.b)+'</p>'+
        '<div class="steps">'+(s.steps||[]).map((x,n)=>'<div class="step"><span class="n">'+(n+1)+
        '</span><span data-lang>'+esc(x)+'</span></div>').join("")+'</div>';
      vis = s.viz && VIZ[s.viz] ? VIZ[s.viz]() : vizStrip(3, 8);
      break;
    case "check":
      title = '<div class="kindrow"><span class="kind">Your Turn</span></div><h2 data-lang>'+esc(s.q)+'</h2>';
      txt = '<div class="opts">'+(s.opts||[]).map((o,n)=>'<div class="opt" data-k="'+n+'">'+
        '<span class="k">'+String.fromCharCode(65+n)+'</span><span data-lang>'+esc(o)+'</span></div>').join("")+
        '</div><div class="fb" id="fb"></div>';
      vis = vizPie(3, 4);
      break;
    case "mistake":
      title = '<div class="kindrow"><span class="kind">Watch Out</span></div><h2 data-lang>'+esc(s.t)+'</h2>';
      txt = '<p class="b" data-lang>'+esc(s.b)+'</p>'+
        (s.items||[]).map(it=>'<div class="mrow"><div style="font-size:24px;line-height:1">⚠️</div><div><b data-lang>'+esc(it[0])+
        '</b><span data-lang>'+esc(it[1])+'</span></div></div>').join("");
      vis = vizStrip(3, 4);
      break;
    case "summary":
      title = '<div class="kindrow"><span class="kind">Master Summary</span></div><h2 data-lang>'+esc(s.t)+'</h2>';
      txt = (s.items||[]).map(it=>'<div class="mrow"><div style="font-size:20px;line-height:1;color:var(--green)">✓</div><div><b data-lang>'+esc(it[0])+
        '</b><span data-lang>'+esc(it[1])+'</span></div></div>').join("");
      vis = vizEquivalent(2);
      break;
    case "end":
      title = '<div class="kindrow"><span class="kind">Mastery Unlocked</span></div><h1 data-lang>'+esc(s.t)+'</h1>';
      txt = '<p class="sub" data-lang>'+esc(s.s||"")+'</p><p class="b" data-lang>'+esc(s.b||"")+'</p>'+
            '<div class="mentor-bubble"><div class="mentor-av">🏆</div><div class="mentor-content">'+
            '<div class="mentor-name">आचार्य (Acharya)</div><div class="mentor-msg">शाबाश! आपने भिन्न के सभी सिद्धांतों को समझ लिया है।</div></div></div>';
      vis = vizPie(4, 4);
      break;
    default:
      title = '<h2 data-lang>'+esc(s.t||"")+'</h2>'; txt = '<p class="b" data-lang>'+esc(s.b||"")+'</p>';
      vis = vizPie(1, 2);
  }}

  card.innerHTML =
    '<div class="head">'+title+'</div>' +
    '<div class="txt">'+txt+'</div>' +
    '<div class="visual" id="vis">'+(hasSim ? simViz(s.sim, initSim(s.sim)) : vis)+'</div>' +
    '<div class="ctl">'+(hasSim ? ctl : '')+'</div>';

  lang(card);
  if(s.kind === "check") wireCheck(s);
  if(hasSim) wireSim(s.sim);
  prog.style.width = Math.round(((i+1)/SLIDES.length)*100)+"%";
  const chip = document.getElementById("chip");
  if(chip) chip.textContent = (i+1) + " / " + SLIDES.length;
  prevB.disabled = i === 0;
  nextB.textContent = (i === SLIDES.length-1) ? "Finish ✓" : "Next ▶";
}}

function wireCheck(s){{
  card.querySelectorAll(".opt").forEach(el=>{{
    el.addEventListener("click", ()=>{{
      const k = +el.dataset.k;
      const fb = document.getElementById("fb");
      card.querySelectorAll(".opt").forEach(o=>o.classList.remove("ok","no"));
      const right = (k === s.ans);
      if(right){{ el.classList.add("ok"); fb.className="fb show ok"; }}
      else {{ el.classList.add("no"); card.querySelectorAll(".opt")[s.ans].classList.add("ok");
             fb.className="fb show no"; }}
      fb.innerHTML = T(s.why||(right?"Correct!":"Not quite."));
      lang(fb);
    }});
  }});
}}

prevB.addEventListener("click", ()=>{{ if(i>0){{ i--; render(); }} }});
nextB.addEventListener("click", ()=>{{ if(i<SLIDES.length-1){{ i++; render(); }} }});
document.addEventListener("keydown", e=>{{
  if(e.key==="ArrowRight") nextB.click();
  if(e.key==="ArrowLeft") prevB.click();
}});
hiAll.addEventListener("click", ()=>{{
  allHi = !allHi;
  hiAll.style.background = allHi ? "rgba(255,194,71,.18)" : "transparent";
  hiAll.style.color = allHi ? "var(--gold)" : "";
  document.querySelectorAll(".hiBtn").forEach(b=>{{
    const on = b.classList.contains("on");
    if(allHi && !on) b.click();
    if(!allHi && on) b.click();
  }});
}});

render();
</script>
"""


def build_chapter7_html() -> str:
    css = get_base_css()
    lle_script = build_lle_script(WORDS, PHRASES)
    svg_and_sims = get_ch7_svg_and_sims()
    render_engine = build_render_engine(
        SLIDES, "Class 6 Mathematics · Chapter 7"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Aasha Learn — Fractions (Class 6 Math Ch 7)</title>
<style>
{css}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="logo">अ</div>
    <div class="brand">AASHA <em>LEARN</em><small>Class 6 Math · Chapter 7: Fractions</small></div>
    <div class="chip" id="chip">1 / {len(SLIDES)}</div>
  </header>
  <div class="bar"><i id="prog"></i></div>
  <div class="card" id="card"></div>
  <div class="tapline">
    <button id="prev" class="gho" aria-label="Previous">◀</button>
    <button id="next" class="pri">Next ▶</button>
    <span class="taphint">Tap any word → <b>हिंदी</b></span>
    <button id="hiAll" class="gho" style="margin-left:auto">हिंदी</button>
  </div>
</div>
<div id="wp" role="dialog" aria-label="Word meaning">
  <div class="r1">
    <span id="wpWord"></span><span id="wpHindi"></span><span id="wpPron"></span>
    <button class="spk" id="wpSpeak">🔊 Hear it</button>
    <button class="spk cls" id="wpClose">Close ✕</button>
  </div>
</div>
{lle_script}
{svg_and_sims}
{render_engine}
</body>
</html>
"""


if __name__ == "__main__":
    out_file = CHAPTERS_DIR / "class6_math_ch07_fractions.html"
    html_content = build_chapter7_html()
    out_file.write_text(html_content, encoding="utf-8")
    print(f"Compiled Chapter 7 Fractions to: {out_file}")
    print(f"Size: {len(html_content):,} bytes ({len(html_content)/1024:.1f} KB)")
