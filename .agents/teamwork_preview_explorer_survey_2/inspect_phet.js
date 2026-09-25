const fs = require('fs');

const fractionsPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html';
const content = fs.readFileSync(fractionsPath, 'utf8');

// Find where PHET_SIMS or simulations are defined and used
const phetIndex = content.indexOf('var PHET_SIMS');
if (phetIndex !== -1) {
  console.log('PHET_SIMS definition context:');
  console.log(content.substring(phetIndex - 200, phetIndex + 300));
}

// Search for how PHET_SIMS is referenced
const phetMatches = content.match(/PHET_SIMS[^\n;]*/g) || [];
console.log('PHET_SIMS references:', phetMatches);

// Let's also check what simulations exist
const simKeys = [];
const keyRegex = /var PHET_SIMS\s*=\s*\{([^:]+):/g;
let kMatch = keyRegex.exec(content);
if (kMatch) {
  console.log('Sim key found:', kMatch[1]);
}

// Let's decode the first 200 chars of base64
const b64Match = content.match(/atobDecode\(["']([A-Za-z0-9+/=]+)["']\)/);
if (b64Match) {
  const b64 = b64Match[1].substring(0, 200);
  console.log('Decoded start of base64:');
  console.log(Buffer.from(b64, 'base64').toString('utf8'));
}
