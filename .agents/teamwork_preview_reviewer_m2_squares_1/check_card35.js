const fs = require('fs');
const path = require('path');

const targetPath = path.resolve('C:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html');
const content = fs.readFileSync(targetPath, 'utf8');

const puz02Idx = content.indexOf('id="boss_08_puz02"');
console.log('Snippet around boss_08_puz02 and after:');
console.log(content.substring(puz02Idx, puz02Idx + 2000));
