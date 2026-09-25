const fs = require('fs');

const fractionsPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html';
const content = fs.readFileSync(fractionsPath, 'utf8');

const scriptRegex = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
let match;
let sIndex = 0;
while ((match = scriptRegex.exec(content)) !== null) {
  const body = match[2];
  if (body.length > 100000) {
    console.log(`Script ${sIndex} is HUGE: ${body.length} chars`);
    console.log('First 500 chars:\n', body.substring(0, 500));
    console.log('Last 500 chars:\n', body.substring(body.length - 500));

    // Let's find large variables or strings
    const lines = body.split('\n');
    console.log(`Total lines in Script ${sIndex}: ${lines.length}`);
    const largeLines = lines.filter(l => l.length > 5000);
    console.log(`Number of lines > 5000 chars: ${largeLines.length}`);
    largeLines.slice(0, 10).forEach((l, idx) => {
      console.log(`Large line ${idx}: length=${l.length}, head=${l.substring(0, 100)}`);
    });
  }
  sIndex++;
}
