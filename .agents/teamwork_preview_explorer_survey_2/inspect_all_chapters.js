const fs = require('fs');
const path = require('path');

const dirs = [
  'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters',
  'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/standalone_chapters'
];

dirs.forEach(dir => {
  if (!fs.existsSync(dir)) return;
  console.log(`\n=== Directory: ${dir} ===`);
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.html'));
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const content = fs.readFileSync(filePath, 'utf8');
    const sizeMB = (content.length / 1024 / 1024).toFixed(2);
    
    // Check KaTeX fonts / JSXGraph / PhET / Audio
    const hasKaTeX = content.includes('KaTeX') || content.includes('katex');
    const hasJSXGraph = content.includes('JSXGraph') || content.includes('JXG');
    const hasPhET = content.includes('PHET_SIMS') || content.includes('phet.colorado.edu');
    const hasAudio = content.includes('AudioContext') || content.includes('webkitAudioContext');
    const hasBase64Font = content.includes('font/woff2;base64') || content.includes('font/woff;base64');
    const hasWordDialog = content.includes('wordDialog');
    const hasWM = content.includes('window.WM') || content.includes('var WM');
    
    console.log(`${file.padEnd(55)} | ${sizeMB.padStart(6)} MB | KaTeX:${hasKaTeX} | JSXGraph:${hasJSXGraph} | PhET:${hasPhET} | WOFF2:${hasBase64Font} | WM:${hasWM} | Dialog:${hasWordDialog}`);
  });
});
