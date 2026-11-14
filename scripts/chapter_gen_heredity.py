"""AASHA AIOS — Class 10 Science Chapter 9: Heredity and Evolution Master Luxury Module."""

from pathlib import Path
from build_all_gold_chapters import build_single_chapter_html, CHAPTERS_DIR

EXTRA_WORDS = {
    "heredity": {"h": "आनुवंशिकता (लक्षणों का संचरण)", "p": "हेरेडिटी"},
    "evolution": {"h": "जैव विकास (क्रमिक विकास)", "p": "इवोल्यूशन"},
    "genetics": {"h": "आनुवंशिकी (जीन विज्ञान)", "p": "जेनेटिक्स"},
    "mendel": {"h": "ग्रेगर जॉन मेंडल (आनुवंशिकी के जनक)", "p": "मेंडल"},
    "alleles": {"h": "युग्मविकल्पी (जीन के रूप)", "p": "एलील्स"},
    "allele": {"h": "युग्मविकल्पी", "p": "एलील"},
    "dominant": {"h": "प्रभावी लक्षण (जो दिखाई दे)", "p": "डोमिनेंट"},
    "recessive": {"h": "अप्रभावी लक्षण (जो दबा रहे)", "p": "रिसेसिव"},
    "phenotype": {"h": "लक्षणाप्ररूप (शारीरिक रूप-रंग)", "p": "फीनोटाइप"},
    "genotype": {"h": "जीनीप्ररूप (आनुवंशिक संरचना)", "p": "जीनोटाइप"},
    "punnett": {"h": "पुनेट वर्ग (जीन संभावना ग्रिड)", "p": "पुनेट"},
    "chromosomes": {"h": "गुणसूत्र (डीएनए वाहक)", "p": "क्रोमोसोम्स"},
    "chromosome": {"h": "गुणसूत्र", "p": "क्रोमोसोम"},
    "monohybrid": {"h": "एकसंकर संकरण (एक लक्षण का क्रॉस)", "p": "मोनोहाइब्रिड"},
    "dihybrid": {"h": "द्विसंकर संकरण", "p": "डाइहाइब्रिड"},
    "homozygous": {"h": "समयुग्मजी (समान जीन जैसे TT)", "p": "होमोज़ाइगस"},
    "heterozygous": {"h": "विषमयुग्मजी (अलग जीन जैसे Tt)", "p": "हेटरोज़ाइगस"},
    "fertilization": {"h": "निषेचन क्रिया", "p": "फ़र्टिलाइज़ेशन"},
    "autosomes": {"h": "कायिक गुणसूत्र (22 जोड़े)", "p": "ऑटोसोम्स"},
    "somatic": {"h": "कायिक कोशिकाएं (शारीरिक अंग)", "p": "सोमैटिक"},
}

EXTRA_PHRASES = {
    "Heredity and Evolution — Mendelian Genetics & Punnett Squares": "आनुवंशिकता एवं जैव विकास — मेंडेलियन आनुवंशिकी और पुनेट वर्ग",
    "Science · Class 10 · Chapter 9": "विज्ञान · कक्षा 10 · अध्याय 9",
    "Why do children look like their parents yet remain uniquely distinct? Gregor Mendel unraveled this mystery in a monastery garden using simple sweet pea plants!": "बच्चे अपने माता-पिता जैसे क्यों दिखते हैं फिर भी पूरी तरह अद्वितीय होते हैं? ग्रेगर मेंडल ने एक मठ के बगीचे में साधारण मटर के पौधों का उपयोग करके इस रहस्य को सुलझाया!",
    "The whole chapter in one line": "पूरा अध्याय केवल एक पंक्ति में",
    "Heredity transfers biological traits across generations via genes located on chromosomes, obeying Mendel's laws of dominance, segregation, and independent assortment.": "आनुवंशिकता गुणसूत्रों पर स्थित जीनों के माध्यम से मेंडल के प्रभाविता, पृथक्करण और स्वतंत्र अपव्यूहन के नियमों का पालन करते हुए पीढ़ियों में जैविक लक्षणों को स्थानांतरित करती है।",
    "What Is Heredity?": "आनुवंशिकता क्या है?",
    "The transmission of characters, traits, and physical features from parents to their biological offspring through genes is known as HEREDITY.": "माता-पिता से उनकी संतानों में जीनों के माध्यम से लक्षणों और शारीरिक विशेषताओं के संचरण को आनुवंशिकता कहा जाता है।",
    "Variations: Why Clones Do Not Rule": "विभिन्नताएं: संतानें माता-पिता की हूबहू नकल क्यों नहीं होतीं?",
    "The subtle differences in traits between individuals of the same species are called VARIATIONS. In sexual reproduction, mixing maternal and paternal DNA generates diverse variations essential for evolution!": "एक ही प्रजाति के व्यक्तियों के बीच लक्षणों के सूक्ष्म अंतर विभिन्नताएं कहलाते हैं। लैंगिक जनन में मातृ और पितृ डीएनए का मिश्रण विकास के लिए आवश्यक विविध विभिन्नताएं उत्पन्न करता है!",
    "Mendel and His Garden Pea Plant": "मेंडल और उनका मटर का पौधा",
    "Gregor Johann Mendel chose the Garden Pea (Pisum sativum) because it had distinct contrasting traits, self-pollinated easily, had a short life cycle, and produced hundreds of seeds per generation.": "ग्रेगर जॉन मेंडल ने बगीचे के मटर (पाइसम सैटाइवम) को चुना क्योंकि इसमें स्पष्ट विपर्यासी लक्षण थे, यह आसानी से स्व-परागित होता था, इसका जीवन चक्र छोटा था, और यह प्रति पीढ़ी सैकड़ों बीज पैदा करता था।",
    "Dominant vs Recessive Alleles": "प्रभावी बनाम अप्रभावी लक्षण",
    "A DOMINANT allele (T) expresses its trait even when only one copy is present (TT or Tt). A RECESSIVE allele (t) is masked and only appears when both copies are identical (tt).": "प्रभावी युग्मविकल्पी (T) केवल एक प्रति उपस्थित होने पर भी अपना लक्षण व्यक्त करता है (TT या Tt)। अप्रभावी युग्मविकल्पी (t) छिपा रहता है और केवल तभी प्रकट होता है जब दोनों प्रतियां समान हों (tt)।",
    "Phenotype vs Genotype": "लक्षणाप्ररूप बनाम जीनीप्ररूप",
    "PHENOTYPE is the observable physical appearance (e.g., Tall or Dwarf plant). GENOTYPE is the underlying genetic makeup of alleles inside the cell (e.g., TT, Tt, or tt).": "लक्षणाप्ररूप (Phenotype) दृश्य शारीरिक बनावट है (जैसे, लंबा या बौना पौधा)। जीनीप्ररूप (Genotype) कोशिका के अंदर युग्मविकल्पियों की वास्तविक आनुवंशिक संरचना है (जैसे, TT, Tt, या tt)।",
    "The Monohybrid Cross (TT x tt)": "एकसंकर संकरण (Monohybrid Cross)",
    "When pure Tall (TT) is crossed with pure Dwarf (tt), all F1 offspring are TALL (Tt)! When F1 plants self-pollinate, the hidden dwarf trait miraculously reappears in F2 in a 3:1 ratio!": "जब शुद्ध लंबे (TT) का शुद्ध बौने (tt) के साथ संकरण कराया जाता है, तो सभी F1 संतानें लंबी (Tt) होती हैं! जब F1 पौधों में स्व-परागण होता है, तो F2 में छिपा हुआ बौना लक्षण 3:1 के अनुपात में फिर से प्रकट होता है!",
    "Try it: Mendelian Punnett Square Simulator": "करके देखें: मेंडेलियन पुनेट वर्ग सिम्युलेटर",
    "Cross parent pea alleles in real-time. Watch the 4-cell Punnett grid calculate the exact 3:1 phenotypic and 1:2:1 genotypic ratios right before your eyes!": "वास्तविक समय में जनक मटर के युग्मविकल्पियों का संकरण कराएं। 4-कक्षीय पुनेट ग्रिड को अपनी आँखों के सामने सटीक 3:1 लक्षणाप्ररूप और 1:2:1 जीनीप्ररूप अनुपातों की गणना करते देखें!",
    "How Do Genes Control Physical Traits?": "जीन शारीरिक लक्षणों को कैसे नियंत्रित करते हैं?",
    "A cellular gene is a section of DNA providing instructions for making a specific protein enzyme. Efficient enzymes synthesize plant growth hormone making it tall; defective enzymes yield a dwarf plant!": "कोशिका का जीन डीएनए का एक खंड होता है जो एक विशिष्ट प्रोटीन एंजाइम बनाने के निर्देश देता है। कुशल एंजाइम पौधे के वृद्धि हार्मोन का निर्माण करके उसे लंबा बनाते हैं; दोषपूर्ण एंजाइम से बौना पौधा बनता है!",
    "Sex Determination in Human Beings": "मनुष्यों में लिंग निर्धारण",
    "Humans have 23 pairs of chromosomes. Pair 23 are Sex Chromosomes: females have XX, males have XY. All eggs carry X; sperm carry either X or Y. The father's sperm strictly determines the child's sex!": "मनुष्यों में 23 जोड़े गुणसूत्र होते हैं। 23वां जोड़ा लिंग गुणसूत्र है: महिलाओं में XX, पुरुषों में XY। सभी अंडों में X होता है; शुक्राणु में X या Y होता है। पिता का शुक्राणु ही बच्चे का लिंग निर्धारित करता है!",
    "Dihybrid Cross: Independent Assortment": "द्विसंकर संकरण: स्वतंत्र अपव्यूहन",
    "Crossing Round Yellow seeds (RRYY) with Wrinkled Green (rryy) produces Round Yellow in F1. In F2, traits segregate independently yielding a classic 9:3:3:1 phenotypic ratio!": "गोल पीले बीजों (RRYY) का झुर्रीदार हरे (rryy) के साथ संकरण F1 में गोल पीले बीज देता है। F2 में, लक्षण स्वतंत्र रूप से अलग होकर क्लासिक 9:3:3:1 का अनुपात बनाते हैं!",
    "Acquired vs Inherited Traits": "उपार्जित बनाम आनुवंशिक लक्षण",
    "Traits developed during a lifetime (gym muscles, language, scars) are ACQUIRED and not passed to offspring. Only changes in the DNA of germ cells (sperm/egg) are INHERITED!": "जीवनकाल के दौरान विकसित लक्षण (जिम की मांसपेशियां, भाषा, चोट के निशान) उपार्जित होते हैं और संतानों में नहीं जाते। केवल जनन कोशिकाओं (शुक्राणु/अंडाणु) के डीएनए में होने वाले परिवर्तन ही आनुवंशिक होते हैं!",
    "Evolution and Natural Selection": "जैव विकास और प्राकृतिक वरण",
    "In nature, individuals carrying variations that give survival advantage (e.g. green beetles camouflaged on green leaves against crows) survive longer and reproduce, driving EVOLUTION.": "प्रकृति में, जिन व्यक्तियों में जीवित रहने के लिए लाभकारी विभिन्नताएं होती हैं (जैसे कौवों से बचने के लिए हरी पत्तियों पर हरे भृंग) वे अधिक समय तक जीवित रहते हैं और प्रजनन करते हैं, जिससे विकास होता है।",
    "Worked example — Predicting Genetic Offspring": "हल किया गया उदाहरण — आनुवंशिक संतान की भविष्यवाणी",
    "A homozygous tall pea plant (TT) is crossed with a heterozygous tall plant (Tt). What percentage of offspring will be dwarf?": "एक समयुग्मजी लंबे मटर के पौधे (TT) का विषमयुग्मजी लंबे पौधे (Tt) के साथ संकरण कराया जाता है। कितने प्रतिशत पौधे बौने होंगे?",
    "Step 1: Parent gametes: Parent 1 produces all T gametes. Parent 2 produces 50% T and 50% t gametes.": "स्टेप 1: जनक युग्मक: जनक 1 केवल T युग्मक बनाता है। जनक 2 50% T और 50% t युग्मक बनाता है।",
    "Step 2: Punnett Cross: T x T -> TT (50%) and T x t -> Tt (50%).": "स्टेप 2: पुनेट क्रॉस: T x T -> TT (50%) और T x t -> Tt (50%)।",
    "Step 3: All offspring carry at least one dominant T allele. Therefore, 100% are Tall and 0% are Dwarf!": "स्टेप 3: सभी संतानों में कम से कम एक प्रभावी T एलील होता है। इसलिए, 100% पौधे लंबे और 0% बौने होंगे!",
    "Zero offspring will be dwarf because the dominant T allele masks the recessive t in all cases!": "शून्य प्रतिशत पौधे बौने होंगे क्योंकि प्रभावी T एलील हर स्थिति में अप्रभावी t को दबा देता है!",
    "What is the phenotypic ratio of a Mendelian monohybrid F2 generation?": "मेंडेलियन एकसंकर F2 पीढ़ी का लक्षणाप्ररूप अनुपात क्या होता है?",
    "3 : 1 (Tall : Dwarf)": "3 : 1 (लंबा : बौना)",
    "1 : 2 : 1 (TT : Tt : tt)": "1 : 2 : 1 (जीनीप्ररूप)",
    "9 : 3 : 3 : 1 (Dihybrid)": "9 : 3 : 3 : 1 (द्विसंकर)",
    "In the F2 generation of a monohybrid cross, 75% show the dominant tall phenotype and 25% show the dwarf phenotype, giving a 3:1 ratio.": "एकसंकर संकरण की F2 पीढ़ी में 75% पौधे लंबा लक्षणाप्ररूप और 25% बौना लक्षणाप्ररूप प्रदर्शित करते हैं, जिससे 3:1 का अनुपात मिलता है।",
    "Who genetically determines the sex of a human newborn baby?": "मानव नवजात शिशु का लिंग आनुवंशिक रूप से कौन निर्धारित करता है?",
    "The Father (via X or Y sperm)": "पिता (X या Y शुक्राणु द्वारा)",
    "The Mother (via egg cytoplasm)": "माता (अंडाणु द्वारा)",
    "Environmental temperature": "पर्यावरणीय तापमान",
    "A mother always contributes an X chromosome. The sex depends entirely on whether the father's fertilizing sperm carries an X (yielding XX female) or Y (yielding XY male).": "माता हमेशा X गुणसूत्र देती है। लिंग पूरी तरह इस बात पर निर्भर करता है कि पिता का निषेचन करने वाला शुक्राणु X (XX लड़की) या Y (XY लड़का) ले जाता है।",
    "Three mistakes that cost marks": "तीन गलतियाँ जो परीक्षा में नंबर कटवाती हैं",
    "Blaming mothers for girl children": "कन्या संतान के लिए माताओं को दोष देना",
    "A tragic social misconception! Mothers have only XX chromosomes and can only donate X. Biologically, the father's Y sperm alone determines if a baby is male.": "एक दुखद सामाजिक कुप्रथा! माताओं में केवल XX गुणसूत्र होते हैं और वे केवल X दे सकती हैं। जैविक रूप से, पिता का Y शुक्राणु ही तय करता है कि बच्चा लड़का होगा।",
    "Confusing Phenotypic vs Genotypic ratios": "लक्षणाप्ररूप और जीनीप्ररूप अनुपात में भ्रम",
    "3:1 is the PHENOTYPIC ratio (what you see outside: 3 Tall, 1 Dwarf). 1:2:1 is the GENOTYPIC ratio (hidden alleles: 1 TT, 2 Tt, 1 tt). Never mix them up!": "3:1 लक्षणाप्ररूप अनुपात है (जो बाहर दिखता है: 3 लंबे, 1 बौना)। 1:2:1 जीनीप्ररूप अनुपात है (आंतरिक जीन: 1 TT, 2 Tt, 1 tt)। इन्हें कभी आपस में न मिलाएं!",
    "Believing acquired traits can be inherited": "यह सोचना कि उपार्जित लक्षण अगली पीढ़ी में जाते हैं",
    "Cutting mice tails for 20 generations still produces mice with full-length tails! Bodily changes in somatic cells never change the reproductive germ-line DNA.": "20 पीढ़ियों तक चूहों की पूंछ काटने पर भी पूरी पूंछ वाले चूहे ही पैदा होते हैं! कायिक कोशिकाओं के शारीरिक परिवर्तन कभी जनन डीएनए को नहीं बदलते।",
    "Where you meet it in real life": "दैनिक जीवन में आनुवंशिकी",
    "Attached vs Free Earlobes": "जुड़े हुए बनाम स्वतंत्र कर्णपालि (कान की लौ)",
    "Look at your classmates' ears right now! Free earlobes are a dominant trait; attached earlobes are homozygous recessive. You can see Mendel's laws right in your classroom!": "अभी अपनी कक्षा में सहपाठियों के कानों को देखें! स्वतंत्र कान की लौ प्रभावी लक्षण है; जुड़ी हुई लौ अप्रभावी है। आप अपनी कक्षा में मेंडल के नियमों को साक्षात देख सकते हैं!",
    "The Indian Green Revolution": "भारतीय हरित क्रांति (High-Yielding Crops)",
    "Dr. M. S. Swaminathan utilized Mendel's principles of cross-breeding to develop semi-dwarf wheat strains, saving India from catastrophic famine in the 1960s!": "डॉ. एम. एस. स्वामीनाथन ने 1960 के दशक में भारत को भुखमरी से बचाने के लिए अर्ध-बौने गेहूं की किस्मों को विकसित करने हेतु मेंडल के संकरण सिद्धांतों का उपयोग किया!",
    "The chapter on one card": "एक कार्ड पर पूरा अध्याय",
    "Heredity": "आनुवंशिकता",
    "Transmission of traits from parents to offspring via DNA genes.": "डीएनए जीनों के माध्यम से माता-पिता से संतानों में लक्षणों का संचरण।",
    "Mendel's Laws": "मेंडल के नियम",
    "Dominance, Segregation, and Independent Assortment in Garden Peas.": "उद्यान मटर में प्रभाविता, पृथक्करण और स्वतंत्र अपव्यूहन के नियम।",
    "Monohybrid Ratios": "एकसंकर अनुपात",
    "F2 Phenotypic: 3:1 (Tall:Dwarf) | F2 Genotypic: 1:2:1 (TT:Tt:tt).": "F2 लक्षणाप्ररूप: 3:1 (लंबा:बौना) | F2 जीनीप्ररूप: 1:2:1 (TT:Tt:tt)।",
    "Sex Determination": "लिंग निर्धारण",
    "Father's sperm (X or Y) strictly determines child's biological sex.": "पिता का शुक्राणु (X या Y) ही बच्चे का जैविक लिंग निर्धारित करता है।",
    "Evolution": "जैव विकास",
    "Survival of advantageous variations via natural selection over time.": "समय के साथ प्राकृतिक वरण के माध्यम से लाभकारी विभिन्नताओं का विकास।",
    "Now test yourself": "अब अपनी परीक्षा लें",
    "Genetics mastery unlocked! You understand DNA inheritance, Punnett squares, and biological evolution.": "आनुवंशिकी मास्टरी अनलॉक! आप डीएनए संचरण, पुनेट वर्ग और जैव विकास को पूरी तरह समझ चुके हैं।",
}

SLIDES = [
    {
        "kind": "title",
        "t": "Heredity and Evolution — Mendelian Genetics & Punnett Squares",
        "s": "Science · Class 10 · Chapter 9",
        "b": "Why do children look like their parents yet remain uniquely distinct? Gregor Mendel unraveled this mystery in a monastery garden using simple sweet pea plants!",
        "viz": "pea_intro",
    },
    {
        "kind": "text",
        "t": "The whole chapter in one line",
        "b": "Heredity transfers biological traits across generations via genes located on chromosomes, obeying Mendel's laws of dominance, segregation, and independent assortment.",
        "mentor": "Acharya's Insight: You are not an exact carbon copy of your parents. You are a brand new combination of nature's greatest genetic deck of cards!",
        "viz": "dna_visual",
    },
    {
        "kind": "text",
        "t": "What Is Heredity?",
        "b": "The transmission of characters, traits, and physical features from parents to their biological offspring through genes is known as HEREDITY.",
        "viz": "dna_visual",
    },
    {
        "kind": "text",
        "t": "Variations: Why Clones Do Not Rule",
        "b": "The subtle differences in traits between individuals of the same species are called VARIATIONS. In sexual reproduction, mixing maternal and paternal DNA generates diverse variations essential for evolution!",
        "viz": "variation_visual",
    },
    {
        "kind": "text",
        "t": "Mendel and His Garden Pea Plant",
        "b": "Gregor Johann Mendel chose the Garden Pea (Pisum sativum) because it had distinct contrasting traits, self-pollinated easily, had a short life cycle, and produced hundreds of seeds per generation.",
        "viz": "pea_traits_visual",
    },
    {
        "kind": "text",
        "t": "Dominant vs Recessive Alleles",
        "b": "A DOMINANT allele (T) expresses its trait even when only one copy is present (TT or Tt). A RECESSIVE allele (t) is masked and only appears when both copies are identical (tt).",
        "viz": "allele_visual",
    },
    {
        "kind": "text",
        "t": "Phenotype vs Genotype",
        "b": "PHENOTYPE is the observable physical appearance (e.g., Tall or Dwarf plant). GENOTYPE is the underlying genetic makeup of alleles inside the cell (e.g., TT, Tt, or tt).",
        "viz": "pheno_geno_visual",
    },
    {
        "kind": "text",
        "t": "The Monohybrid Cross (TT x tt)",
        "b": "When pure Tall (TT) is crossed with pure Dwarf (tt), all F1 offspring are TALL (Tt)! When F1 plants self-pollinate, the hidden dwarf trait miraculously reappears in F2 in a 3:1 ratio!",
        "viz": "cross_visual",
    },
    {
        "kind": "sim",
        "t": "Try it: Mendelian Punnett Square Simulator",
        "b": "Cross parent pea alleles in real-time. Watch the 4-cell Punnett grid calculate the exact 3:1 phenotypic and 1:2:1 genotypic ratios right before your eyes!",
        "sim": "punnett_sim",
    },
    {
        "kind": "text",
        "t": "How Do Genes Control Physical Traits?",
        "b": "A cellular gene is a section of DNA providing instructions for making a specific protein enzyme. Efficient enzymes synthesize plant growth hormone making it tall; defective enzymes yield a dwarf plant!",
        "viz": "protein_gene_visual",
    },
    {
        "kind": "text",
        "t": "Sex Determination in Human Beings",
        "b": "Humans have 23 pairs of chromosomes. Pair 23 are Sex Chromosomes: females have XX, males have XY. All eggs carry X; sperm carry either X or Y. The father's sperm strictly determines the child's sex!",
        "viz": "sex_determination_visual",
    },
    {
        "kind": "text",
        "t": "Dihybrid Cross: Independent Assortment",
        "b": "Crossing Round Yellow seeds (RRYY) with Wrinkled Green (rryy) produces Round Yellow in F1. In F2, traits segregate independently yielding a classic 9:3:3:1 phenotypic ratio!",
        "viz": "dihybrid_visual",
    },
    {
        "kind": "text",
        "t": "Acquired vs Inherited Traits",
        "b": "Traits developed during a lifetime (gym muscles, language, scars) are ACQUIRED and not passed to offspring. Only changes in the DNA of germ cells (sperm/egg) are INHERITED!",
        "viz": "acquired_visual",
    },
    {
        "kind": "text",
        "t": "Evolution and Natural Selection",
        "b": "In nature, individuals carrying variations that give survival advantage (e.g. green beetles camouflaged on green leaves against crows) survive longer and reproduce, driving EVOLUTION.",
        "viz": "beetle_visual",
    },
    {
        "kind": "steps",
        "t": "Worked example — Predicting Genetic Offspring",
        "b": "A homozygous tall pea plant (TT) is crossed with a heterozygous tall plant (Tt). What percentage of offspring will be dwarf?",
        "steps": [
            "Step 1: Parent gametes: Parent 1 produces all T gametes. Parent 2 produces 50% T and 50% t gametes.",
            "Step 2: Punnett Cross: T x T -> TT (50%) and T x t -> Tt (50%).",
            "Step 3: All offspring carry at least one dominant T allele. Therefore, 100% are Tall and 0% are Dwarf!",
            "Zero offspring will be dwarf because the dominant T allele masks the recessive t in all cases!",
        ],
        "viz": "cross_visual",
    },
    {
        "kind": "check",
        "q": "What is the phenotypic ratio of a Mendelian monohybrid F2 generation?",
        "opts": [
            "3 : 1 (Tall : Dwarf)",
            "1 : 2 : 1 (TT : Tt : tt)",
            "9 : 3 : 3 : 1 (Dihybrid)",
        ],
        "ans": 0,
        "why": "In the F2 generation of a monohybrid cross, 75% show the dominant tall phenotype and 25% show the dwarf phenotype, giving a 3:1 ratio.",
    },
    {
        "kind": "check",
        "q": "Who genetically determines the sex of a human newborn baby?",
        "opts": [
            "The Father (via X or Y sperm)",
            "The Mother (via egg cytoplasm)",
            "Environmental temperature",
        ],
        "ans": 0,
        "why": "A mother always contributes an X chromosome. The sex depends entirely on whether the father's fertilizing sperm carries an X (yielding XX female) or Y (yielding XY male).",
    },
    {
        "kind": "mistake",
        "t": "Three mistakes that cost marks",
        "b": "Watch out for these common misconceptions about genetics and inheritance.",
        "items": [
            [
                "Blaming mothers for girl children",
                "A tragic social misconception! Mothers have only XX chromosomes and can only donate X. Biologically, the father's Y sperm alone determines if a baby is male.",
            ],
            [
                "Confusing Phenotypic vs Genotypic ratios",
                "3:1 is the PHENOTYPIC ratio (what you see outside: 3 Tall, 1 Dwarf). 1:2:1 is the GENOTYPIC ratio (hidden alleles: 1 TT, 2 Tt, 1 tt). Never mix them up!",
            ],
            [
                "Believing acquired traits can be inherited",
                "Cutting mice tails for 20 generations still produces mice with full-length tails! Bodily changes in somatic cells never change the reproductive germ-line DNA.",
            ],
        ],
    },
    {
        "kind": "text",
        "t": "Where you meet it in real life",
        "b": "From attached earlobes in your school class to high-yielding Green Revolution crops, genetics touches every breath.",
        "mentor": "Look in the mirror today: whether your earlobe is free or attached was decided by Mendel's 3:1 ratio before you were born!",
        "viz": "pea_intro",
    },
    {
        "kind": "summary",
        "t": "The chapter on one card",
        "b": "Mendel's laws, monohybrid ratios, sex determination, and evolution fundamentals on a single card.",
        "items": [
            [
                "Heredity",
                "Transmission of traits from parents to offspring via DNA genes.",
            ],
            [
                "Mendel's Laws",
                "Dominance, Segregation, and Independent Assortment in Garden Peas.",
            ],
            [
                "Monohybrid Ratios",
                "F2 Phenotypic: 3:1 (Tall:Dwarf) | F2 Genotypic: 1:2:1 (TT:Tt:tt).",
            ],
            [
                "Sex Determination",
                "Father's sperm (X or Y) strictly determines child's biological sex.",
            ],
            [
                "Evolution",
                "Survival of advantageous variations via natural selection over time.",
            ],
        ],
    },
    {
        "kind": "end",
        "t": "Now test yourself",
        "s": "Genetics mastery unlocked! You understand DNA inheritance, Punnett squares, and biological evolution.",
        "b": "You have mastered the science of inheritance that governs every living organism on Earth!",
    },
]

SVG_AND_SIMS_JS = """
<script>
const VB = 'viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet"';
function svgOpen(extra){ return '<svg '+VB+' font-family="system-ui,sans-serif" '+(extra||"")+'>'; }

function vizPunnett(p1, p2){
  let s = svgOpen();
  s += '<rect x="15" y="15" width="370" height="270" rx="12" fill="#081422" stroke="#1d3852"/>';

  // Punnett 2x2 Grid Coordinates
  const gx = 130, gy = 80, cw = 100, ch = 80;

  // Header Gametes Labels
  // Parent 1 (Top horizontal: P1_allele1, P1_allele2)
  s += '<text x="110" y="55" fill="#31e6c4" font-size="12" font-weight="900">Parent 1 Gametes ▶</text>';
  s += '<circle cx="180" cy="55" r="16" fill="#31e6c4" fill-opacity=".2" stroke="#31e6c4" stroke-width="2"/>';
  s += '<text x="180" y="60" fill="#31e6c4" font-size="15" font-weight="900" text-anchor="middle">'+p1[0]+'</text>';

  s += '<circle cx="280" cy="55" r="16" fill="#31e6c4" fill-opacity=".2" stroke="#31e6c4" stroke-width="2"/>';
  s += '<text x="280" y="60" fill="#31e6c4" font-size="15" font-weight="900" text-anchor="middle">'+p1[1]+'</text>';

  // Parent 2 (Left vertical: P2_allele1, P2_allele2)
  s += '<circle cx="95" cy="120" r="16" fill="#ffc247" fill-opacity=".2" stroke="#ffc247" stroke-width="2"/>';
  s += '<text x="95" y="125" fill="#ffc247" font-size="15" font-weight="900" text-anchor="middle">'+p2[0]+'</text>';

  s += '<circle cx="95" cy="200" r="16" fill="#ffc247" fill-opacity=".2" stroke="#ffc247" stroke-width="2"/>';
  s += '<text x="95" y="205" fill="#ffc247" font-size="15" font-weight="900" text-anchor="middle">'+p2[1]+'</text>';

  // 4 Cells:
  const cells = [
    { r: 0, c: 0, a1: p2[0], a2: p1[0] },
    { r: 0, c: 1, a1: p2[0], a2: p1[1] },
    { r: 1, c: 0, a1: p2[1], a2: p1[0] },
    { r: 1, c: 1, a1: p2[1], a2: p1[1] }
  ];

  for(const cell of cells){
    const x = gx + cell.c * cw;
    const y = gy + cell.r * ch;

    // Normalizing genotype (T before t)
    const g = (cell.a1 === "T" || cell.a2 === "T") && (cell.a1 === "t" || cell.a2 === "t") ? "Tt" : (cell.a1 + cell.a2);
    const isTall = g.includes("T");
    const fillCol = isTall ? "rgba(49,230,196,.12)" : "rgba(255,95,120,.12)";
    const strokeCol = isTall ? "#31e6c4" : "#ff5f78";
    const label = isTall ? "🌱 Tall" : "🌾 Dwarf";

    s += '<rect x="'+x+'" y="'+y+'" width="'+cw+'" height="'+ch+'" fill="'+fillCol+'" stroke="'+strokeCol+'" stroke-width="2"/>';
    s += '<text x="'+(x+cw/2)+'" y="'+(y+35)+'" fill="'+strokeCol+'" font-size="22" font-weight="900" text-anchor="middle">'+g+'</text>';
    s += '<text x="'+(x+cw/2)+'" y="'+(y+60)+'" fill="'+(isTall?"#a7f3d0":"#fecdd3")+'" font-size="12" font-weight="700" text-anchor="middle">'+label+'</text>';
  }

  s += '<text x="200" y="280" fill="#ffc247" font-size="13.5" font-weight="800" text-anchor="middle">Offspring Genotypes: 4 Fertilization Possibilities</text>';
  return s + '</svg>';
}

function vizDna(){
  let s = svgOpen();
  s += '<rect x="15" y="15" width="370" height="270" rx="12" fill="#09131d" stroke="#18324a"/>';
  // Double helix strands
  for(let i=0; i<12; i++){
    const y = 45 + i*18;
    const x1 = 200 + Math.sin(i*0.6)*60;
    const x2 = 200 - Math.sin(i*0.6)*60;
    const col = (i%2===0) ? "#31e6c4" : "#ffc247";
    s += '<line x1="'+x1+'" y1="'+y+'" x2="'+x2+'" y2="'+y+'" stroke="'+col+'" stroke-width="3" stroke-linecap="round"/>';
    s += '<circle cx="'+x1+'" cy="'+y+'" r="5" fill="#31e6c4"/>';
    s += '<circle cx="'+x2+'" cy="'+y+'" r="5" fill="#ffc247"/>';
  }
  s += '<text x="200" y="275" fill="#31e6c4" font-size="14" font-weight="800" text-anchor="middle">DNA Chromosome Architecture & Genes</text>';
  return s + '</svg>';
}

const VIZ = {
  pea_intro: ()=> vizPunnett(["T","t"], ["T","t"]),
  dna_visual: ()=> vizDna(),
  variation_visual: ()=> vizDna(),
  pea_traits_visual: ()=> vizPunnett(["T","T"], ["t","t"]),
  allele_visual: ()=> vizPunnett(["T","t"], ["T","t"]),
  pheno_geno_visual: ()=> vizPunnett(["T","t"], ["T","t"]),
  cross_visual: ()=> vizPunnett(["T","t"], ["T","t"]),
  protein_gene_visual: ()=> vizDna(),
  sex_determination_visual: ()=> vizPunnett(["X","Y"], ["X","X"]),
  dihybrid_visual: ()=> vizPunnett(["T","t"], ["T","t"]),
  acquired_visual: ()=> vizDna(),
  beetle_visual: ()=> vizDna(),
};

const SIM = {
  punnett_sim: ()=>'<label style="font-size:13.5px;color:var(--muted)">Select Cross Mode (Mendelian Generations):</label>'+
    '<div class="simctl">'+
      '<input id="sCross" type="range" min="1" max="3" value="2" step="1"/>'+
      '<div class="readout">'+
        '<span>Cross: <b id="oCross">F1 Self-Cross (Tt x Tt)</b></span> | '+
        '<span>Phenotype: <b id="oRatio" style="color:#31e6c4">3 Tall : 1 Dwarf</b></span>'+
      '</div>'+
      '<div style="font-size:12.5px;color:var(--muted);margin-top:6px" id="oGeno">'+
        'Genotypic Ratio: 1 TT (25%) : 2 Tt (50%) : 1 tt (25%)'+
      '</div>'+
    '</div>'
};

function simViz(name, v){
  if(v === "1") return vizPunnett(["T","T"], ["t","t"]);
  if(v === "3") return vizPunnett(["T","T"], ["T","t"]);
  return vizPunnett(["T","t"], ["T","t"]);
}

function initSim(name){
  return "2";
}

function wireSim(name){
  if(name === "punnett_sim"){
    const sC = document.getElementById("sCross");
    const oC = document.getElementById("oCross");
    const oR = document.getElementById("oRatio");
    const oG = document.getElementById("oGeno");

    sC.addEventListener("input", (e)=>{
      const v = e.target.value;
      if(v === "1"){
        oC.textContent = "Pure Parental Cross (TT x tt)";
        oR.textContent = "100% Tall (All Tt)";
        oR.style.color = "#31e6c4";
        oG.textContent = "Genotype: 100% Heterozygous Tt (All hybrid tall plants)";
      } else if(v === "2"){
        oC.textContent = "F1 Self-Cross (Tt x Tt)";
        oR.textContent = "3 Tall : 1 Dwarf (75% : 25%)";
        oR.style.color = "#31e6c4";
        oG.textContent = "Genotype: 1 TT (25%) : 2 Tt (50%) : 1 tt (25%)";
      } else {
        oC.textContent = "Back Cross (TT x Tt)";
        oR.textContent = "100% Tall (50% TT, 50% Tt)";
        oR.style.color = "#ffc247";
        oG.textContent = "Genotype: 2 TT (50%) : 2 Tt (50%) : 0 Dwarf (0%)";
      }
      setVis(simViz(name, v));
    });
  }
}
</script>
"""

if __name__ == "__main__":
    html = build_single_chapter_html(
        chapter_id="class10_science_ch09_heredity_evolution",
        title="Heredity and Evolution (Class 10 Science Ch 9)",
        grade_subject_sub="Class 10 Science · Chapter 9: Heredity and Evolution",
        chapter_num_label="Chapter 9",
        slides=SLIDES,
        chapter_svg_and_sims_js=SVG_AND_SIMS_JS,
        extra_words=EXTRA_WORDS,
        extra_phrases=EXTRA_PHRASES,
    )
    out_file = CHAPTERS_DIR / "class10_science_ch09_heredity_evolution.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Compiled Chapter 9 Heredity and Evolution to: {out_file}")
    print(f"Size: {len(html):,} bytes ({len(html)/1024:.1f} KB)")
