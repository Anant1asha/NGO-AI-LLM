const fs = require('fs');

const dictPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/experience_registry/aasha_dictionary_db.json';
const data = JSON.parse(fs.readFileSync(dictPath, 'utf8'));

console.log('Total dictionary entries:', Object.keys(data).length);
const sampleKeys = Object.keys(data).slice(0, 15);
console.log('Sample entries:');
sampleKeys.forEach(k => {
  console.log(`  "${k}":`, JSON.stringify(data[k]));
});

// Check if format is [सरल अर्थ] ([देवनागरी उच्चारण]) or object
let stringFormatCount = 0;
let objectFormatCount = 0;
let hasHindiMeaning = 0;
let hasPhonetic = 0;

for (const [k, v] of Object.entries(data)) {
  if (typeof v === 'string') {
    stringFormatCount++;
  } else if (typeof v === 'object' && v !== null) {
    objectFormatCount++;
    if (v.hi || v.meaning || v.hindi) hasHindiMeaning++;
    if (v.pron || v.phonetic || v.devanagari) hasPhonetic++;
  }
}

console.log(`Format breakdown: string=${stringFormatCount}, object=${objectFormatCount}`);
console.log(`If object: hasHindiMeaning=${hasHindiMeaning}, hasPhonetic=${hasPhonetic}`);

// Check specific Rational Numbers terms
const terms = [
  'rational', 'number', 'numerator', 'denominator', 'positive', 'negative',
  'fraction', 'integer', 'standard', 'form', 'additive', 'multiplicative',
  'inverse', 'density', 'closure', 'commutative', 'associative', 'distributive'
];

console.log('\nChecking Class 8 Rational Numbers key terms:');
terms.forEach(t => {
  console.log(`  "${t}":`, data[t] ? JSON.stringify(data[t]) : 'MISSING');
});
