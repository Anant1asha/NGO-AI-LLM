"""AASHA AIOS — Class 8 Science Chapter 4: Combustion and Flame Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "combustion": {"h": "दहन (जलने की रासायनिक क्रिया)", "p": "कम्बशन"},
    "flame": {"h": "ज्वाला (लौ)", "p": "फ़्लेम"},
    "ignition": {"h": "ज्वलन (आग पकड़ने का बिंदु)", "p": "इग्निशन"},
    "temperature": {"h": "तापमान", "p": "टेम्परेचर"},
    "fuel": {"h": "ईंधन", "p": "फ्यूल"},
    "fuels": {"h": "ईंधन", "p": "फ्यूल्स"},
    "oxygen": {"h": "ऑक्सीजन गैस", "p": "ऑक्सीजन"},
    "combustible": {"h": "दहनशील (जलने योग्य)", "p": "कम्बस्टिबल"},
    "inflammable": {"h": "ज्वलनशील (शीघ्र आग पकड़ने वाला)", "p": "इन्फ़्लैमेबल"},
    "extinguisher": {"h": "अग्निशामक (आग बुझाने का यंत्र)", "p": "एक्सटिंग्विशर"},
    "spontaneous": {"h": "स्वतः दहन (अपने आप भड़क उठना)", "p": "स्पॉन्टेनियस"},
    "calorific": {"h": "ऊष्मीय मान (कैलोरी मान)", "p": "कैलोरिफ़िक"},
    "luminous": {"h": "दीप्त (चमकदार पीला क्षेत्र)", "p": "लूमिनस"},
    "goldsmith": {"h": "सुनार", "p": "गोल्डस्मिथ"},
    "blowpipe": {"h": "फूंकनी (धातु की नली)", "p": "ब्लोपाइप"},
    "monoxide": {"h": "कार्बन मोनोऑक्साइड (विषाक्त गैस)", "p": "मोनोऑक्साइड"},
    "greenhouse": {"h": "ग्रीनहाउस प्रभाव", "p": "ग्रीनहाउस"},
    "thermal": {"h": "तापीय (गर्मी संबंधी)", "p": "थर्मल"},
    "substance": {"h": "पदार्थ", "p": "सब्सटेंस"},
    "substances": {"h": "पदार्थ", "p": "सब्सटेंसेज़"},
}

EXTRA_PHRASES = {
    "Combustion and Flame — Thermal Zones & Fire Triangle": "दहन और ज्वाला — तापीय क्षेत्र और अग्नि त्रिकोण",
    "Science · Class 8 · Chapter 4": "विज्ञान · कक्षा 8 · अध्याय 4",
    "Strike a matchstick or light a kitchen gas stove. That dancing flame is not magic — it is a rapid chemical dance of atoms releasing immense heat and light!": "माचिस की तीली जलाएं या रसोई का गैस स्टोव चालू करें। वह नाचती हुई लौ कोई जादू नहीं है — यह अत्यधिक गर्मी और प्रकाश उत्सर्जित करने वाले परमाणुओं का एक तीव्र रासायनिक नृत्य है!",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "Combustion is a chemical reaction between fuel and oxygen releasing heat and light, requiring ignition temperature, and producing distinct flame zones based on oxygen availability.": "दहन ईंधन और ऑक्सीजन के बीच एक रासायनिक प्रतिक्रिया है जो गर्मी और प्रकाश छोड़ती है, जिसके लिए ज्वलन तापमान की आवश्यकता होती है, और यह ऑक्सीजन की उपलब्धता के आधार पर अलग-अलग ज्वाला क्षेत्र बनाती है।",
    "What Is Combustion?": "दहन क्या होता है?",
    "A chemical process in which a substance reacts with oxygen to give off heat is called COMBUSTION. The substance that undergoes combustion is said to be COMBUSTIBLE or a FUEL.": "एक रासायनिक प्रक्रिया जिसमें कोई पदार्थ ऑक्सीजन के साथ प्रतिक्रिया करके ऊष्मा देता है, दहन कहलाती है। जिस पदार्थ का दहन होता है उसे दहनशील या ईंधन कहा जाता है।",
    "Combustible vs Non-Combustible": "दहनशील बनाम अदहनशील पदार्थ",
    "Substances that catch fire easily (wood, paper, kerosene, LPG, coal) are COMBUSTIBLE. Substances that do not burn under normal conditions (stone, iron nail, glass, brick) are NON-COMBUSTIBLE.": "जो पदार्थ आसानी से आग पकड़ लेते हैं (लकड़ी, कागज, मिट्टी का तेल, एलपीजी, कोयला) दहनशील कहलाते हैं। जो पदार्थ सामान्य परिस्थितियों में नहीं जलते (पत्थर, लोहे की कील, कांच, ईंट) अदहनशील कहलाते हैं।",
    "The Essential Fire Triangle": "अनिवार्य अग्नि त्रिकोण (Fire Triangle)",
    "Three conditions are strictly necessary for combustion to occur: 1. Fuel (the combustible material), 2. Air / Oxygen (supporter of combustion), and 3. Heat (to reach ignition temperature).": "दहन होने के लिए तीन शर्तें पूरी तरह आवश्यक हैं: 1. ईंधन (जलने वाला पदार्थ), 2. वायु / ऑक्सीजन (दहन का पोषक), और 3. ऊष्मा (ज्वलन तापमान तक पहुँचने के लिए)।",
    "What is Ignition Temperature?": "ज्वलन तापमान क्या है?",
    "The lowest temperature at which a substance catches fire is called its IGNITION TEMPERATURE. A matchstick does not catch fire on its own at room temperature because it has not reached its ignition temperature!": "वह न्यूनतम तापमान जिस पर कोई पदार्थ आग पकड़ लेता है, उसका ज्वलन तापमान कहलाता है। माचिस की तीली कमरे के तापमान पर अपने आप आग नहीं पकड़ती क्योंकि वह अपने ज्वलन तापमान तक नहीं पहुँची होती!",
    "Inflammable Substances": "अत्यधिक ज्वलनशील पदार्थ",
    "Substances which have very low ignition temperatures and can easily catch fire with a flame are called INFLAMMABLE SUBSTANCES. Examples: Petrol, alcohol, and Liquefied Petroleum Gas (LPG).": "वे पदार्थ जिनका ज्वलन तापमान बहुत कम होता है और जो ज्वाला के साथ आसानी से आग पकड़ लेते हैं, ज्वलनशील पदार्थ कहलाते हैं। उदाहरण: पेट्रोल, अल्कोहल और एलपीजी।",
    "How Do We Control Fire?": "हम आग पर नियंत्रण कैसे पाते हैं?",
    "Fire can be controlled by cutting off any one side of the Fire Triangle: 1. Cooling fuel below its ignition temperature (using water), 2. Cutting off oxygen supply (using carbon dioxide or blanket), or 3. Removing fuel.": "अग्नि त्रिकोण के किसी एक हिस्से को काटकर आग पर नियंत्रण पाया जा सकता है: 1. ईंधन को उसके ज्वलन तापमान से नीचे ठंडा करना (पानी द्वारा), 2. ऑक्सीजन की आपूर्ति काटना (CO2 या कंबल द्वारा), या 3. ईंधन को हटाना।",
    "Try it: Thermal Probe & Candle Flame Lab": "करके देखें: थर्मल प्रोब और मोमबत्ती की ज्वाला लैब",
    "Move the thermal probe across the three concentric zones of the flame. Observe the real-time temperature change and understand why goldsmiths use the outermost tip!": "थर्मल प्रोब को लौ के तीनों संकेंद्री क्षेत्रों में घुमाएं। वास्तविक समय में तापमान परिवर्तन देखें और समझें कि सुनार सबसे बाहरी सिरे का उपयोग क्यों करते हैं!",
    "Three Distinct Zones of a Flame": "ज्वाला के तीन विशिष्ट क्षेत्र",
    "A candle flame has three concentric zones: 1. Outer non-luminous zone (blue, hottest), 2. Middle luminous zone (yellow, moderately hot), and 3. Innermost dark zone (least hot, unburnt wax vapors).": "मोमबत्ती की लौ के तीन संकेंद्री क्षेत्र होते हैं: 1. बाहरी अदीप्त क्षेत्र (नीला, सबसे गर्म), 2. मध्य दीप्त क्षेत्र (पीला, मध्यम गर्म), और 3. सबसे भीतरी काला क्षेत्र (सबसे कम गर्म, बिना जली मोम की वाष्प)।",
    "Why Goldsmiths Use the Outer Blue Zone": "सुनार बाहरी नीले क्षेत्र का उपयोग क्यों करते हैं?",
    "Goldsmiths blow through a metallic blowpipe directing the outermost blue zone onto gold and silver. Why? Because the outer zone has plenty of oxygen, achieving complete combustion at over 1400°C!": "सुनार सोने और चांदी पर सबसे बाहरी नीले क्षेत्र को केंद्रित करने के लिए धातु की फूंकनी से फूंक मारते हैं। क्यों? क्योंकि बाहरी क्षेत्र में प्रचुर मात्रा में ऑक्सीजन होती है, जिससे 1400°C से अधिक पर पूर्ण दहन होता है!",
    "Types of Combustion": "दहन के विभिन्न प्रकार",
    "1. Rapid combustion (LPG gas burner burning instantly). 2. Spontaneous combustion (White phosphorus bursting into flames without external heat). 3. Explosion (Firecracker ignition producing heat, light, and sound).": "1. तीव्र दहन (एलपीजी गैस बर्नर तुरंत जलता है)। 2. स्वतः दहन (सफेद फास्फोरस बिना बाहरी गर्मी के अपने आप जल उठता है)। 3. विस्फोट (पटाखे का प्रज्वलन जो गर्मी, प्रकाश और तेज ध्वनि उत्पन्न करता है)।",
    "What Makes a Good Fuel?": "एक आदर्श ईंधन की क्या विशेषताएं हैं?",
    "A good fuel is readily available, cheap, burns easily in air at a moderate rate, produces large amounts of heat, and leaves behind no undesirable poisonous residues.": "एक अच्छा ईंधन आसानी से उपलब्ध होता है, सस्ता होता है, मध्यम दर पर हवा में सुगमता से जलता है, अत्यधिक ऊष्मा उत्पन्न करता है, और कोई अवांछनीय विषैला अवशेष नहीं छोड़ता।",
    "Calorific Value of Fuels": "ईंधनों का ऊष्मीय (कैलोरी) मान",
    "The amount of heat energy produced on complete combustion of 1 kg of a fuel is called its CALORIFIC VALUE. It is measured in kilojoules per kilogram (kJ/kg). Hydrogen has the highest value at 150,000 kJ/kg!": "1 किलोग्राम ईंधन के पूर्ण दहन से उत्पन्न ऊष्मा ऊर्जा की मात्रा उसका ऊष्मीय मान (कैलोरी मान) कहलाती है। इसे किलोजूल प्रति किलोग्राम (kJ/kg) में मापा जाता है। हाइड्रोजन का मान सर्वाधिक 150,000 kJ/kg है!",
    "Harmful By-products of Burning": "ईंधन जलने के हानिकारक प्रभाव",
    "Incomplete combustion releases deadly poisonous Carbon Monoxide (CO). Excess Carbon Dioxide (CO2) leads to global warming. Oxides of sulfur and nitrogen dissolve in rainwater causing devastating ACID RAIN.": "अपूर्ण दहन से अत्यंत विषैली कार्बन मोनोऑक्साइड (CO) निकलती है। अत्यधिक कार्बन डाइऑक्साइड (CO2) से ग्लोबल वार्मिंग होती है। सल्फर और नाइट्रोजन के ऑक्साइड वर्षा जल में घुलकर विनाशकारी अम्ल वर्षा करते हैं।",
    "Worked example — Calculating Fuel Efficiency": "हल किया गया उदाहरण — ईंधन दक्षता की गणना",
    "In an experiment, 4.5 kg of a fuel was completely burned. The heat produced was measured to be 180,000 kJ. What is the calorific value of the fuel?": "एक प्रयोग में, 4.5 किलोग्राम ईंधन को पूरी तरह जलाया गया। उत्पन्न ऊष्मा 180,000 किलोजूल मापी गई। ईंधन का ऊष्मीय मान ज्ञात कीजिए।",
    "Step 1: Formula: Calorific Value = Total Heat Produced (kJ) / Mass of Fuel (kg).": "स्टेप 1: सूत्र: ऊष्मीय मान = कुल उत्पन्न ऊष्मा (kJ) / ईंधन का द्रव्यमान (kg)।",
    "Step 2: Substitute: 180,000 kJ / 4.5 kg = 40,000 kJ/kg.": "स्टेप 2: मान रखें: 180,000 kJ / 4.5 kg = 40,000 kJ/kg।",
    "Step 3: Comparing with standard values, this fuel is likely Biogas or Diesel/Kerosene!": "स्टेप 3: मानक मानों से तुलना करने पर, यह ईंधन बायोगैस या डीजल/केरोसिन जैसा कुशल ईंधन है!",
    "The fuel releases 40,000 kJ of clean energy for every single kilogram burned!": "यह ईंधन जलाए गए प्रत्येक किलोग्राम के लिए 40,000 kJ ऊर्जा प्रदान करता है!",
    "Which zone of a candle flame is the hottest?": "मोमबत्ती की लौ का कौन सा क्षेत्र सबसे अधिक गर्म होता है?",
    "Outer Blue Zone": "बाहरी नीला क्षेत्र",
    "Middle Yellow Zone": "मध्य पीला क्षेत्र",
    "Innermost Dark Zone": "सबसे भीतरी काला क्षेत्र",
    "The outer blue zone undergoes complete combustion due to unlimited oxygen supply, reaching temperatures above 1400°C.": "असीमित ऑक्सीजन आपूर्ति के कारण बाहरी नीला क्षेत्र पूर्ण दहन करता है, जिससे इसका तापमान 1400°C से ऊपर पहुँच जाता है।",
    "Why is water NOT used to extinguish electrical fires?": "बिजली की आग बुझाने के लिए पानी का उपयोग क्यों नहीं किया जाता?",
    "Water conducts electricity and can electrocute firefighters": "पानी बिजली का सुचालक है और करंट लगा सकता है",
    "Water increases the ignition temperature": "पानी ज्वलन तापमान बढ़ा देता है",
    "Water releases flammable hydrogen gas": "पानी ज्वलनशील हाइड्रोजन गैस छोड़ता है",
    "Ordinary tap water contains dissolved mineral ions, making it a dangerous electrical conductor that can deliver a fatal shock!": "साधारण नल के पानी में खनिज आयन घुले होते हैं, जिससे यह बिजली का खतरनाक सुचालक बन जाता है और जानलेवा करंट लगा सकता है!",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Assuming yellow flame is hottest": "यह सोचना कि पीली लौ सबसे गर्म होती है",
    "Students often think bright yellow means highest heat. In reality, yellow flame indicates incomplete combustion; the faint blue outer edge is much hotter!": "विद्यार्थी अक्सर सोचते हैं कि चमकीला पीला रंग सबसे अधिक गर्मी दर्शाता है। वास्तव में, पीली लौ अपूर्ण दहन दर्शाती है; धुंधला नीला बाहरी किनारा कहीं अधिक गर्म होता है!",
    "Pouring water on petrol fires": "पेट्रोल की आग पर पानी डालना",
    "Petrol and oil are lighter than water. Water sinks to the bottom while burning petrol floats on top, spreading the fire rapidly! Use CO2 or sand instead.": "पेट्रोल और तेल पानी से हल्के होते हैं। पानी नीचे बैठ जाता है जबकि जलता हुआ पेट्रोल ऊपर तैरता रहता है, जिससे आग तेजी से फैलती है! इसके स्थान पर CO2 या रेत का प्रयोग करें।",
    "Sleeping near a burning coal stove": "जलती हुई कोयले की अंगीठी के पास सोना",
    "In a closed room, burning coal produces colorless, odorless Carbon Monoxide (CO). It binds to haemoglobin 200x faster than oxygen, causing silent fatal suffocation.": "बंद कमरे में जलता कोयला रंगहीन, गंधहीन कार्बन मोनोऑक्साइड (CO) बनाता है। यह हीमोग्लोबिन से ऑक्सीजन की तुलना में 200 गुना तेजी से जुड़कर दम घोंट देता है।",
    "Where you meet it in real life": "दैनिक जीवन में दहन और ज्वाला",
    "The Village Goldsmith (सुनार)": "गांव का सुनार (पारंपरिक धातु शिल्पी)",
    "Notice how a goldsmith blows air through a narrow pipe into the blue edge of the oil lamp. He directs the 1400°C non-luminous tip directly onto gold grains to melt them cleanly!": "ध्यान दें कि कैसे एक सुनार दीये के नीले किनारे में एक संकरी नली से हवा फूंकता है। वह सोने के दानों को साफ पिघलाने के लिए 1400°C वाले अदीप्त सिरे को सीधे उन पर केंद्रित करता है!",
    "The Red Fire Extinguisher in Schools": "स्कूलों में लाल रंग का अग्निशामक सिलेंडर",
    "Inside modern dry powder and CO2 extinguishers, pressurized gas blankets the fire, instantaneously depriving it of oxygen without leaving messy conductive liquid.": "आधुनिक ड्राई पाउडर और CO2 अग्निशामकों के अंदर, दबाव वाली गैस आग पर चादर की तरह फैल जाती है, जिससे बिना किसी तरल के तुरंत ऑक्सीजन का संपर्क कट जाता है।",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Combustion": "दहन",
    "Chemical process of burning with oxygen releasing heat.": "ऑक्सीजन के साथ जलने की रासायनिक प्रक्रिया जो ऊष्मा छोड़ती है।",
    "Fire Triangle": "अग्नि त्रिकोण",
    "Requires Fuel, Oxygen, and Ignition Temperature. Remove one to extinguish.": "ईंधन, ऑक्सीजन और ज्वलन तापमान की आवश्यकता। बुझाने के लिए एक को हटाएं।",
    "Flame Architecture": "ज्वाला की संरचना",
    "Outer Blue (Hottest), Middle Yellow (Luminous), Inner Dark (Wax vapors).": "बाहरी नीला (सबसे गर्म), मध्य पीला (दीप्त), भीतरी काला (मोम वाष्प)।",
    "Calorific Value": "ऊष्मीय मान",
    "Heat per kg (kJ/kg). Hydrogen is highest (150,000 kJ/kg).": "प्रति किलोग्राम ऊष्मा (kJ/kg)। हाइड्रोजन सर्वाधिक है (150,000 kJ/kg)।",
    "Safety Rules": "सुरक्षा नियम",
    "Never use water on electrical/petrol fires; avoid CO in closed rooms.": "बिजली/पेट्रोल की आग पर कभी पानी न डालें; बंद कमरे में अंगीठी न जलाएं।",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Thermal mastery unlocked! You understand the atomic chemistry of fire, flame zones, and fire safety.": "तापीय मास्टरी अनलॉक! आप आग के परमाणु रसायन, ज्वाला के क्षेत्रों और अग्नि सुरक्षा को अच्छी तरह समझ चुके हैं।",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Combustion and Flame — Thermal Zones & Fire Triangle",
        "s": "Science · Class 8 · Chapter 4",
        "b": "Strike a matchstick or light a kitchen gas stove. That dancing flame is not magic — it is a rapid chemical dance of atoms releasing immense heat and light!",
        "viz": "flame_intro",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "Combustion is a chemical reaction between fuel and oxygen releasing heat and light, requiring ignition temperature, and producing distinct flame zones based on oxygen availability.",
        "mentor": "Acharya's Golden Rule: Fire needs 3 pillars. Break any one pillar of the triangle, and even the fiercest fire dies instantly!",
        "viz": "triangle_visual",
    },
    {
        "kind": "text",
        "t": "What Is Combustion?",
        "b": "A chemical process in which a substance reacts with oxygen to give off heat is called COMBUSTION. The substance that undergoes combustion is said to be COMBUSTIBLE or a FUEL.",
        "viz": "combustion_visual",
    },
    {
        "kind": "text",
        "t": "Combustible vs Non-Combustible",
        "b": "Substances that catch fire easily (wood, paper, kerosene, LPG, coal) are COMBUSTIBLE. Substances that do not burn under normal conditions (stone, iron nail, glass, brick) are NON-COMBUSTIBLE.",
        "viz": "materials_visual",
    },
    {
        "kind": "text",
        "t": "The Essential Fire Triangle",
        "b": "Three conditions are strictly necessary for combustion to occur: 1. Fuel (the combustible material), 2. Air / Oxygen (supporter of combustion), and 3. Heat (to reach ignition temperature).",
        "viz": "triangle_visual",
    },
    {
        "kind": "text",
        "t": "What is Ignition Temperature?",
        "b": "The lowest temperature at which a substance catches fire is called its IGNITION TEMPERATURE. A matchstick does not catch fire on its own at room temperature because it has not reached its ignition temperature!",
        "viz": "matchstick_visual",
    },
    {
        "kind": "text",
        "t": "Inflammable Substances",
        "b": "Substances which have very low ignition temperatures and can easily catch fire with a flame are called INFLAMMABLE SUBSTANCES. Examples: Petrol, alcohol, and Liquefied Petroleum Gas (LPG).",
        "viz": "lpg_visual",
    },
    {
        "kind": "text",
        "t": "How Do We Control Fire?",
        "b": "Fire can be controlled by cutting off any one side of the Fire Triangle: 1. Cooling fuel below its ignition temperature (using water), 2. Cutting off oxygen supply (using carbon dioxide or blanket), or 3. Removing fuel.",
        "viz": "extinguisher_visual",
    },
    {
        "kind": "sim",
        "t": "Try it: Thermal Probe & Candle Flame Lab",
        "b": "Move the thermal probe across the three concentric zones of the flame. Observe the real-time temperature change and understand why goldsmiths use the outermost tip!",
        "sim": "flame_lab",
    },
    {
        "kind": "text",
        "t": "Three Distinct Zones of a Flame",
        "b": "A candle flame has three concentric zones: 1. Outer non-luminous zone (blue, hottest), 2. Middle luminous zone (yellow, moderately hot), and 3. Innermost dark zone (least hot, unburnt wax vapors).",
        "viz": "candle_zones_visual",
    },
    {
        "kind": "text",
        "t": "Why Goldsmiths Use the Outer Blue Zone",
        "b": "Goldsmiths blow through a metallic blowpipe directing the outermost blue zone onto gold and silver. Why? Because the outer zone has plenty of oxygen, achieving complete combustion at over 1400°C!",
        "viz": "goldsmith_visual",
    },
    {
        "kind": "text",
        "t": "Types of Combustion",
        "b": "1. Rapid combustion (LPG gas burner burning instantly). 2. Spontaneous combustion (White phosphorus bursting into flames without external heat). 3. Explosion (Firecracker ignition producing heat, light, and sound).",
        "viz": "combustion_types_visual",
    },
    {
        "kind": "text",
        "t": "What Makes a Good Fuel?",
        "b": "A good fuel is readily available, cheap, burns easily in air at a moderate rate, produces large amounts of heat, and leaves behind no undesirable poisonous residues.",
        "viz": "good_fuel_visual",
    },
    {
        "kind": "text",
        "t": "Calorific Value of Fuels",
        "b": "The amount of heat energy produced on complete combustion of 1 kg of a fuel is called its CALORIFIC VALUE. It is measured in kilojoules per kilogram (kJ/kg). Hydrogen has the highest value at 150,000 kJ/kg!",
        "viz": "calorific_visual",
    },
    {
        "kind": "text",
        "t": "Harmful By-products of Burning",
        "b": "Incomplete combustion releases deadly poisonous Carbon Monoxide (CO). Excess Carbon Dioxide (CO2) leads to global warming. Oxides of sulfur and nitrogen dissolve in rainwater causing devastating ACID RAIN.",
        "viz": "pollution_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — Calculating Fuel Efficiency",
        "b": "In an experiment, 4.5 kg of a fuel was completely burned. The heat produced was measured to be 180,000 kJ. What is the calorific value of the fuel?",
        "steps": [
            "Step 1: Formula: Calorific Value = Total Heat Produced (kJ) / Mass of Fuel (kg).",
            "Step 2: Substitute: 180,000 kJ / 4.5 kg = 40,000 kJ/kg.",
            "Step 3: Comparing with standard values, this fuel is likely Biogas or Diesel/Kerosene!",
            "The fuel releases 40,000 kJ of clean energy for every single kilogram burned!",
        ],
        "viz": "calorific_visual",
    },
    {
        "kind": "check",
        "q": "Which zone of a candle flame is the hottest?",
        "opts": ["Outer Blue Zone", "Middle Yellow Zone", "Innermost Dark Zone"],
        "ans": 0,
        "why": "The outer blue zone undergoes complete combustion due to unlimited oxygen supply, reaching temperatures above 1400°C.",
    },
    {
        "kind": "check",
        "q": "Why is water NOT used to extinguish electrical fires?",
        "opts": [
            "Water conducts electricity and can electrocute firefighters",
            "Water increases the ignition temperature",
            "Water releases flammable hydrogen gas",
        ],
        "ans": 0,
        "why": "Ordinary tap water contains dissolved mineral ions, making it a dangerous electrical conductor that can deliver a fatal shock!",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Watch out for these common misconceptions about fire physics and flame structure.",
        "items": [
            [
                "Assuming yellow flame is hottest",
                "Students often think bright yellow means highest heat. In reality, yellow flame indicates incomplete combustion; the faint blue outer edge is much hotter!",
            ],
            [
                "Pouring water on petrol fires",
                "Petrol and oil are lighter than water. Water sinks to the bottom while burning petrol floats on top, spreading the fire rapidly! Use CO2 or sand instead.",
            ],
            [
                "Sleeping near a burning coal stove",
                "In a closed room, burning coal produces colorless, odorless Carbon Monoxide (CO). It binds to haemoglobin 200x faster than oxygen, causing silent fatal suffocation.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "From village goldsmiths melting silver to red fire safety cylinders, flame science protects lives.",
        "mentor": "Next time you see a red cylinder in your school, remember: it starves the flame of oxygen in 3 seconds flat!",
        "viz": "goldsmith_visual",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "The Fire Triangle, flame zones, fuel values, and life safety rules on a single master card.",
        "items": [
            [
                "Combustion",
                "Chemical process of burning with oxygen releasing heat.",
            ],
            [
                "Fire Triangle",
                "Requires Fuel, Oxygen, and Ignition Temperature. Remove one to extinguish.",
            ],
            [
                "Flame Architecture",
                "Outer Blue (Hottest), Middle Yellow (Luminous), Inner Dark (Wax vapors).",
            ],
            [
                "Calorific Value",
                "Heat per kg (kJ/kg). Hydrogen is highest (150,000 kJ/kg).",
            ],
            [
                "Safety Rules",
                "Never use water on electrical/petrol fires; avoid CO in closed rooms.",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Thermal mastery unlocked! You understand the atomic chemistry of fire, flame zones, and fire safety.",
        "b": "You can explain why a goldsmith's blowpipe melts gold and how fire extinguishers save lives!",
    },
]

SVG_AND_SIMS_JS = """
<script>
const VB = 'viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet"';
function svgOpen(extra){ return '<svg '+VB+' font-family="system-ui,sans-serif" '+(extra||"")+'>'; }

function vizFlame(zoneIndex, probeY){
  let s = svgOpen();
  // Dark lab background
  s += '<rect x="10" y="10" width="380" height="280" rx="12" fill="#07121e" stroke="#1d354d"/>';

  // Candle base & wax cylinder
  s += '<rect x="175" y="220" width="50" height="70" rx="4" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>';
  s += '<path d="M 175 220 Q 200 226 225 220" fill="none" stroke="#cbd5e1" stroke-width="3"/>';
  // Wick
  s += '<line x1="200" y1="220" x2="200" y2="195" stroke="#1e293b" stroke-width="3.5" stroke-linecap="round"/>';

  // Flame Zones (Outer Blue -> Middle Yellow -> Inner Dark)
  // 1. Outer Zone (Blue / Non-luminous)
  s += '<path d="M 200 60 C 240 120 235 195 200 205 C 165 195 160 120 200 60 Z" fill="#2563eb" fill-opacity=".35" stroke="#3b82f6" stroke-width="2.5"/>';

  // 2. Middle Zone (Yellow / Luminous)
  s += '<path d="M 200 95 C 230 140 225 195 200 202 C 175 195 170 140 200 95 Z" fill="#facc15" fill-opacity=".75" stroke="#eab308" stroke-width="1.5"/>';

  // 3. Inner Dark Zone (Wax vapor)
  s += '<path d="M 200 155 C 215 175 212 198 200 200 C 188 198 185 175 200 155 Z" fill="#0f172a" fill-opacity=".95" stroke="#334155" stroke-width="1.5"/>';

  // Zone labels
  s += '<text x="90" y="80" fill="#60a5fa" font-size="12" font-weight="800">Outer Blue (~1400°C)</text>';
  s += '<line x1="160" y1="80" x2="190" y2="90" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="3 3"/>';

  s += '<text x="75" y="130" fill="#fde047" font-size="12" font-weight="800">Middle Yellow (~1000°C)</text>';
  s += '<line x1="160" y1="130" x2="185" y2="140" stroke="#fde047" stroke-width="1.5" stroke-dasharray="3 3"/>';

  s += '<text x="80" y="175" fill="#94a3b8" font-size="12" font-weight="800">Inner Dark (~800°C)</text>';
  s += '<line x1="160" y1="175" x2="192" y2="175" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3 3"/>';

  // Thermal Probe (Metallic Rod with Thermometer display)
  const py = probeY || 75; // Y position based on slider
  s += '<line x1="285" y1="'+py+'" x2="205" y2="'+py+'" stroke="#ef4444" stroke-width="4" stroke-linecap="round"/>';
  s += '<circle cx="205" cy="'+py+'" r="5" fill="#f87171"/>';

  // Probe handle
  s += '<rect x="285" y="'+(py-8)+'" width="80" height="16" rx="4" fill="#334155" stroke="#64748b"/>';
  s += '<text x="325" y="'+(py+4)+'" fill="#f8fafc" font-size="10" font-weight="800" text-anchor="middle">PROBE</text>';

  return s + '</svg>';
}

function vizTriangle(){
  let s = svgOpen();
  s += '<rect x="15" y="15" width="370" height="270" rx="12" fill="#091421" stroke="#1e3a5a"/>';

  // Equilateral triangle
  s += '<polygon points="200,50 90,230 310,230" fill="none" stroke="#ff5f78" stroke-width="5"/>';
  s += '<circle cx="200" cy="155" r="32" fill="#ff5f78" fill-opacity=".15"/>';
  s += '<text x="200" y="162" font-size="34" text-anchor="middle">🔥</text>';

  // 3 Vertices / Sides
  s += '<rect x="145" y="25" width="110" height="30" rx="6" fill="#1e293b" stroke="#ff5f78" stroke-width="2"/>';
  s += '<text x="200" y="45" fill="#ff5f78" font-size="13" font-weight="900" text-anchor="middle">1. HEAT (Temp)</text>';

  s += '<rect x="25" y="225" width="105" height="30" rx="6" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>';
  s += '<text x="77" y="245" fill="#38bdf8" font-size="13" font-weight="900" text-anchor="middle">2. OXYGEN</text>';

  s += '<rect x="270" y="225" width="105" height="30" rx="6" fill="#1e293b" stroke="#facc15" stroke-width="2"/>';
  s += '<text x="322" y="245" fill="#facc15" font-size="13" font-weight="900" text-anchor="middle">3. FUEL</text>';

  s += '<text x="200" y="280" fill="#31e6c4" font-size="14" font-weight="800" text-anchor="middle">Remove ANY one side -> Fire extinguishes instantly!</text>';
  return s + '</svg>';
}

const VIZ = {
  flame_intro: ()=> vizFlame(0, 75),
  triangle_visual: ()=> vizTriangle(),
  combustion_visual: ()=> vizTriangle(),
  materials_visual: ()=> vizFlame(1, 130),
  matchstick_visual: ()=> vizFlame(0, 75),
  lpg_visual: ()=> vizFlame(0, 75),
  extinguisher_visual: ()=> vizTriangle(),
  candle_zones_visual: ()=> vizFlame(0, 75),
  goldsmith_visual: ()=> vizFlame(0, 75),
  combustion_types_visual: ()=> vizTriangle(),
  good_fuel_visual: ()=> vizFlame(0, 75),
  calorific_visual: ()=> vizTriangle(),
  pollution_visual: ()=> vizTriangle(),
};

const SIM = {
  flame_lab: ()=>'<label style="font-size:13.5px;color:var(--muted)">Adjust Thermal Probe Position (Height in Flame):</label>'+
    '<div class="simctl">'+
      '<input id="sProbe" type="range" min="1" max="3" value="1" step="1"/>'+
      '<div class="readout">'+
        '<span>Position: <b id="oZone">Outer Blue Zone</b></span> | '+
        '<span>Temp: <b id="oTemp" style="color:#60a5fa">1400°C</b></span>'+
      '</div>'+
      '<div style="font-size:12.5px;color:var(--muted);margin-top:6px" id="oDesc">'+
        'Complete combustion · Goldsmith blowpipe tip · Hottest part'+
      '</div>'+
    '</div>'
};

function simViz(name, v){
  let py = 75;
  if(v === "2") py = 135;
  if(v === "3") py = 175;
  return vizFlame(+v-1, py);
}

function initSim(name){
  return "1";
}

function wireSim(name){
  if(name === "flame_lab"){
    const sP = document.getElementById("sProbe");
    const oZ = document.getElementById("oZone");
    const oT = document.getElementById("oTemp");
    const oD = document.getElementById("oDesc");

    sP.addEventListener("input", (e)=>{
      const v = e.target.value;
      if(v === "1"){
        oZ.textContent = "Outer Blue Zone";
        oT.textContent = "1400°C";
        oT.style.color = "#60a5fa";
        oD.textContent = "Complete combustion · Goldsmith blowpipe tip · Hottest part";
      } else if(v === "2"){
        oZ.textContent = "Middle Yellow Zone";
        oT.textContent = "1000°C";
        oT.style.color = "#facc15";
        oD.textContent = "Incomplete combustion · Glowing carbon soot · Moderately hot";
      } else {
        oZ.textContent = "Innermost Dark Zone";
        oT.textContent = "800°C";
        oT.style.color = "#94a3b8";
        oD.textContent = "No combustion · Unburnt wax vapors · Least hot";
      }
      setVis(simViz(name, v));
    });
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class8_science_ch04_combustion_and_flame",
        title="Combustion and Flame (Class 8 Science Ch 4)",
        grade_subject_sub="Class 8 Science · Chapter 4: Combustion and Flame",
        chapter_num_label="Chapter 4",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class8_science_ch04_combustion_and_flame.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 4 Combustion and Flame to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
