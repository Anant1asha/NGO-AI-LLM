const fs = require('fs');

const p = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/Polynomials_JSXGraph_Inlined_Enhanced_v6.html';
const content = fs.readFileSync(p, 'utf8');

const lines = content.split('\n');
console.log('Lines count:', lines.length);

// Look for lines mentioning katex, jsxgraph, fonts
lines.forEach((l, idx) => {
  if (l.toLowerCase().includes('katex') || l.toLowerCase().includes('font') || l.toLowerCase().includes('jsxgraph') || l.toLowerCase().includes('jxg')) {
    console.log(`Line ${idx}: ${l.substring(0, 120)}`);
  }
});
