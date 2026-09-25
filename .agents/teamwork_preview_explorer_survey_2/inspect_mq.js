const fs = require('fs');

const p = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html';
const content = fs.readFileSync(p, 'utf8');

const styleMatch = content.match(/<style\b[^>]*>([\s\S]*?)<\/style>/i);
const css = styleMatch ? styleMatch[1] : '';

// Find media queries
const mqRegex = /@media[^{]+\{[\s\S]+?\}(?:\s*\})/gi;
console.log('=== FULL MEDIA QUERIES ===');
let match;
while ((match = mqRegex.exec(css)) !== null) {
  console.log(match[0]);
  console.log('----------------------------------------------------');
}

// Find bottom bar and navigation rules
console.log('=== BOTTOM BAR & NAVIGATION RULES ===');
const navRegex = /(?:#bottomBar|\.nav-bar|\.bottom-nav|footer|\.nav)[^{]*\{[^}]+\}/gi;
while ((match = navRegex.exec(css)) !== null) {
  console.log(match[0]);
}

// Find dialog rules
console.log('=== DIALOG & MODAL RULES ===');
const dlgRegex = /(?:#wordDialog|\.modal|\.dialog|dialog)[^{]*\{[^}]+\}/gi;
while ((match = dlgRegex.exec(css)) !== null) {
  console.log(match[0]);
}
