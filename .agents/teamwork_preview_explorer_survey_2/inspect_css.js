const fs = require('fs');

const p = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html';
const content = fs.readFileSync(p, 'utf8');

// Extract CSS rules for screen, concept-def, sim-canvas, preset-bar, nav-bar, bottomBar, etc.
const styleMatch = content.match(/<style\b[^>]*>([\s\S]*?)<\/style>/i);
const css = styleMatch ? styleMatch[1] : '';

console.log('=== CSS INSPECTION ===');
const cssSelectors = [
  '.screen',
  '.concept-def',
  '.sim-canvas',
  '.preset-bar',
  '.bottom-nav',
  '#bottomBar',
  '.nav-bar',
  '#wordDialog',
  '.word',
  '.math-var'
];

cssSelectors.forEach(sel => {
  const regex = new RegExp(`(${sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^{]*\\{[^}]+\\})`, 'gi');
  let m;
  console.log(`\n--- Matches for selector "${sel}": ---`);
  while ((m = regex.exec(css)) !== null) {
    console.log(m[1].replace(/\s+/g, ' '));
  }
});

// Look for media queries in CSS
console.log('\n=== MEDIA QUERIES IN CSS ===');
const mqRegex = /@media[^{]+\{([\s\S]+?\}(?:\s*\})?)/gi;
let mqMatch;
while ((mqMatch = mqRegex.exec(css)) !== null) {
  console.log(mqMatch[0].substring(0, 200).replace(/\s+/g, ' ') + '...');
}
