const fs = require('fs');
const path = require('path');

const targetPath = path.resolve('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html');
const content = fs.readFileSync(targetPath, 'utf8');

// Find all elements with class quiz-card
const quizCardRegex = /<div[^>]*class=["'][^"']*quiz-card[^"']*["'][^>]*>/gi;
let match;
const cards = [];
while ((match = quizCardRegex.exec(content)) !== null) {
  cards.push({
    index: match.index,
    tag: match[0],
    snippet: content.substring(match.index, match.index + 300)
  });
}

console.log(`Found ${cards.length} quiz-card tags:`);
cards.forEach((c, i) => {
  console.log(`Card ${i + 1}: ${c.tag}`);
});
