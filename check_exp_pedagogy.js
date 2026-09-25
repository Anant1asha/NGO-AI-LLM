const fs = require('fs');
const content = fs.readFileSync('Aasha-AI/chapters/ExponentsPowers_Class8_MDS.html', 'utf8');

function extractJsonVar(content, varName) {
  const regex = new RegExp(`var\\s+${varName}\\s*=\\s*([\\[\\{][\\s\\S]*?);\\s*(?:var|function|App|$)`);
  const match = content.match(regex);
  if (match) {
    try {
      const fn = new Function(`return ${match[1]};`);
      return fn();
    } catch (e) {
      return null;
    }
  }
  return null;
}

const nodes = extractJsonVar(content, 'NODES');
console.log("Total Nodes extracted:", nodes ? nodes.length : "null");
if (nodes) {
  nodes.forEach((n, idx) => {
    console.log(`\nNode ${idx + 1}: ${n.title}`);
    (n.steps || []).forEach((s, sIdx) => {
      console.log(`  Step ${sIdx + 1} (${s.t}): ${s.title || (s.h ? s.h.replace(/<[^>]+>/g, '') : '')}`);
    });
  });
}