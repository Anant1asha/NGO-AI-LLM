"""AASHA AIOS — Class 6 Science Chapter 2: Components of Food Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "components": {"h": "घटक", "p": "कम्पोनेन्ट्स"},
    "nutrients": {"h": "पोषक तत्व", "p": "न्युट्रिएंट्स"},
    "carbohydrates": {"h": "कार्बोहाइड्रेट (ऊर्जा प्रदाता)", "p": "कारबोहाइड्रेट्स"},
    "protein": {"h": "प्रोटीन (शरीर वर्धक)", "p": "प्रोटीन"},
    "proteins": {"h": "प्रोटीन", "p": "प्रोटीन्स"},
    "fats": {"h": "वसा (ऊर्जा भंडार)", "p": "फ़ैट्स"},
    "vitamins": {"h": "विटामिन (सुरक्षात्मक तत्व)", "p": "विटामिन्स"},
    "minerals": {"h": "खनिज लवण", "p": "मिनरल्स"},
    "roughage": {"h": "आहारी रेशे / रुक्षांश", "p": "रफ़ेज"},
    "diet": {"h": "आहार", "p": "डाइट"},
    "balanced": {"h": "संतुलित आहार", "p": "बैलेंस्ड"},
    "iodine": {"h": "आयोडीन घोल", "p": "आयोडिन"},
    "starch": {"h": "स्टार्च / मंड", "p": "स्टार्च"},
    "biuret": {"h": "बाययूरेट परीक्षण", "p": "बाययूरेट"},
    "caustic": {"h": "कास्टिक सोडा", "p": "कॉस्टिक"},
    "copper": {"h": "कॉपर सल्फेट (नीला थोथा)", "p": "कॉपर"},
    "translucent": {"h": "पारभासी (धुंधला दिखने वाला)", "p": "ट्रांसलूसेंट"},
    "deficiency": {"h": "अभावजन्य रोग (कमी से होने वाले)", "p": "डेफिशिएंसी"},
    "scurvy": {"h": "स्कर्वी रोग (मसूड़ों से खून आना)", "p": "स्कर्वी"},
    "beriberi": {"h": "बेरी-बेरी रोग (मांसपेशियों की दुर्बलता)", "p": "बेरी-बेरी"},
    "rickets": {"h": "रिकेट्स (हड्डियों का मुड़ना)", "p": "रिकेट्स"},
    "goitre": {"h": "घेंघा रोग (गले की ग्रंथि की सूजन)", "p": "गॉइटर"},
    "anaemia": {"h": "अरक्तता / एनीमिया (आयरन की कमी)", "p": "एनीमिया"},
}

EXTRA_PHRASES = {
    "Components of Food — Nutrients, Balanced Diet & Chemical Tests": "भोजन के घटक — पोषक तत्व, संतुलित आहार और रासायनिक परीक्षण",
    "Science · Class 6 · Chapter 2": "विज्ञान · कक्षा 6 · अध्याय 2",
    "Look at a traditional Indian thali: dal, roti, ghee, curd, and spinach. Why is it arranged like that? Because it is a complete nutritional laboratory on your plate!": "पारंपरिक भारतीय थाली को देखें: दाल, रोटी, घी, दही और पालक। इसे ऐसे क्यों सजाया गया है? क्योंकि यह आपकी थाली में एक संपूर्ण पोषण प्रयोगशाला है!",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "Food fuels life through five major nutrients — carbohydrates, fats, proteins, vitamins, and minerals — supported by roughage and water.": "भोजन पाँच प्रमुख पोषक तत्वों — कार्बोहाइड्रेट, वसा, प्रोटीन, विटामिन और खनिज — के माध्यम से रुक्षांश और जल के सहारे जीवन को ऊर्जा देता है।",
    "What Are Nutrients?": "पोषक तत्व क्या होते हैं?",
    "The chemical substances present in our food that our body needs to grow, repair tissues, produce energy, and defend against diseases are called NUTRIENTS.": "हमारे भोजन में उपस्थित वे रासायनिक पदार्थ जिनकी हमारे शरीर को वृद्धि करने, ऊतकों की मरम्मत करने, ऊर्जा उत्पन्न करने और रोगों से रक्षा के लिए आवश्यकता होती है, पोषक तत्व कहलाते हैं।",
    "Energy Givers: Carbohydrates and Fats": "ऊर्जा प्रदाता: कार्बोहाइड्रेट और वसा",
    "Carbohydrates (rice, wheat, potatoes, sugar) provide quick energy. Fats (ghee, butter, mustard oil, nuts) store concentrated energy — giving more than twice the energy of carbohydrates!": "कार्बोहाइड्रेट (चावल, गेहूं, आलू, चीनी) त्वरित ऊर्जा प्रदान करते हैं। वसा (घी, मक्खन, सरसों का तेल, मेवे) संचित ऊर्जा प्रदान करते हैं — जो कार्बोहाइड्रेट से दोगुनी से अधिक ऊर्जा देते हैं!",
    "Body Builders: Proteins": "शरीर वर्धक: प्रोटीन",
    "Proteins are the building blocks of human life. They are essential for cell growth, muscle repair, and making new tissues. Rich sources: pulses (dal), milk, eggs, paneer, and fish.": "प्रोटीन मानव जीवन के निर्माण खंड हैं। वे कोशिकाओं की वृद्धि, मांसपेशियों की मरम्मत और नए ऊतकों के निर्माण के लिए आवश्यक हैं। समृद्ध स्रोत: दालें, दूध, अंडे, पनीर और मछली।",
    "Protectors: Vitamins and Minerals": "सुरक्षात्मक तत्व: विटामिन और खनिज",
    "Though needed in tiny amounts, vitamins and minerals protect our eyes, bones, teeth, and gums from dangerous illnesses. Vitamin A keeps eyes sharp; Vitamin C fights infections.": "यद्यपि इनकी बहुत कम मात्रा में आवश्यकता होती है, फिर भी विटामिन और खनिज हमारी आंखों, हड्डियों, दांतों और मसूड़ों को खतरनाक बीमारियों से बचाते हैं। विटामिन A आंखों को स्वस्थ रखता है; विटामिन C संक्रमण से लड़ता है।",
    "Try it: Virtual Chemical Dropper Lab": "करके देखें: वर्चुअल रासायनिक ड्रॉपर लैब",
    "Select a food item and drop chemical reagents onto the test tube. Watch the authentic color change take place right in front of your eyes!": "एक खाद्य पदार्थ चुनें और टेस्ट ट्यूब पर रासायनिक अभिकर्मक की बूंदें डालें। अपनी आँखों के सामने प्रामाणिक रंग परिवर्तन होते देखें!",
    "The Iodine Test for Starch": "मंड (स्टार्च) के लिए आयोडीन परीक्षण",
    "Take a slice of raw potato. Add 2-3 drops of dilute Iodine solution. If it contains starch, the brown iodine turns into a deep BLUE-BLACK color!": "कच्चे आलू का एक टुकड़ा लें। तनु आयोडीन घोल की 2-3 बूँदें डालें। यदि इसमें स्टार्च है, तो भूरा आयोडीन गहरे नीले-काले रंग में बदल जाता है!",
    "The Biuret Test for Protein": "प्रोटीन के लिए बाययूरेट परीक्षण",
    "Make a paste of boiled dal. Add 2 drops of Copper Sulfate (blue) and 10 drops of Caustic Soda. Shake well. The mixture turns a beautiful VIOLET color if protein is present!": "उबली दाल का पेस्ट बनाएं। 2 बूँद कॉपर सल्फेट (नीला) और 10 बूँद कास्टिक सोडा मिलाएं। अच्छी तरह हिलाएं। प्रोटीन उपस्थित होने पर मिश्रण सुंदर बैंगनी रंग में बदल जाता है!",
    "The Paper Translucency Test for Fat": "वसा के लिए कागज़ की पारभासकता का परीक्षण",
    "Rub a small piece of butter or crushed groundnut on a clean white paper. Let it dry. If a translucent oily patch appears under a light bulb, fats are confirmed!": "सफेद कागज़ पर मक्खन का एक छोटा टुकड़ा या पिसी हुई मूंगफली रगड़ें। इसे सूखने दें। यदि प्रकाश के नीचे एक पारभासी तैलीय धब्बा दिखाई देता है, तो वसा की पुष्टि होती है!",
    "Roughage (Dietary Fibre) and Water": "रुक्षांश (आहारी रेशे) और जल",
    "Roughage does not provide energy, but adds bulk to food, helping our digestive tract push out undigested waste smoothly. Water absorbs nutrients and flushes toxins in urine and sweat.": "रुक्षांश ऊर्जा प्रदान नहीं करता, लेकिन भोजन में मात्रा जोड़ता है, जिससे हमारी पाचन नली अपचित भोजन को आसानी से बाहर निकाल सकती है। जल पोषक तत्वों को अवशोषित करता है और पसीने व मूत्र में विषाक्त पदार्थों को बाहर निकालता है।",
    "What is a Balanced Diet?": "संतुलित आहार क्या होता है?",
    "A diet that contains all essential nutrients in the right proportions, along with adequate roughage and water. You don't need expensive foreign food: sattu, jaggery, sprouted moong, and spinach make a world-class balanced diet!": "वह आहार जिसमें सभी आवश्यक पोषक तत्व उचित अनुपात में हों, साथ ही पर्याप्त रुक्षांश और जल भी हो। आपको महंगे विदेशी भोजन की आवश्यकता नहीं है: सत्तू, गुड़, अंकुरित मूंग और पालक एक विश्वस्तरीय संतुलित आहार बनाते हैं!",
    "Deficiency Diseases: When Nutrients Go Missing": "अभावजन्य रोग: जब पोषक तत्वों की कमी हो जाती है",
    "Diseases caused by the prolonged lack of specific nutrients in food are called DEFICIENCY DISEASES. Lack of Vitamin A causes Night Blindness; Vitamin D deficiency causes brittle Rickets!": "भोजन में विशिष्ट पोषक तत्वों की लंबे समय तक कमी के कारण होने वाले रोग अभावजन्य रोग (Deficiency Diseases) कहलाते हैं। विटामिन A की कमी से रतौंधी होती है; विटामिन D की कमी से रिकेट्स (सूखा रोग) होता है!",
    "Worked example — Diagnosing Deficiency": "हल किया गया उदाहरण — अभावजन्य रोग का निदान",
    "A 10-year-old child in Bihar suffers from bleeding gums and wounds that take very long to heal. What nutrient is lacking?": "बिहार के एक 10 वर्षीय बच्चे के मसूड़ों से खून आता है और उसके घाव भरने में बहुत समय लगता है। किस पोषक तत्व की कमी है?",
    "Step 1: Bleeding gums and delayed wound healing are classic symptoms of Scurvy.": "स्टेप 1: मसूड़ों से खून आना और घावों का देर से भरना स्कर्वी रोग के प्रमुख लक्षण हैं।",
    "Step 2: Scurvy is caused strictly by the deficiency of Vitamin C.": "स्टेप 2: स्कर्वी रोग पूरी तरह विटामिन C की कमी से होता है।",
    "Step 3: Treatment: Consume citrus fruits like Amla (आंवला), lemons, oranges, and raw tomatoes.": "स्टेप 3: उपचार: आंवला, नींबू, संतरे और कच्चे टमाटर जैसे खट्टे फलों का सेवन करें।",
    "Adding fresh Amla restored the child's gums within 2 weeks!": "ताजा आंवला देने से 2 सप्ताह में बच्चे के मसूड़े पूरी तरह स्वस्थ हो गए!",
    "Which chemical turns blue-black in the presence of starch?": "स्टार्च की उपस्थिति में कौन सा रसायन नीला-काला हो जाता है?",
    "Iodine Solution": "आयोडीन घोल",
    "Copper Sulfate": "कॉपर सल्फेट",
    "Caustic Soda": "कास्टिक सोडा",
    "Dilute Iodine solution reacts with starch carbohydrates to form a deep blue-black chemical complex.": "तनु आयोडीन घोल स्टार्च कार्बोहाइड्रेट के साथ प्रतिक्रिया करके गहरा नीला-काला रासायनिक यौगिक बनाता है।",
    "Which disease is caused by lack of Iodine in diet?": "आहार में आयोडीन की कमी से कौन सा रोग होता है?",
    "Goitre (घेंघा)": "घेंघा (गले की सूजन)",
    "Anaemia (अरक्तता)": "एनीमिया (खून की कमी)",
    "Rickets (रिकेट्स)": "रिकेट्स (हड्डियों की बीमारी)",
    "Iodine deficiency causes Goitre, where the thyroid gland in the neck becomes visibly enlarged.": "आयोडीन की कमी से घेंघा (Goitre) रोग होता है, जिसमें गर्दन की थायरॉइड ग्रंथि सूज जाती है।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Washing vegetables after cutting": "सब्जियां काटने के बाद धोना",
    "Never wash peeled and chopped vegetables! Water-soluble Vitamins B and C wash right down the kitchen drain with the water.": "कटी हुई सब्जियों को कभी न धोएं! जल में घुलनशील विटामिन B और C पानी के साथ नाली में बह जाते हैं।",
    "Over-cooking and deep frying": "अत्यधिक पकाना और तलना",
    "Vitamin C is fragile and gets completely destroyed by high cooking heat. Always include fresh raw fruits and salads in your diet!": "विटामिन C नाजुक होता है और अत्यधिक पकाने की गर्मी से पूरी तरह नष्ट हो जाता है। अपने आहार में ताजे कच्चे फल और सलाद अवश्य शामिल करें!",
    "Confusing energy providers": "ऊर्जा प्रदाताओं में भ्रम",
    "Fats give more energy than carbohydrates gram-for-gram, but carbohydrates are the primary source utilized first by the body.": "वसा प्रति ग्राम कार्बोहाइड्रेट से अधिक ऊर्जा देती है, लेकिन कार्बोहाइड्रेट प्राथमिक स्रोत है जिसका शरीर पहले उपयोग करता है।",
    "Where you meet it in real life": "दैनिक जीवन में पोषण कहाँ मिलता है",
    "The Midday Meal Scheme": "मध्याह्न भोजन योजना (PM POSHAN)",
    "Indian government schools serve khichdi with vegetables, boiled eggs, and fortified salt to eliminate childhood malnutrition across 120 million students!": "भारतीय सरकारी स्कूल 12 करोड़ बच्चों में कुपोषण को दूर करने के लिए सब्जियों वाली खिचड़ी, उबले अंडे और फोर्टिफाइड नमक परोसते हैं!",
    "Sprouted Moong and Chana": "अंकुरित मूंग और चना",
    "Sprouting pulses overnight multiplies their Vitamin C and protein bio-availability by over 300% at zero cost!": "दालों को रात भर अंकुरित करने से बिना किसी खर्च के उनमें विटामिन C और प्रोटीन की मात्रा 300% से अधिक बढ़ जाती है!",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Carbohydrates": "कार्बोहाइड्रेट",
    "Quick energy (Rice, Wheat, Potato). Blue-black with Iodine.": "त्वरित ऊर्जा (चावल, गेहूं, आलू)। आयोडीन से नीला-काला।",
    "Proteins": "प्रोटीन",
    "Growth & Repair (Dal, Milk, Egg). Violet with Biuret.": "वृद्धि और मरम्मत (दाल, दूध, अंडा)। बाययूरेट से बैंगनी।",
    "Fats": "वसा",
    "Energy storage (Ghee, Butter). Translucent paper patch.": "ऊर्जा भंडारण (घी, मक्खन)। कागज़ पर पारभासी धब्बा।",
    "Vitamins & Minerals": "विटामिन और खनिज",
    "Immunity & Protection (Vit A, B, C, D, Iron, Iodine).": "रोग प्रतिरोधक क्षमता और सुरक्षा (विटामिन A, B, C, D, आयरन, आयोडीन)।",
    "Roughage & Water": "रुक्षांश और जल",
    "Smooth digestion and toxin elimination. Essential bulk.": "सुगम पाचन और विषाक्त पदार्थों का निष्कासन। आवश्यक मात्रा।",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Mastery unlocked! You are certified in food nutrition and biochemical analysis.": "मास्टरी अनलॉक! आप खाद्य पोषण और जैव रासायनिक परीक्षणों में प्रमाणित हो चुके हैं।",
    "You understand how every nutrient in an Indian thali keeps the body energized and disease-free!": "आप समझ गए हैं कि भारतीय थाली का प्रत्येक पोषक तत्व शरीर को ऊर्जावान और रोगमुक्त कैसे रखता है!",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Components of Food — Nutrients, Balanced Diet & Chemical Tests",
        "s": "Science · Class 6 · Chapter 2",
        "b": "Look at a traditional Indian thali: dal, roti, ghee, curd, and spinach. Why is it arranged like that? Because it is a complete nutritional laboratory on your plate!",
        "viz": "thali_visual",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "Food fuels life through five major nutrients — carbohydrates, fats, proteins, vitamins, and minerals — supported by roughage and water.",
        "mentor": "Namaste! I am Acharya. Your body is the most complex machine on Earth, and food is its high-octane rocket fuel!",
        "viz": "thali_visual",
    },
    {
        "kind": "text",
        "t": "What Are Nutrients?",
        "b": "The chemical substances present in our food that our body needs to grow, repair tissues, produce energy, and defend against diseases are called NUTRIENTS.",
        "viz": "nutrients_circle",
    },
    {
        "kind": "text",
        "t": "Energy Givers: Carbohydrates and Fats",
        "b": "Carbohydrates (rice, wheat, potatoes, sugar) provide quick energy. Fats (ghee, butter, mustard oil, nuts) store concentrated energy — giving more than twice the energy of carbohydrates!",
        "viz": "energy_visual",
    },
    {
        "kind": "text",
        "t": "Body Builders: Proteins",
        "b": "Proteins are the building blocks of human life. They are essential for cell growth, muscle repair, and making new tissues. Rich sources: pulses (dal), milk, eggs, paneer, and fish.",
        "mentor": "Notice how Indian wrestlers eat soaked almonds and drink buffalo milk? That's natural protein building strong muscle fibers!",
        "viz": "protein_visual",
    },
    {
        "kind": "text",
        "t": "Protectors: Vitamins and Minerals",
        "b": "Though needed in tiny amounts, vitamins and minerals protect our eyes, bones, teeth, and gums from dangerous illnesses. Vitamin A keeps eyes sharp; Vitamin C fights infections.",
        "viz": "vitamins_visual",
    },
    {
        "kind": "sim",
        "sim": "reagent_lab",
        "t": "Try it: Virtual Chemical Dropper Lab",
        "b": "Select a food item and drop chemical reagents onto the test tube. Watch the authentic color change take place right in front of your eyes!",
        "hint": "Iodine turns starch blue-black; Copper Sulfate + Caustic Soda turns protein violet!",
    },
    {
        "kind": "text",
        "t": "The Iodine Test for Starch",
        "b": "Take a slice of raw potato. Add 2-3 drops of dilute Iodine solution. If it contains starch, the brown iodine turns into a deep BLUE-BLACK color!",
        "viz": "starch_test_visual",
    },
    {
        "kind": "text",
        "t": "The Biuret Test for Protein",
        "b": "Make a paste of boiled dal. Add 2 drops of Copper Sulfate (blue) and 10 drops of Caustic Soda. Shake well. The mixture turns a beautiful VIOLET color if protein is present!",
        "viz": "protein_test_visual",
    },
    {
        "kind": "text",
        "t": "The Paper Translucency Test for Fat",
        "b": "Rub a small piece of butter or crushed groundnut on a clean white paper. Let it dry. If a translucent oily patch appears under a light bulb, fats are confirmed!",
        "viz": "fat_test_visual",
    },
    {
        "kind": "text",
        "t": "Roughage (Dietary Fibre) and Water",
        "b": "Roughage does not provide energy, but adds bulk to food, helping our digestive tract push out undigested waste smoothly. Water absorbs nutrients and flushes toxins in urine and sweat.",
        "viz": "roughage_visual",
    },
    {
        "kind": "text",
        "t": "What is a Balanced Diet?",
        "b": "A diet that contains all essential nutrients in the right proportions, along with adequate roughage and water. You don't need expensive foreign food: sattu, jaggery, sprouted moong, and spinach make a world-class balanced diet!",
        "mentor": "A balanced diet doesn't cost gold: traditional sattu and roasted chana provide more bio-available nutrition than costly imported cereals!",
        "viz": "thali_visual",
    },
    {
        "kind": "text",
        "t": "Deficiency Diseases: When Nutrients Go Missing",
        "b": "Diseases caused by the prolonged lack of specific nutrients in food are called DEFICIENCY DISEASES. Lack of Vitamin A causes Night Blindness; Vitamin D deficiency causes brittle Rickets!",
        "viz": "deficiency_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — Diagnosing Deficiency",
        "b": "A 10-year-old child in Bihar suffers from bleeding gums and wounds that take very long to heal. What nutrient is lacking?",
        "steps": [
            "Step 1: Bleeding gums and delayed wound healing are classic symptoms of Scurvy.",
            "Step 2: Scurvy is caused strictly by the deficiency of Vitamin C.",
            "Step 3: Treatment: Consume citrus fruits like Amla (आंवला), lemons, oranges, and raw tomatoes.",
            "Adding fresh Amla restored the child's gums within 2 weeks!",
        ],
        "viz": "vitamins_visual",
    },
    {
        "kind": "check",
        "q": "Which chemical turns blue-black in the presence of starch?",
        "opts": ["Iodine Solution", "Copper Sulfate", "Caustic Soda"],
        "ans": 0,
        "why": "Dilute Iodine solution reacts with starch carbohydrates to form a deep blue-black chemical complex.",
    },
    {
        "kind": "check",
        "q": "Which disease is caused by lack of Iodine in diet?",
        "opts": ["Goitre (घेंघा)", "Anaemia (अरक्तता)", "Rickets (रिकेट्स)"],
        "ans": 0,
        "why": "Iodine deficiency causes Goitre, where the thyroid gland in the neck becomes visibly enlarged.",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Watch out for these common misconceptions about food preparation and nutrients.",
        "items": [
            [
                "Washing vegetables after cutting",
                "Never wash peeled and chopped vegetables! Water-soluble Vitamins B and C wash right down the kitchen drain with the water.",
            ],
            [
                "Over-cooking and deep frying",
                "Vitamin C is fragile and gets completely destroyed by high cooking heat. Always include fresh raw fruits and salads in your diet!",
            ],
            [
                "Confusing energy providers",
                "Fats give more energy than carbohydrates gram-for-gram, but carbohydrates are the primary source utilized first by the body.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "From government school midday meals to village sprouted grams, nutrition is actively engineered.",
        "mentor": "Whenever you eat sprouted moong, you are enjoying 300% extra Vitamin C generated purely by mother nature!",
        "viz": "thali_visual",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "The 5 major nutrients, diagnostic tests, and disease matrix on a single reference card.",
        "items": [
            [
                "Carbohydrates",
                "Quick energy (Rice, Wheat, Potato). Blue-black with Iodine.",
            ],
            [
                "Proteins",
                "Growth & Repair (Dal, Milk, Egg). Violet with Biuret.",
            ],
            [
                "Fats",
                "Energy storage (Ghee, Butter). Translucent paper patch.",
            ],
            [
                "Vitamins & Minerals",
                "Immunity & Protection (Vit A, B, C, D, Iron, Iodine).",
            ],
            [
                "Roughage & Water",
                "Smooth digestion and toxin elimination. Essential bulk.",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Mastery unlocked! You are certified in food nutrition and biochemical analysis.",
        "b": "You understand how every nutrient in an Indian thali keeps the body energized and disease-free!",
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
  s += '<text x="200" y="165" font-size="60" text-anchor="middle">🥗</text>';
  return s + '</svg>';
}

function vizThali(){
  let s = svgOpen();
  const cx = 200, cy = 150, r = 110;
  // Steel Thali
  s += '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="#122538" stroke="#8ba2b6" stroke-width="6"/>';
  s += '<circle cx="'+cx+'" cy="'+cy+'" r="'+(r-10)+'" fill="#0b1724" stroke="#1d4055" stroke-width="2"/>';

  // Bowls (Katoris)
  // 1. Dal (Protein - Orange)
  s += '<circle cx="150" cy="95" r="32" fill="#ff9d5b" fill-opacity=".25" stroke="#ff9d5b" stroke-width="2"/>';
  s += '<text x="150" y="99" fill="#ff9d5b" font-size="12" font-weight="900" text-anchor="middle">Dal (Protein)</text>';

  // 2. Rice / Roti (Carbs - Gold)
  s += '<circle cx="200" cy="170" r="42" fill="#ffc247" fill-opacity=".2" stroke="#ffc247" stroke-width="2"/>';
  s += '<text x="200" y="174" fill="#ffc247" font-size="13" font-weight="900" text-anchor="middle">Roti (Carbs)</text>';

  // 3. Spinach Sabzi (Vitamins - Emerald)
  s += '<circle cx="250" cy="95" r="32" fill="#4ade80" fill-opacity=".25" stroke="#4ade80" stroke-width="2"/>';
  s += '<text x="250" y="99" fill="#4ade80" font-size="12" font-weight="900" text-anchor="middle">Greens (Vit)</text>';

  // 4. Ghee drop (Fat - Rose)
  s += '<circle cx="140" cy="170" r="16" fill="#ff5f78" fill-opacity=".3" stroke="#ff5f78" stroke-width="1.5"/>';
  s += '<text x="140" y="174" fill="#ff5f78" font-size="9" font-weight="800" text-anchor="middle">Ghee</text>';

  s += '<text x="200" y="285" fill="#31e6c4" font-size="15" font-weight="800" text-anchor="middle">The Balanced Indian Thali Architecture</text>';
  return s + '</svg>';
}

function vizLab(testType){
  let s = svgOpen();
  const tx = 200, ty = 140;

  // Test tube rack stand
  s += '<rect x="100" y="240" width="200" height="14" rx="4" fill="#5c7386"/>';

  // Test Tube
  s += '<path d="M 175 70 L 175 220 A 25 25 0 0 0 225 220 L 225 70 Z" fill="#0d2133" stroke="#8ba2b6" stroke-width="3"/>';

  let liquidCol = '#38d6c0', label = 'Raw Sample', dropCol = '#ffc247';
  if(testType === "starch"){
    liquidCol = '#1a1f55'; // Blue-black
    dropCol = '#d97706'; // Brown iodine
    label = 'Starch + Iodine -> Deep Blue-Black!';
  } else if(testType === "protein"){
    liquidCol = '#8b5cf6'; // Violet
    dropCol = '#3b82f6'; // Copper sulfate blue
    label = 'Protein + Biuret -> Rich Violet!';
  } else if(testType === "fat"){
    liquidCol = '#ffd98a';
    dropCol = '#ffc247';
    label = 'Fat -> Translucent Greasy Patch!';
  }

  // Liquid in test tube
  s += '<path d="M 177 150 L 177 220 A 23 23 0 0 0 223 220 L 223 150 Z" fill="'+liquidCol+'" fill-opacity=".85"/>';

  // Dropper
  s += '<rect x="195" y="15" width="10" height="35" rx="3" fill="#8ba2b6"/>';
  s += '<circle cx="200" cy="12" r="10" fill="#ff5f78"/>';
  // Falling drop
  s += '<circle cx="200" cy="62" r="5" fill="'+dropCol+'"/>';

  s += '<rect x="40" y="265" width="320" height="28" rx="6" fill="#122436" stroke="rgba(255,255,255,.1)"/>';
  s += '<text x="200" y="284" fill="#ffc247" font-size="14" font-weight="800" text-anchor="middle">'+label+'</text>';
  return s + '</svg>';
}

const VIZ = {
  thali_visual: ()=> vizThali(),
  nutrients_circle: ()=> vizThali(),
  energy_visual: ()=> vizThali(),
  protein_visual: ()=> vizLab("protein"),
  vitamins_visual: ()=> vizThali(),
  starch_test_visual: ()=> vizLab("starch"),
  protein_test_visual: ()=> vizLab("protein"),
  fat_test_visual: ()=> vizLab("fat"),
  roughage_visual: ()=> vizThali(),
  deficiency_visual: ()=> vizThali(),
};

const SIM = {
  reagent_lab: ()=>'<label style="font-size:13.5px;color:var(--muted)">Select Biochemical Test:</label>'+
    '<div class="switch">'+
      '<button id="btnStarch" class="on">1. Starch Test</button>'+
      '<button id="btnProtein">2. Protein Test</button>'+
      '<button id="btnFat">3. Fat Test</button>'+
    '</div>'+
    '<div class="readout"><span id="oReaction">Reagent: <b>Dilute Iodine Solution (Brown)</b></span></div>'
};

function simViz(name, v){
  if(name === "reagent_lab") return vizLab(v);
  return vizThali();
}

function initSim(name){
  return "starch";
}

function wireSim(name){
  if(name === "reagent_lab"){
    const bS = document.getElementById("btnStarch");
    const bP = document.getElementById("btnProtein");
    const bF = document.getElementById("btnFat");
    const oR = document.getElementById("oReaction");

    const clear = ()=>{ bS.classList.remove("on"); bP.classList.remove("on"); bF.classList.remove("on"); };

    bS.addEventListener("click", ()=>{
      clear(); bS.classList.add("on");
      oR.innerHTML = "Reagent: <b>Dilute Iodine</b> -> Result: <b style='color:#63a9ff'>Deep Blue-Black</b>";
      setVis(vizLab("starch"));
    });
    bP.addEventListener("click", ()=>{
      clear(); bP.classList.add("on");
      oR.innerHTML = "Reagents: <b>Copper Sulfate + Caustic Soda</b> -> Result: <b style='color:#9d7bff'>Rich Violet</b>";
      setVis(vizLab("protein"));
    });
    bF.addEventListener("click", ()=>{
      clear(); bF.classList.add("on");
      oR.innerHTML = "Medium: <b>White Paper</b> -> Result: <b style='color:#ffc247'>Translucent Grease Patch</b>";
      setVis(vizLab("fat"));
    });
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class6_science_ch02_components_of_food",
        title="Components of Food (Class 6 Science Ch 2)",
        grade_subject_sub="Class 6 Science · Chapter 2: Components of Food",
        chapter_num_label="Chapter 2",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class6_science_ch02_components_of_food.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 2 Components of Food to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
