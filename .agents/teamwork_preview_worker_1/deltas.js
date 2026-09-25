// api/chapters/deltas.js
// AASHA-AIOS Curriculum Delta Route — Class 6–8 Mathematics
// Exposes versioned question item banks with visual manipulative specs,
// Foundation F01 Escape Run Boss Challenge mechanics, and LLE bilingual vocabulary.

export const access = "public";
export const methods = ["GET"];

const DELTA_REGISTRY = {
  "c6_fractions": {
    "chapterId": "c6_fractions",
    "title": "Fractions — Understanding Parts of Whole (भिन्न)",
    "grade": 6,
    "version": 3,
    "updatedAt": "2026-09-17T03:00:00Z",
    "f01Mechanics": {
      "foundation": "F01_EscapeRun",
      "timeLimitSec": 25,
      "lives": 3,
      "streakMultipliers": {
        "1": 1.0,
        "3": 1.5,
        "5": 2.0
      },
      "shieldMessage": "Cognitive Shield Recharged! Review the visual fraction bar before advancing."
    },
    "visualManipulatives": {
      "sim-fraction-bar": {
        "type": "svg_bar_partition",
        "description": "Interactive segmented bar partition showing numerator shaded over denominator total",
        "defaultSegments": 8,
        "activeSegments": 3,
        "touchTargetMin": "44x44px"
      },
      "sim-fraction-circle": {
        "type": "canvas_pizza_sector",
        "description": "Circular sector partition model with dynamic fractional division",
        "defaultParts": 6
      },
      "sim-fraction-equiv": {
        "type": "svg_dual_bar_equiv",
        "description": "Stacked fraction bars comparing proportional slices across equal lengths",
        "defaultBars": [
          { "parts": 3, "shaded": 2 },
          { "parts": 12, "shaded": 8 }
        ]
      }
    },
    "vocab": {
      "fraction": { "hindi": "भिन्न", "phonics": "फ्रैक्शन", "def": "संपूर्ण वस्तु का समान भागों में से चुना गया हिस्सा" },
      "numerator": { "hindi": "अंश", "phonics": "न्यूमरेटर", "def": "भिन्न का ऊपरी भाग जो चुने हुए हिस्सों को दर्शाता है" },
      "denominator": { "hindi": "हर", "phonics": "डिनॉमिनेटर", "def": "भिन्न का निचला भाग जो कुल बराबर हिस्सों को दर्शाता है" },
      "proper_fraction": { "hindi": "उचित भिन्न", "phonics": "प्रॉपर फ्रैक्शन", "def": "वह भिन्न जिसमें अंश, हर से छोटा होता है" },
      "improper_fraction": { "hindi": "विषम भिन्न", "phonics": "इम्प्रॉपर फ्रैक्शन", "def": "वह भिन्न जिसमें अंश, हर के बराबर या बड़ा होता है" },
      "mixed_number": { "hindi": "मिश्रित भिन्न", "phonics": "मिक्स्ड नंबर", "def": "एक पूर्ण संख्या और एक उचित भिन्न का संयुक्त रूप" },
      "equivalent_fraction": { "hindi": "तुल्य भिन्न", "phonics": "इक्विवेलेंट फ्रैक्शन", "def": "समान मात्रा अथवा मान दर्शाने वाले भिन्न" },
      "common_denominator": { "hindi": "उभयनिष्ठ हर", "phonics": "कॉमन डिनॉमिनेटर", "def": "दो या अधिक भिन्नों का एक समान हर (ल.स.प. द्वारा)" }
    },
    "itemBank": [
      {
        "id": "c6_frac_q1",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["numerator", "denominator"],
        "stem": "In any fraction \\(\\frac{a}{b}\\), what mathematical role does the denominator \\(b\\) represent?",
        "options": [
          { "text": "The total count of equal parts that compose the whole", "isCorrect": true },
          { "text": "The number of selected or shaded parts", "isCorrect": false, "m": "Confuses numerator with denominator; the top number counts selected portions." },
          { "text": "The numerical difference between parts", "isCorrect": false, "m": "Treats fraction components as a subtraction comparison rather than part-whole partition." },
          { "text": "The count of unshaded parts remaining", "isCorrect": false, "m": "Denominator counts all equal divisions collectively rather than solely remaining pieces." }
        ],
        "hints": [
          { "tier": "H1", "text": "Look at the bottom position of the fraction." },
          { "tier": "H2", "text": "The whole object gets divided into a certain quantity of identical pieces." },
          { "tier": "H3", "text": "The upper number counts parts taken; the lower number defines partition size." },
          { "tier": "H4", "text": "Denominator names the total equal divisions creating one complete unit." }
        ]
      },
      {
        "id": "c6_frac_q2",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["fraction", "numerator", "denominator"],
        "stem": "A rectangular bar divided into 8 equal parts has 3 parts shaded. Which fraction represents the shaded region?",
        "options": [
          { "text": "\\(\\frac{3}{8}\\)", "isCorrect": true },
          { "text": "\\(\\frac{3}{5}\\)", "isCorrect": false, "m": "Compares shaded parts to unshaded parts rather than to the entire whole bar." },
          { "text": "\\(\\frac{8}{3}\\)", "isCorrect": false, "m": "Inverts fraction structure by placing total parts above selected parts." },
          { "text": "\\(\\frac{5}{8}\\)", "isCorrect": false, "m": "Selected unshaded fraction rather than shaded fraction requested in the prompt." }
        ],
        "hints": [
          { "tier": "H1", "text": "Count shaded pieces first, then count all pieces together." },
          { "tier": "H2", "text": "Fraction form requires selected pieces over total equal pieces." },
          { "tier": "H3", "text": "Numerator takes shaded count; denominator takes whole partition count." },
          { "tier": "H4", "text": "Place 3 over total segment count 8." }
        ]
      },
      {
        "id": "c6_frac_q3",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["proper_fraction", "numerator", "denominator"],
        "stem": "Which condition defines a proper fraction?",
        "options": [
          { "text": "Numerator strictly less than denominator", "isCorrect": true },
          { "text": "Numerator strictly greater than denominator", "isCorrect": false, "m": "Defines an improper fraction representing values greater than one whole." },
          { "text": "Numerator exactly equal to denominator", "isCorrect": false, "m": "Represents one complete whole rather than a strictly proper fractional part." },
          { "text": "Denominator fixed at 100", "isCorrect": false, "m": "Confuses general proper fractions with percentage denominators." }
        ],
        "hints": [
          { "tier": "H1", "text": "Consider whether the fraction value remains strictly less than one whole." },
          { "tier": "H2", "text": "In a proper fraction, you possess fewer pieces than needed for a complete whole." },
          { "tier": "H3", "text": "Compare the magnitude of top number against bottom number." },
          { "tier": "H4", "text": "Top value must remain smaller than bottom value." }
        ]
      },
      {
        "id": "c6_frac_q4",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-fraction-equiv",
        "vocabRefs": ["equivalent_fraction"],
        "stem": "Which fraction represents an equivalent value to \\(\\frac{2}{3}\\) with denominator 12?",
        "options": [
          { "text": "\\(\\frac{8}{12}\\)", "isCorrect": true },
          { "text": "\\(\\frac{6}{12}\\)", "isCorrect": false, "m": "Added common amount to both terms rather than multiplying by constant factor." },
          { "text": "\\(\\frac{4}{12}\\)", "isCorrect": false, "m": "Multiplied numerator by two while multiplying denominator by four." },
          { "text": "\\(\\frac{10}{12}\\)", "isCorrect": false, "m": "Multiplied numerator by incorrect scaling multiplier." }
        ],
        "hints": [
          { "tier": "H1", "text": "Determine what factor scales denominator 3 up to 12." },
          { "tier": "H2", "text": "Equivalent fractions require multiplying both top and bottom by identical factors." },
          { "tier": "H3", "text": "Multiply numerator by the same scaling factor applied to denominator." },
          { "tier": "H4", "text": "Denominator multiplies by 4; multiply top number 2 by 4." }
        ]
      },
      {
        "id": "c6_frac_q5",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["improper_fraction", "mixed_number"],
        "stem": "Convert the improper fraction \\(\\frac{17}{5}\\) into mixed number form.",
        "options": [
          { "text": "\\(3\\frac{2}{5}\\)", "isCorrect": true },
          { "text": "\\(2\\frac{7}{5}\\)", "isCorrect": false, "m": "Left an improper fractional portion rather than extracting all complete wholes." },
          { "text": "\\(3\\frac{1}{5}\\)", "isCorrect": false, "m": "Calculation slip in division remainder when subtracting whole multiples." },
          { "text": "\\(5\\frac{2}{3}\\)", "isCorrect": false, "m": "Swapped whole quotient with original denominator." }
        ],
        "hints": [
          { "tier": "H1", "text": "Divide numerator 17 by denominator 5 to find whole groups." },
          { "tier": "H2", "text": "Quotient forms whole number; remainder forms new numerator over original denominator." },
          { "tier": "H3", "text": "17 divided by 5 yields quotient 3 with remainder 2." },
          { "tier": "H4", "text": "Combine whole quotient 3 with remainder 2 over original denominator 5." }
        ]
      },
      {
        "id": "c6_frac_q6",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["mixed_number", "improper_fraction"],
        "stem": "Express the mixed number \\(4\\frac{3}{7}\\) as an improper fraction.",
        "options": [
          { "text": "\\(\\frac{31}{7}\\)", "isCorrect": true },
          { "text": "\\(\\frac{19}{7}\\)", "isCorrect": false, "m": "Multiplied whole number by numerator rather than denominator." },
          { "text": "\\(\\frac{28}{7}\\)", "isCorrect": false, "m": "Forgot to add the existing numerator portion after multiplying whole parts." },
          { "text": "\\(\\frac{31}{4}\\)", "isCorrect": false, "m": "Replaced original denominator with whole number multiplier." }
        ],
        "hints": [
          { "tier": "H1", "text": "Each whole unit contains 7 sevenths." },
          { "tier": "H2", "text": "Multiply whole number by denominator, then add numerator." },
          { "tier": "H3", "text": "Compute whole part products: 4 times 7, then add remaining 3 parts." },
          { "tier": "H4", "text": "Sum all sevenths over original denominator 7." }
        ]
      },
      {
        "id": "c6_frac_q7",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-equiv",
        "vocabRefs": ["common_denominator"],
        "stem": "Which comparison statement correctly relates \\(\\frac{3}{5}\\) and \\(\\frac{5}{8}\\)?",
        "options": [
          { "text": "\\(\\frac{3}{5} < \\frac{5}{8}\\)", "isCorrect": true },
          { "text": "\\(\\frac{3}{5} > \\frac{5}{8}\\)", "isCorrect": false, "m": "Cross-multiplied directions in reverse or judged based on smaller denominator." },
          { "text": "\\(\\frac{3}{5} = \\frac{5}{8}\\)", "isCorrect": false, "m": "Assumed equal differences between numerators and denominators imply equivalence." },
          { "text": "\\(\\frac{3}{5} > \\frac{6}{8}\\)", "isCorrect": false, "m": "Confused fraction magnitudes without finding common denominator." }
        ],
        "hints": [
          { "tier": "H1", "text": "Convert both fractions to common denominator 40." },
          { "tier": "H2", "text": "Compare numerators after equalizing denominators: 3*8 versus 5*5." },
          { "tier": "H3", "text": "Cross products give 24 for first fraction and 25 for second fraction." },
          { "tier": "H4", "text": "24 fortieths compared against 25 fortieths." }
        ]
      },
      {
        "id": "c6_frac_q8",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["common_denominator"],
        "stem": "Calculate the sum of like fractions: \\(\\frac{3}{11} + \\frac{5}{11}\\).",
        "options": [
          { "text": "\\(\\frac{8}{11}\\)", "isCorrect": true },
          { "text": "\\(\\frac{8}{22}\\)", "isCorrect": false, "m": "Added denominators together rather than retaining the shared piece size." },
          { "text": "\\(\\frac{15}{11}\\)", "isCorrect": false, "m": "Multiplied numerators rather than adding addends." },
          { "text": "\\(\\frac{2}{11}\\)", "isCorrect": false, "m": "Subtracted numerators rather than combining them." }
        ],
        "hints": [
          { "tier": "H1", "text": "Notice both fractions possess matching denominators." },
          { "tier": "H2", "text": "Piece size elevenths remains constant during addition." },
          { "tier": "H3", "text": "Retain denominator 11 and add numerators 3 and 5." },
          { "tier": "H4", "text": "Sum top numbers over unchanged denominator 11." }
        ]
      },
      {
        "id": "c6_frac_q9",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-equiv",
        "vocabRefs": ["common_denominator"],
        "stem": "Find the sum of unlike fractions: \\(\\frac{2}{5} + \\frac{1}{3}\\).",
        "options": [
          { "text": "\\(\\frac{11}{15}\\)", "isCorrect": true },
          { "text": "\\(\\frac{3}{8}\\)", "isCorrect": false, "m": "Added numerators together and denominators together across unlike fractions." },
          { "text": "\\(\\frac{3}{15}\\)", "isCorrect": false, "m": "Added numerators without scaling them to common denominator." },
          { "text": "\\(\\frac{7}{15}\\)", "isCorrect": false, "m": "Incorrectly scaled numerators during common denominator conversion." }
        ],
        "hints": [
          { "tier": "H1", "text": "Find common denominator using LCM of 5 and 3." },
          { "tier": "H2", "text": "Convert both fractions to fifteenths before adding." },
          { "tier": "H3", "text": "Scale fractions: 2/5 to 6/15, and 1/3 to 5/15." },
          { "tier": "H4", "text": "Add scaled numerators 6 and 5 over 15." }
        ]
      },
      {
        "id": "c6_frac_q10",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["common_denominator"],
        "stem": "Evaluate the difference: \\(\\frac{5}{6} - \\frac{1}{4}\\).",
        "options": [
          { "text": "\\(\\frac{7}{12}\\)", "isCorrect": true },
          { "text": "\\(\\frac{4}{2}\\)", "isCorrect": false, "m": "Subtracted numerators and subtracted denominators directly." },
          { "text": "\\(\\frac{4}{12}\\)", "isCorrect": false, "m": "Subtracted unscaled numerators without common denominator adjustment." },
          { "text": "\\(\\frac{9}{12}\\)", "isCorrect": false, "m": "Added scaled values rather than subtracting second term." }
        ],
        "hints": [
          { "tier": "H1", "text": "Find the least common multiple for denominators 6 and 4." },
          { "tier": "H2", "text": "Lowest common denominator equals 12." },
          { "tier": "H3", "text": "Convert 5/6 to 10/12 and 1/4 to 3/12." },
          { "tier": "H4", "text": "Subtract scaled numerators: 10 minus 3 over 12." }
        ]
      },
      {
        "id": "c6_frac_q11",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-fraction-circle",
        "vocabRefs": ["mixed_number", "common_denominator"],
        "stem": "Sarita purchased \\(\\frac{2}{5}\\) metre of ribbon and Lalita purchased \\(\\frac{3}{4}\\) metre of ribbon. What total length of ribbon did both purchase together?",
        "options": [
          { "text": "\\(1\\frac{3}{20}\\) m", "isCorrect": true },
          { "text": "\\(\\frac{5}{9}\\) m", "isCorrect": false, "m": "Added numerators and denominators directly across ribbon lengths." },
          { "text": "\\(\\frac{17}{20}\\) m", "isCorrect": false, "m": "Arithmetic error in cross-scaling numerator terms." },
          { "text": "\\(1\\frac{1}{20}\\) m", "isCorrect": false, "m": "Calculation slip when converting improper sum to mixed form." }
        ],
        "hints": [
          { "tier": "H1", "text": "Combine both ribbon lengths using addition." },
          { "tier": "H2", "text": "Find common denominator for 5 and 4, which equals 20." },
          { "tier": "H3", "text": "Convert to twentieths: 8/20 plus 15/20." },
          { "tier": "H4", "text": "Sum to 23/20 and convert to mixed metres." }
        ]
      },
      {
        "id": "c6_frac_q12",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["fraction", "common_denominator"],
        "stem": "A piece of wire \\(\\frac{7}{8}\\) metre long broke into two pieces. One piece measured \\(\\frac{1}{4}\\) metre. What length remains for the second piece?",
        "options": [
          { "text": "\\(\\frac{5}{8}\\) m", "isCorrect": true },
          { "text": "\\(\\frac{6}{4}\\) m", "isCorrect": false, "m": "Subtracted numerators and denominators separately without common denominator." },
          { "text": "\\(\\frac{3}{8}\\) m", "isCorrect": false, "m": "Subtracted incorrectly after common denominator conversion." },
          { "text": "\\(\\frac{9}{8}\\) m", "isCorrect": false, "m": "Added wire portions together rather than determining remaining difference." }
        ],
        "hints": [
          { "tier": "H1", "text": "Subtract broken piece length from total wire length." },
          { "tier": "H2", "text": "Common denominator between 8 and 4 equals 8." },
          { "tier": "H3", "text": "Rewrite 1/4 metre as 2/8 metre." },
          { "tier": "H4", "text": "Compute 7/8 minus 2/8 to find remaining wire." }
        ]
      },
      {
        "id": "c6_frac_q13",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-fraction-circle",
        "vocabRefs": ["mixed_number"],
        "stem": "Ramesh completed \\(2\\frac{1}{2}\\) hours of academic study and \\(1\\frac{1}{4}\\) hours of sports training. What total duration did he spend across both activities?",
        "options": [
          { "text": "\\(3\\frac{3}{4}\\) hours", "isCorrect": true },
          { "text": "\\(3\\frac{2}{6}\\) hours", "isCorrect": false, "m": "Added fractional numerators and denominators directly without finding fourths." },
          { "text": "\\(4\\frac{1}{4}\\) hours", "isCorrect": false, "m": "Carried excess whole hour without sufficient fractional sum." },
          { "text": "\\(3\\frac{1}{4}\\) hours", "isCorrect": false, "m": "Omitted half hour fractional addend from total." }
        ],
        "hints": [
          { "tier": "H1", "text": "Add whole hour portions and fractional hour portions." },
          { "tier": "H2", "text": "Convert 1/2 hour to 2/4 hour for common denominator." },
          { "tier": "H3", "text": "Sum wholes: 2 + 1; sum fractions: 2/4 + 1/4." },
          { "tier": "H4", "text": "Combine whole sum 3 with fraction sum 3/4." }
        ]
      },
      {
        "id": "c6_frac_q14",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-fraction-bar",
        "vocabRefs": ["improper_fraction", "common_denominator"],
        "stem": "Jaidev takes \\(2\\frac{1}{5}\\) minutes to walk across the school park, while Rahul takes \\(\\frac{7}{4}\\) minutes. Who takes less time, and by what difference?",
        "options": [
          { "text": "Rahul takes less time by \\(\\frac{9}{20}\\) min", "isCorrect": true },
          { "text": "Jaidev takes less time by \\(\\frac{9}{20}\\) min", "isCorrect": false, "m": "Identified the wrong student despite finding correct numerical difference." },
          { "text": "Rahul takes less time by \\(\\frac{1}{20}\\) min", "isCorrect": false, "m": "Subtracted mixed fractions incorrectly after denominator conversion." },
          { "text": "Both take equal time", "isCorrect": false, "m": "Assumed fractional values match without converting to common denominator." }
        ],
        "hints": [
          { "tier": "H1", "text": "Convert both durations to twentieths of a minute." },
          { "tier": "H2", "text": "2 1/5 equals 11/5 = 44/20; 7/4 equals 35/20." },
          { "tier": "H3", "text": "Compare 35/20 against 44/20 to see who finishes faster." },
          { "tier": "H4", "text": "Subtract 35/20 from 44/20 to determine time gap." }
        ]
      }
    ]
  },
  "c7_perimeter_area": {
    "chapterId": "c7_perimeter_area",
    "title": "Perimeter and Area — Geometric Measurement (परिमाप और क्षेत्रफल)",
    "grade": 7,
    "version": 3,
    "updatedAt": "2026-09-17T03:00:00Z",
    "f01Mechanics": {
      "foundation": "F01_EscapeRun",
      "timeLimitSec": 25,
      "lives": 3,
      "streakMultipliers": {
        "1": 1.0,
        "3": 1.5,
        "5": 2.0
      },
      "shieldMessage": "Boundary Shield Activated! Re-trace outer perimeter edges before continuing."
    },
    "visualManipulatives": {
      "sim-grid-explorer": {
        "type": "canvas_2d_grid",
        "description": "Grid canvas highlighting perimeter boundary in red and internal area squares in blue",
        "gridSize": "20px"
      },
      "sim-decomposition-lshape": {
        "type": "svg_polygon_decomposition",
        "description": "L-shaped polygon with dashed divider decomposing into two simple rectangles"
      }
    },
    "vocab": {
      "perimeter": { "hindi": "परिमाप", "phonics": "पेरीमीटर", "def": "किसी बंद आकृति की बाहरी सीमा की कुल लम्बाई" },
      "area": { "hindi": "क्षेत्रफल", "phonics": "एरिया", "def": "किसी बंद समतल आकृति द्वारा घेरे गए तल का विस्तार" },
      "length": { "hindi": "लम्बाई", "phonics": "लेंथ", "def": "किसी आकृति का अधिक लम्बा विस्तार" },
      "breadth": { "hindi": "चौड़ाई", "phonics": "ब्रेड्थ", "def": "किसी आकृति का छोटा या पार्श्व विस्तार" },
      "perpendicular_height": { "hindi": "लम्बवत ऊँचाई", "phonics": "परपेंडिकुलर हाइट", "def": "आधार पर डाला गया 90 डिग्री का सीधा लम्ब" },
      "circumference": { "hindi": "परिधि", "phonics": "सरकमफेरेंस", "def": "वृत्त की बाहरी सीमा की कुल लम्बाई" },
      "radius": { "hindi": "त्रिज्या", "phonics": "रेडियस", "def": "वृत्त के केंद्र से परिधि तक की दूरी" },
      "diameter": { "hindi": "व्यास", "phonics": "डायमीटर", "def": "वृत्त के केंद्र से होकर दोनों सिरों को छूने वाली रेखा (2 × त्रिज्या)" }
    },
    "itemBank": [
      {
        "id": "c7_pa_q1",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["perimeter", "area"],
        "stem": "Which practical activity requires measuring boundary PERIMETER rather than surface area?",
        "options": [
          { "text": "Constructing a wire security fence along the outer border of a farmland", "isCorrect": true },
          { "text": "Spreading organic grass seeds across a community football ground", "isCorrect": false, "m": "Requires calculating two-dimensional surface coverage (area)." },
          { "text": "Polishing granite floor tiles inside an assembly hall", "isCorrect": false, "m": "Interior floor finishing covers surface space, requiring area." },
          { "text": "Applying waterproof paint across a flat rectangular rooftop", "isCorrect": false, "m": "Coating a flat surface requires area calculation rather than boundary path." }
        ],
        "hints": [
          { "tier": "H1", "text": "Differentiate between walking along an edge versus covering a flat face." },
          { "tier": "H2", "text": "Perimeter measures outer border line; area measures flat surface spread." },
          { "tier": "H3", "text": "Fencing outlines the boundary; turfing and tiling fill the interior." },
          { "tier": "H4", "text": "Select the option that only follows outer border line." }
        ]
      },
      {
        "id": "c7_pa_q2",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["perimeter", "length", "breadth"],
        "stem": "A rectangular garden has length 9 m and breadth 5 m. What is its perimeter?",
        "options": [
          { "text": "28 m", "isCorrect": true },
          { "text": "45 m²", "isCorrect": false, "m": "Multiplied length by breadth, finding surface area rather than boundary perimeter." },
          { "text": "14 m", "isCorrect": false, "m": "Added only one length and one breadth, forgetting opposite two sides." },
          { "text": "56 m", "isCorrect": false, "m": "Doubled perimeter formula components twice unnecessarily." }
        ],
        "hints": [
          { "tier": "H1", "text": "A rectangle possesses 4 boundary sides: two lengths and two breadths." },
          { "tier": "H2", "text": "Perimeter formula equals 2 times (length plus breadth)." },
          { "tier": "H3", "text": "Add 9 m and 5 m together, then multiply by 2." },
          { "tier": "H4", "text": "Double the sum of adjacent dimensions." }
        ]
      },
      {
        "id": "c7_pa_q3",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["perimeter"],
        "stem": "If the perimeter of a square game board measures 36 cm, what is the length of each side?",
        "options": [
          { "text": "9 cm", "isCorrect": true },
          { "text": "18 cm", "isCorrect": false, "m": "Divided by two rather than four equal boundary sides of a square." },
          { "text": "6 cm", "isCorrect": false, "m": "Confused perimeter division with square root area calculation." },
          { "text": "144 cm", "isCorrect": false, "m": "Multiplied perimeter by 4 rather than dividing among equal sides." }
        ],
        "hints": [
          { "tier": "H1", "text": "A square has four identical sides." },
          { "tier": "H2", "text": "Perimeter equals 4 times side length." },
          { "tier": "H3", "text": "Divide total boundary measurement by 4." },
          { "tier": "H4", "text": "36 divided by 4 isolates side length." }
        ]
      },
      {
        "id": "c7_pa_q4",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area"],
        "stem": "Which unit correctly quantifies the two-dimensional surface area of a classroom noticeboard?",
        "options": [
          { "text": "cm²", "isCorrect": true },
          { "text": "cm", "isCorrect": false, "m": "Linear unit measuring 1D boundary length or distance, not 2D surface." },
          { "text": "cm³", "isCorrect": false, "m": "Cubic unit quantifying 3D volume capacity, not flat surface." },
          { "text": "kg", "isCorrect": false, "m": "Unit measuring physical mass rather than geometric surface space." }
        ],
        "hints": [
          { "tier": "H1", "text": "Consider how many dimensions are being measured." },
          { "tier": "H2", "text": "Surface area counts square units covering a flat region." },
          { "tier": "H3", "text": "Linear units measure length; square units measure area." },
          { "tier": "H4", "text": "Look for square notation exponent." }
        ]
      },
      {
        "id": "c7_pa_q5",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area"],
        "stem": "Calculate the surface area of a square courtyard with side length 8 m.",
        "options": [
          { "text": "64 m²", "isCorrect": true },
          { "text": "32 m", "isCorrect": false, "m": "Multiplied side by 4, calculating perimeter rather than surface area." },
          { "text": "16 m²", "isCorrect": false, "m": "Multiplied side by 2 rather than squaring side length." },
          { "text": "64 m", "isCorrect": false, "m": "Attached linear length units rather than square area units." }
        ],
        "hints": [
          { "tier": "H1", "text": "Square area equals side multiplied by itself." },
          { "tier": "H2", "text": "Apply formula Area = side * side." },
          { "tier": "H3", "text": "Compute 8 times 8." },
          { "tier": "H4", "text": "Include square metre units in final answer." }
        ]
      },
      {
        "id": "c7_pa_q6",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "length", "breadth"],
        "stem": "A rectangular banner has an area of 96 cm² and breadth 8 cm. What is its length?",
        "options": [
          { "text": "12 cm", "isCorrect": true },
          { "text": "88 cm", "isCorrect": false, "m": "Subtracted breadth from area rather than using division." },
          { "text": "24 cm", "isCorrect": false, "m": "Calculation slip in division of area by breadth." },
          { "text": "768 cm", "isCorrect": false, "m": "Multiplied area by breadth rather than dividing to find missing dimension." }
        ],
        "hints": [
          { "tier": "H1", "text": "Area equals length times breadth." },
          { "tier": "H2", "text": "To isolate length, divide total area by known breadth." },
          { "tier": "H3", "text": "Divide 96 by 8." },
          { "tier": "H4", "text": "Quotient yields length in centimetres." }
        ]
      },
      {
        "id": "c7_pa_q7",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "perpendicular_height"],
        "stem": "A parallelogram has base 8 cm and perpendicular height 5 cm. What is its area?",
        "options": [
          { "text": "40 cm²", "isCorrect": true },
          { "text": "20 cm²", "isCorrect": false, "m": "Applied triangle formula factor of one-half to a parallelogram." },
          { "text": "26 cm", "isCorrect": false, "m": "Calculated perimeter-like sum 2*(8+5) rather than area product." },
          { "text": "13 cm²", "isCorrect": false, "m": "Added base and height rather than multiplying them." }
        ],
        "hints": [
          { "tier": "H1", "text": "Parallelogram area equals base times perpendicular height." },
          { "tier": "H2", "text": "Do not divide by 2 for parallelograms." },
          { "tier": "H3", "text": "Multiply base 8 cm by perpendicular height 5 cm." },
          { "tier": "H4", "text": "Direct product gives total area." }
        ]
      },
      {
        "id": "c7_pa_q8",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "perpendicular_height"],
        "stem": "Find the area of a triangle with base 12 cm and perpendicular altitude 7 cm.",
        "options": [
          { "text": "42 cm²", "isCorrect": true },
          { "text": "84 cm²", "isCorrect": false, "m": "Omitted the half multiplier in triangle area formula." },
          { "text": "19 cm²", "isCorrect": false, "m": "Added base and altitude rather than applying area formula." },
          { "text": "38 cm", "isCorrect": false, "m": "Combined dimensions using perimeter logic with wrong units." }
        ],
        "hints": [
          { "tier": "H1", "text": "Triangles occupy half the area of a enclosing rectangle with same base and height." },
          { "tier": "H2", "text": "Apply triangle formula: Area = (1/2) * base * height." },
          { "tier": "H3", "text": "Multiply 12 by 7, then divide by 2." },
          { "tier": "H4", "text": "Half of 84 gives triangle area." }
        ]
      },
      {
        "id": "c7_pa_q9",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["circumference", "radius"],
        "stem": "Find the circumference of a circular plate of radius 14 cm. (Use \\(\\pi = \\frac{22}{7}\\))",
        "options": [
          { "text": "88 cm", "isCorrect": true },
          { "text": "616 cm²", "isCorrect": false, "m": "Calculated circular surface area pi*r^2 rather than boundary circumference." },
          { "text": "44 cm", "isCorrect": false, "m": "Applied pi*r rather than 2*pi*r, omitting factor of two." },
          { "text": "176 cm", "isCorrect": false, "m": "Used diameter in place of radius with 2*pi multiplier." }
        ],
        "hints": [
          { "tier": "H1", "text": "Circumference represents the boundary perimeter around a circle." },
          { "tier": "H2", "text": "Apply formula C = 2 * pi * r." },
          { "tier": "H3", "text": "Substitute: 2 * (22/7) * 14." },
          { "tier": "H4", "text": "Cancel 7 into 14, then multiply remaining factors." }
        ]
      },
      {
        "id": "c7_pa_q10",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "diameter", "radius"],
        "stem": "What is the surface area of a circular lawn with diameter 14 m? (Use \\(\\pi = \\frac{22}{7}\\))",
        "options": [
          { "text": "154 m²", "isCorrect": true },
          { "text": "616 m²", "isCorrect": false, "m": "Used diameter 14 directly as radius in formula pi*r^2." },
          { "text": "44 m", "isCorrect": false, "m": "Calculated circumference boundary rather than interior surface area." },
          { "text": "308 m²", "isCorrect": false, "m": "Doubled radius or made factor error during cancellation." }
        ],
        "hints": [
          { "tier": "H1", "text": "First determine radius: radius equals half of diameter." },
          { "tier": "H2", "text": "Radius equals 7 m." },
          { "tier": "H3", "text": "Apply Area = pi * r^2: (22/7) * 7 * 7." },
          { "tier": "H4", "text": "Cancel 7 in denominator and multiply 22 by 7." }
        ]
      },
      {
        "id": "c7_pa_q11",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["perimeter", "area"],
        "stem": "A metallic wire shaped as a rectangle of length 40 cm and breadth 22 cm is reshaped into a square. Which shape encloses greater area, and what is the square side?",
        "options": [
          { "text": "Square of side 31 cm encloses greater area (961 cm² vs 880 cm²)", "isCorrect": true },
          { "text": "Rectangle encloses greater area by 81 cm²", "isCorrect": false, "m": "Incorrectly assumed elongated rectangle encloses more area than square of same perimeter." },
          { "text": "Square of side 62 cm encloses greater area", "isCorrect": false, "m": "Divided perimeter by two rather than four sides when finding square side." },
          { "text": "Both shapes enclose exactly equal area because perimeter is conserved", "isCorrect": false, "m": "Conflated constant boundary perimeter with constant surface area." }
        ],
        "hints": [
          { "tier": "H1", "text": "Perimeter remains conserved when wire is rebent." },
          { "tier": "H2", "text": "Compute rectangle perimeter: 2*(40 + 22) = 124 cm." },
          { "tier": "H3", "text": "Square side equals 124 divided by 4." },
          { "tier": "H4", "text": "Compare areas: 31*31 versus 40*22." }
        ]
      },
      {
        "id": "c7_pa_q12",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "perimeter"],
        "stem": "A rectangular garden 90 m long and 75 m broad has an outdoor walking path 5 m wide built around its outside. What is the area of this walking path?",
        "options": [
          { "text": "1750 m²", "isCorrect": true },
          { "text": "825 m²", "isCorrect": false, "m": "Added path width once to each dimension rather than both sides." },
          { "text": "6750 m²", "isCorrect": false, "m": "Calculated inner garden area rather than outer border path." },
          { "text": "1650 m²", "isCorrect": false, "m": "Forgot corner square overlaps when calculating path borders." }
        ],
        "hints": [
          { "tier": "H1", "text": "Outer dimensions increase by twice path width: 5 m on each end." },
          { "tier": "H2", "text": "Outer length equals 90 + 10 = 100 m; outer breadth equals 75 + 10 = 85 m." },
          { "tier": "H3", "text": "Path area equals outer rectangle area minus inner garden area." },
          { "tier": "H4", "text": "Compute 100*85 minus 90*75." }
        ]
      },
      {
        "id": "c7_pa_q13",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-grid-explorer",
        "vocabRefs": ["area", "perimeter"],
        "stem": "A banquet floor measures 15 m in length and 10 m in breadth. Find the total cost of paving ceramic tiles over this floor at Rs 50 per square metre.",
        "options": [
          { "text": "Rs 7,500", "isCorrect": true },
          { "text": "Rs 2,500", "isCorrect": false, "m": "Multiplied perimeter by unit rate rather than surface area." },
          { "text": "Rs 15,000", "isCorrect": false, "m": "Doubled surface area unnecessarily before cost calculation." },
          { "text": "Rs 750", "isCorrect": false, "m": "Division slip by ten when multiplying total square units." }
        ],
        "hints": [
          { "tier": "H1", "text": "Tiling covers floor surface; calculate area first." },
          { "tier": "H2", "text": "Area equals length times breadth: 15 m * 10 m." },
          { "tier": "H3", "text": "Total area equals 150 square metres." },
          { "tier": "H4", "text": "Multiply 150 sq m by cost rate Rs 50." }
        ]
      },
      {
        "id": "c7_pa_q14",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-decomposition-lshape",
        "vocabRefs": ["area", "perimeter"],
        "stem": "An L-shaped lawn can be decomposed into two non-overlapping rectangles: Rectangle A measuring 6 m by 3 m, and Rectangle B measuring 4 m by 2 m. What is the total area of the lawn?",
        "options": [
          { "text": "26 m²", "isCorrect": true },
          { "text": "50 m²", "isCorrect": false, "m": "Multiplied outer maximum bounds 10 by 5, including missing corner cut-out." },
          { "text": "30 m", "isCorrect": false, "m": "Calculated boundary perimeter rather than composite region area." },
          { "text": "20 m²", "isCorrect": false, "m": "Omitted one rectangular component during summation." }
        ],
        "hints": [
          { "tier": "H1", "text": "Composite area equals sum of individual non-overlapping component areas." },
          { "tier": "H2", "text": "Calculate area of Rectangle A: 6 m * 3 m." },
          { "tier": "H3", "text": "Calculate area of Rectangle B: 4 m * 2 m." },
          { "tier": "H4", "text": "Add 18 sq m and 8 sq m together." }
        ]
      }
    ]
  },
  "c8_rational_linear": {
    "chapterId": "c8_rational_linear",
    "title": "Rational Numbers & Linear Equations (परिमेय संख्याएँ और रैखिक समीकरण)",
    "grade": 8,
    "version": 4,
    "updatedAt": "2026-09-17T03:00:00Z",
    "f01Mechanics": {
      "foundation": "F01_EscapeRun",
      "timeLimitSec": 25,
      "lives": 3,
      "streakMultipliers": {
        "1": 1.0,
        "3": 1.5,
        "5": 2.0
      },
      "shieldMessage": "Cognitive Shield Recharged! Review inverse operations before next hurdle."
    },
    "visualManipulatives": {
      "sim-balance-scale": {
        "type": "svg_balance_scale",
        "description": "Two-pan balance scale tilting according to mass imbalance, reaching equilibrium when solved",
        "pivotPoint": { "x": 150, "y": 80 }
      },
      "sim-numberline-density": {
        "type": "canvas_interactive_numberline",
        "description": "Zoomable number line displaying rational density and mirror placement for inverses",
        "domain": [-2, 2]
      }
    },
    "vocab": {
      "rational_number": { "hindi": "परिमेय संख्या", "phonics": "रैशनल नंबर", "def": "वह संख्या जिसे p/q के रूप में लिखा जा सके, जहाँ p, q पूर्णांक हैं और q ≠ 0" },
      "linear_equation": { "hindi": "रैखिक समीकरण", "phonics": "लीनियर इक्वेशन", "def": "एक चर वाला ऐसा समीकरण जिसमें चर की अधिकतम घात 1 हो" },
      "variable": { "hindi": "चर", "phonics": "वेरिएबल", "def": "अज्ञात राशि जिसका मान परिस्थिति अनुसार बदलता है (उदा. x, y)" },
      "constant": { "hindi": "अचर", "phonics": "कांस्टेंट", "def": "निश्चित संख्यात्मक मान जो कभी नहीं बदलता" },
      "equality": { "hindi": "समता / समानता", "phonics": "इक्वलिटी", "def": "बराबर चिह्न (=) जो दर्शाता है कि बायाँ पक्ष और दायाँ पक्ष तुल्य हैं" },
      "lhs": { "hindi": "बायाँ पक्ष", "phonics": "एल.एच.एस.", "def": "बराबर चिह्न के बाईं ओर स्थित व्यंजक" },
      "rhs": { "hindi": "दायाँ पक्ष", "phonics": "आर.एच.एस.", "def": "बराबर चिह्न के दाईं ओर स्थित व्यंजक" },
      "transposition": { "hindi": "पक्षांतरण", "phonics": "ट्रांसपोजिशन", "def": "किसी पद को बराबर चिह्न के एक तरफ से दूसरी तरफ ले जाना (चिह्न बदलकर)" },
      "additive_inverse": { "hindi": "योज्य प्रतिलोम", "phonics": "एडिटिव इन्वर्स", "def": "वह संख्या जिसे जोड़ने पर योग शून्य प्राप्त हो" },
      "multiplicative_inverse": { "hindi": "गुणात्मक प्रतिलोम", "phonics": "मल्टिप्लिकेटिव इन्वर्स", "def": "वह संख्या जिससे गुणा करने पर गुणनफल 1 प्राप्त हो (व्युत्क्रम)" },
      "cross_multiplication": { "hindi": "वज्र-गुणन", "phonics": "क्रॉस मल्टीप्लिकेशन", "def": "भिन्नात्मक समीकरणों में तिर्यक गुणा करके हर हटाने की विधि" }
    },
    "itemBank": [
      {
        "id": "c8_rnle_q1",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-numberline-density",
        "vocabRefs": ["rational_number"],
        "stem": "Which condition must hold for any number written in the form \\(\\frac{p}{q}\\) to qualify as a rational number?",
        "options": [
          { "text": "\\(p, q\\) are integers and \\(q \\neq 0\\)", "isCorrect": true },
          { "text": "\\(p, q\\) are whole numbers and \\(q = 0\\)", "isCorrect": false, "m": "Division by zero represents an undefined mathematical operation." },
          { "text": "\\(p\\) must strictly be positive", "isCorrect": false, "m": "Rational numbers encompass negative integers as well as positive integers." },
          { "text": "\\(p\\) must be divisible by \\(q\\) without remainder", "isCorrect": false, "m": "Restricts rational numbers to integers, excluding non-terminating or proper rational values." }
        ],
        "hints": [
          { "tier": "H1", "text": "Recall formal definition of rational numbers." },
          { "tier": "H2", "text": "Both numerator and denominator must belong to integer set." },
          { "tier": "H3", "text": "Check condition on bottom number." },
          { "tier": "H4", "text": "Denominator cannot equal zero." }
        ]
      },
      {
        "id": "c8_rnle_q2",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-numberline-density",
        "vocabRefs": ["multiplicative_inverse", "additive_inverse"],
        "stem": "What is the multiplicative inverse (reciprocal) of \\(-\\frac{13}{19}\\)?",
        "options": [
          { "text": "\\(-\\frac{19}{13}\\)", "isCorrect": true },
          { "text": "\\(\\frac{13}{19}\\)", "isCorrect": false, "m": "Found additive inverse (negated sign) rather than flipping fraction numerator and denominator." },
          { "text": "\\(\\frac{19}{13}\\)", "isCorrect": false, "m": "Flipped fraction but omitted the essential negative sign." },
          { "text": "\\(-\\frac{1}{13}\\)", "isCorrect": false, "m": "Replaced numerator with one without preserving denominator magnitude." }
        ],
        "hints": [
          { "tier": "H1", "text": "Multiplying a number by its multiplicative inverse must produce 1." },
          { "tier": "H2", "text": "Reciprocal inverts numerator and denominator while preserving sign." },
          { "tier": "H3", "text": "Swap 13 and 19." },
          { "tier": "H4", "text": "Retain negative sign: -19/13." }
        ]
      },
      {
        "id": "c8_rnle_q3",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "variable"],
        "stem": "Which algebraic statement represents a linear equation in one variable?",
        "options": [
          { "text": "\\(3x - 5 = 16\\)", "isCorrect": true },
          { "text": "\\(3x - 5\\)", "isCorrect": false, "m": "Represents an algebraic expression; lacks equality symbol linking two sides." },
          { "text": "\\(x^2 + 4 = 20\\)", "isCorrect": false, "m": "Contains quadratic variable exponent 2; linear equations require exponent 1." },
          { "text": "\\(2x + 3y = 12\\)", "isCorrect": false, "m": "Contains two distinct variables x and y rather than a single variable." }
        ],
        "hints": [
          { "tier": "H1", "text": "Look for three features: single variable letter, exponent 1, and equality symbol." },
          { "tier": "H2", "text": "Expressions lack an equals sign; quadratic equations have squared variables." },
          { "tier": "H3", "text": "Verify single variable with power 1 on both sides." },
          { "tier": "H4", "text": "3x - 5 = 16 satisfies all three requirements." }
        ]
      },
      {
        "id": "c8_rnle_q4",
        "tier": 1,
        "tierName": "Warm-up",
        "section": "#section-warmup",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["equality", "transposition"],
        "stem": "To solve the balance equation \\(x - 8 = 15\\), which operation should be applied to both sides?",
        "options": [
          { "text": "Add 8 to both sides", "isCorrect": true },
          { "text": "Subtract 8 from both sides", "isCorrect": false, "m": "Subtracting 8 doubles negative offset on left pan; addition cancels subtraction." },
          { "text": "Multiply both sides by 8", "isCorrect": false, "m": "Multiplication inverts division rather than subtraction." },
          { "text": "Divide both sides by 15", "isCorrect": false, "m": "Target operations isolate variable by eliminating attached term on variable side." }
        ],
        "hints": [
          { "tier": "H1", "text": "Identify the operation currently attached to variable x." },
          { "tier": "H2", "text": "Variable has 8 subtracted from it." },
          { "tier": "H3", "text": "Inverse operation of subtraction is addition." },
          { "tier": "H4", "text": "Apply addition of 8 across both pans to preserve balance." }
        ]
      },
      {
        "id": "c8_rnle_q5",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-numberline-density",
        "vocabRefs": ["rational_number"],
        "stem": "Evaluate using distributivity: \\((-\\frac{3}{7}) \\times \\frac{2}{5} + (-\\frac{3}{7}) \\times \\frac{3}{5}\\).",
        "options": [
          { "text": "\\(-\\frac{3}{7}\\)", "isCorrect": true },
          { "text": "\\(\\frac{3}{7}\\)", "isCorrect": false, "m": "Sign error when multiplying negative common factor." },
          { "text": "\\(-\\frac{6}{35}\\)", "isCorrect": false, "m": "Calculated first product only, omitting second term." },
          { "text": "\\(-\\frac{9}{35}\\)", "isCorrect": false, "m": "Calculated second product only, omitting first term." }
        ],
        "hints": [
          { "tier": "H1", "text": "Notice the common factor present in both product terms." },
          { "tier": "H2", "text": "Factor out -3/7 using distributive law: a*b + a*c = a*(b + c)." },
          { "tier": "H3", "text": "Combine bracketed fractions: 2/5 + 3/5 = 5/5 = 1." },
          { "tier": "H4", "text": "Multiply common factor -3/7 by 1." }
        ]
      },
      {
        "id": "c8_rnle_q6",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-numberline-density",
        "vocabRefs": ["rational_number"],
        "stem": "Which rational number lies between \\(\\frac{1}{4}\\) and \\(\\frac{1}{2}\\)?",
        "options": [
          { "text": "\\(\\frac{3}{8}\\)", "isCorrect": true },
          { "text": "\\(\\frac{1}{8}\\)", "isCorrect": false, "m": "Smaller than 1/4 (2/8); lies outside the specified interval." },
          { "text": "\\(\\frac{5}{8}\\)", "isCorrect": false, "m": "Larger than 1/2 (4/8); exceeds upper boundary." },
          { "text": "\\(\\frac{2}{3}\\)", "isCorrect": false, "m": "Exceeds 1/2; 2/3 equals approximately 0.67." }
        ],
        "hints": [
          { "tier": "H1", "text": "Convert both boundaries to common denominator 8." },
          { "tier": "H2", "text": "1/4 equals 2/8; 1/2 equals 4/8." },
          { "tier": "H3", "text": "Look for a numerator lying strictly between 2 and 4." },
          { "tier": "H4", "text": "Fraction with numerator 3 over denominator 8 fits." }
        ]
      },
      {
        "id": "c8_rnle_q7",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["variable", "transposition", "rhs"],
        "stem": "Solve for \\(y\\) in the linear equation: \\(2y + \\frac{5}{2} = \\frac{37}{2}\\).",
        "options": [
          { "text": "\\(y = 8\\)", "isCorrect": true },
          { "text": "\\(y = 16\\)", "isCorrect": false, "m": "Subtracted constant term correctly but omitted final division by coefficient 2." },
          { "text": "\\(y = 21\\)", "isCorrect": false, "m": "Added 5/2 to RHS rather than subtracting during transposition." },
          { "text": "\\(y = 4\\)", "isCorrect": false, "m": "Divided by 4 rather than variable coefficient 2." }
        ],
        "hints": [
          { "tier": "H1", "text": "Transpose constant fraction 5/2 to Right Hand Side." },
          { "tier": "H2", "text": "Subtract: 37/2 minus 5/2 gives 32/2 = 16." },
          { "tier": "H3", "text": "Equation simplifies to 2y = 16." },
          { "tier": "H4", "text": "Divide 16 by coefficient 2 to isolate y." }
        ]
      },
      {
        "id": "c8_rnle_q8",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["transposition", "variable", "lhs", "rhs"],
        "stem": "Solve the equation with variables on both sides: \\(5x + 9 = 5 + 3x\\).",
        "options": [
          { "text": "\\(x = -2\\)", "isCorrect": true },
          { "text": "\\(x = 2\\)", "isCorrect": false, "m": "Omitted negative sign when subtracting 9 from 5 on RHS." },
          { "text": "\\(x = -7\\)", "isCorrect": false, "m": "Transposed variable term without reversing operational sign." },
          { "text": "\\(x = 7\\)", "isCorrect": false, "m": "Combined like terms incorrectly across both sides." }
        ],
        "hints": [
          { "tier": "H1", "text": "Group variable terms on LHS and numerical constants on RHS." },
          { "tier": "H2", "text": "Transpose 3x left: 5x - 3x = 2x." },
          { "tier": "H3", "text": "Transpose 9 right: 5 - 9 = -4." },
          { "tier": "H4", "text": "Divide -4 by 2 to find x." }
        ]
      },
      {
        "id": "c8_rnle_q9",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "transposition"],
        "stem": "Solve the equation containing brackets: \\(3(t - 3) = 5(2t + 1)\\).",
        "options": [
          { "text": "\\(t = -2\\)", "isCorrect": true },
          { "text": "\\(t = 2\\)", "isCorrect": false, "m": "Made sign error when dividing negative constant by negative coefficient." },
          { "text": "\\(t = -1\\)", "isCorrect": false, "m": "Failed to multiply bracketed constant terms by outer factor." },
          { "text": "\\(t = -14\\)", "isCorrect": false, "m": "Combined variable coefficients without division." }
        ],
        "hints": [
          { "tier": "H1", "text": "Apply distributive law across both sets of parentheses." },
          { "tier": "H2", "text": "Expand: 3t - 9 = 10t + 5." },
          { "tier": "H3", "text": "Transpose: 3t - 10t = 5 + 9, giving -7t = 14." },
          { "tier": "H4", "text": "Divide 14 by -7 to obtain t." }
        ]
      },
      {
        "id": "c8_rnle_q10",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["cross_multiplication", "transposition"],
        "stem": "Solve the fractional equation: \\(\\frac{x - 5}{3} = \\frac{x - 3}{5}\\).",
        "options": [
          { "text": "\\(x = 8\\)", "isCorrect": true },
          { "text": "\\(x = 4\\)", "isCorrect": false, "m": "Transposed constant terms across equality with wrong sign." },
          { "text": "\\(x = -8\\)", "isCorrect": false, "m": "Sign error when grouping linear terms on one side." },
          { "text": "\\(x = 16\\)", "isCorrect": false, "m": "Cross-multiplied denominators without distributing across numerators." }
        ],
        "hints": [
          { "tier": "H1", "text": "Cross-multiply numerators and denominators across equals sign." },
          { "tier": "H2", "text": "Set up equation: 5*(x - 5) = 3*(x - 3)." },
          { "tier": "H3", "text": "Expand brackets: 5x - 25 = 3x - 9." },
          { "tier": "H4", "text": "Transpose: 5x - 3x = -9 + 25, so 2x = 16." }
        ]
      },
      {
        "id": "c8_rnle_q11",
        "tier": 2,
        "tierName": "Deep Dive",
        "section": "#section-deep_dive",
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "variable"],
        "stem": "The sum of two numbers is 95. If one number exceeds the other by 15, what is the smaller number?",
        "options": [
          { "text": "40", "isCorrect": true },
          { "text": "55", "isCorrect": false, "m": "Identified the larger number (x + 15) rather than requested smaller number." },
          { "text": "35", "isCorrect": false, "m": "Arithmetic slip when subtracting 15 from 95." },
          { "text": "80", "isCorrect": false, "m": "Subtracted difference without dividing by two across both unknown terms." }
        ],
        "hints": [
          { "tier": "H1", "text": "Let smaller number be x; then larger number represents x + 15." },
          { "tier": "H2", "text": "Set up linear equation: x + (x + 15) = 95." },
          { "tier": "H3", "text": "Combine terms: 2x + 15 = 95, so 2x = 80." },
          { "tier": "H4", "text": "Divide 80 by 2 to determine smaller number." }
        ]
      },
      {
        "id": "c8_rnle_q12",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-numberline-density",
        "vocabRefs": ["rational_number", "multiplicative_inverse"],
        "stem": "The product of two rational numbers is \\(-\\frac{16}{9}\\). If one of the numbers is \\(-\\frac{4}{3}\\), find the other rational number.",
        "options": [
          { "text": "\\(\\frac{4}{3}\\)", "isCorrect": true },
          { "text": "\\(-\\frac{4}{3}\\)", "isCorrect": false, "m": "Retained negative sign despite dividing negative product by negative factor." },
          { "text": "\\(\\frac{64}{27}\\)", "isCorrect": false, "m": "Multiplied numbers together rather than dividing product by known factor." },
          { "text": "\\(\\frac{3}{4}\\)", "isCorrect": false, "m": "Inverted final quotient fraction." }
        ],
        "hints": [
          { "tier": "H1", "text": "To find missing factor, divide product by given factor." },
          { "tier": "H2", "text": "Division by fraction requires multiplying by its reciprocal." },
          { "tier": "H3", "text": "Set up: (-16/9) divided by (-4/3) = (-16/9) * (-3/4)." },
          { "tier": "H4", "text": "Negative times negative yields positive; cancel factors." }
        ]
      },
      {
        "id": "c8_rnle_q13",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "variable"],
        "stem": "The perimeter of a rectangular swimming pool is 154 m. Its length is 2 m more than twice its breadth. What are the length and breadth?",
        "options": [
          { "text": "Length = 52 m, Breadth = 25 m", "isCorrect": true },
          { "text": "Length = 50 m, Breadth = 27 m", "isCorrect": false, "m": "Failed to model length as twice breadth plus two." },
          { "text": "Length = 76 m, Breadth = 38 m", "isCorrect": false, "m": "Equated half perimeter directly to length rather than sum of dimensions." },
          { "text": "Length = 54 m, Breadth = 23 m", "isCorrect": false, "m": "Calculation slip when solving 6x + 4 = 154." }
        ],
        "hints": [
          { "tier": "H1", "text": "Let breadth be b; then length represents 2b + 2." },
          { "tier": "H2", "text": "Perimeter formula: 2 * (length + breadth) = 154." },
          { "tier": "H3", "text": "Substitute: 2 * (2b + 2 + b) = 2 * (3b + 2) = 6b + 4 = 154." },
          { "tier": "H4", "text": "6b = 150, so breadth b = 25 m; length = 2*(25) + 2." }
        ]
      },
      {
        "id": "c8_rnle_q14",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "variable"],
        "stem": "The present ages of Sahil and his mother are in the ratio 1:3. Five years later, the sum of their ages will be 66 years. What is Sahil's present age?",
        "options": [
          { "text": "14 years", "isCorrect": true },
          { "text": "42 years", "isCorrect": false, "m": "Identified mother's present age rather than Sahil's present age." },
          { "text": "19 years", "isCorrect": false, "m": "Calculated Sahil's age after 5 years rather than his present age." },
          { "text": "16 years", "isCorrect": false, "m": "Added 5 years only once rather than for both individuals." }
        ],
        "hints": [
          { "tier": "H1", "text": "Let Sahil's age be x and mother's age be 3x." },
          { "tier": "H2", "text": "In 5 years, their ages become (x + 5) and (3x + 5)." },
          { "tier": "H3", "text": "Sum of future ages: (x + 5) + (3x + 5) = 4x + 10 = 66." },
          { "tier": "H4", "text": "4x = 56, so x = 14 gives Sahil's present age." }
        ]
      },
      {
        "id": "c8_rnle_q15",
        "tier": 3,
        "tierName": "Boss Challenge",
        "section": "#section-boss",
        "bossChallenge": true,
        "simKey": "sim-balance-scale",
        "vocabRefs": ["linear_equation", "variable"],
        "stem": "Deveshi has total cash of Rs 590 as currency notes in denominations of Rs 50, Rs 20, and Rs 10. The ratio of Rs 50 notes to Rs 20 notes is 3:5. If she has 25 notes in total, how many Rs 50 notes does she have?",
        "options": [
          { "text": "6", "isCorrect": true },
          { "text": "10", "isCorrect": false, "m": "Identified count of Rs 20 notes (5x) rather than Rs 50 notes (3x)." },
          { "text": "9", "isCorrect": false, "m": "Identified count of Rs 10 notes rather than Rs 50 notes." },
          { "text": "15", "isCorrect": false, "m": "Assumed notes divided equally without factoring denomination values." }
        ],
        "hints": [
          { "tier": "H1", "text": "Let count of Rs 50 notes be 3x and Rs 20 notes be 5x." },
          { "tier": "H2", "text": "Total notes = 25, so Rs 10 notes count equals 25 - (3x + 5x) = 25 - 8x." },
          { "tier": "H3", "text": "Total money equation: 50*(3x) + 20*(5x) + 10*(25 - 8x) = 590." },
          { "tier": "H4", "text": "150x + 100x + 250 - 80x = 590; 170x = 340, so x = 2; Rs 50 count = 3*(2)." }
        ]
      }
    ]
  }
};

const ALIASES = {
  "math6-fractions": "c6_fractions",
  "math7-perimeter-area": "c7_perimeter_area",
  "math8-rational-numbers": "c8_rational_linear",
  "math8-linear-equations": "c8_rational_linear"
};

export default async function (req, res) {
  try {
    const { chapter, grade, version } = req.query || {};

    // 1. Specific chapter query
    if (chapter) {
      const resolvedId = ALIASES[chapter] || chapter;
      const match = DELTA_REGISTRY[resolvedId];
      if (!match) {
        return res.status(404).json({
          error: "chapter_not_found",
          requested: chapter,
          available: Object.keys(DELTA_REGISTRY)
        });
      }

      // Bandwidth optimization: if client already has this version, send lightweight upToDate packet
      const clientVer = parseInt(version, 10);
      if (!isNaN(clientVer) && clientVer === match.version) {
        return res.json({
          chapterId: match.chapterId,
          version: match.version,
          upToDate: true,
          updatedAt: match.updatedAt
        });
      }

      return res.json({
        chapterId: match.chapterId,
        title: match.title,
        grade: match.grade,
        version: match.version,
        updatedAt: match.updatedAt,
        upToDate: false,
        f01Mechanics: match.f01Mechanics,
        visualManipulatives: match.visualManipulatives,
        vocab: match.vocab,
        itemBank: match.itemBank
      });
    }

    // 2. Filter by Grade (6, 7, 8)
    if (grade) {
      const targetGrade = parseInt(grade, 10);
      const filtered = Object.values(DELTA_REGISTRY).filter(c => c.grade === targetGrade);
      if (filtered.length === 0) {
        return res.status(404).json({
          error: "grade_not_found",
          requestedGrade: targetGrade,
          availableGrades: [6, 7, 8]
        });
      }

      // Version caching check across grade chapters
      const clientVer = parseInt(version, 10);
      if (!isNaN(clientVer) && filtered.every(c => c.version === clientVer)) {
        return res.json({
          grade: targetGrade,
          version: clientVer,
          upToDate: true,
          updatedAt: filtered[0].updatedAt
        });
      }

      return res.json({
        grade: targetGrade,
        count: filtered.length,
        version: filtered[0].version,
        chapters: filtered
      });
    }

    // 3. Manifest Overview (No query parameters)
    const manifest = Object.values(DELTA_REGISTRY).map(c => ({
      chapterId: c.chapterId,
      title: c.title,
      grade: c.grade,
      version: c.version,
      updatedAt: c.updatedAt,
      itemCount: c.itemBank.length,
      hasVisualSims: Object.keys(c.visualManipulatives || {}).length > 0,
      hasF01Boss: Boolean(c.f01Mechanics)
    }));

    return res.json({
      ecosystem: "Aasha-AIOS",
      targetGrades: [6, 7, 8],
      totalChapters: manifest.length,
      totalQuestions: manifest.reduce((acc, c) => acc + c.itemCount, 0),
      chapters: manifest
    });
  } catch (err) {
    return res.status(500).json({ error: "server_error", message: err.message });
  }
}
