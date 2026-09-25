const fs = require('fs');
const path = require('path');

const fractionsPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/Fractions_Gamified_v5_(2)_Enhanced_v6.html';
const rationalPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_Gamified_v5_Enhanced_v6.html';
const rationalAdPath = 'c:/Users/admin/Downloads/NGO AI LLM/Aasha-AI/chapters/RationalNumbers_Class8_AD_Gamified_v5_Enhanced_v6.html';

function analyzeFile(filePath, name) {
  console.log(`\n================== ${name} ==================`);
  if (!fs.existsSync(filePath)) {
    console.log(`File not found: ${filePath}`);
    return;
  }
  const stats = fs.statSync(filePath);
  console.log(`File size: ${stats.size} bytes (${(stats.size / 1024 / 1024).toFixed(2)} MB)`);
  const content = fs.readFileSync(filePath, 'utf8');

  // Check KaTeX fonts / data URIs
  const dataUris = content.match(/data:[^;]+;base64,[A-Za-z0-9+/=]+/g) || [];
  console.log(`Data URI count: ${dataUris.length}`);
  let totalDataUriBytes = 0;
  dataUris.forEach(uri => totalDataUriBytes += uri.length);
  console.log(`Total data URI size: ${totalDataUriBytes} bytes (${(totalDataUriBytes / 1024 / 1024).toFixed(2)} MB)`);

  // Check external URLs / CDN
  const urls = content.match(/https?:\/\/[^\s"'\<\>]+/g) || [];
  console.log(`External URL references count: ${urls.length}`);
  const cdnUrls = urls.filter(u => !u.includes('w3.org') && !u.includes('schema.org'));
  console.log(`Potentially active CDN/external resource URLs:`, [...new Set(cdnUrls)].slice(0, 10));

  // Check script tags
  const scriptRegex = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match;
  let sIndex = 0;
  while ((match = scriptRegex.exec(content)) !== null) {
    const attrs = match[1];
    const body = match[2];
    const srcMatch = attrs.match(/src=["'](.*?)["']/i);
    const src = srcMatch ? srcMatch[1] : 'INLINE';
    console.log(`Script ${sIndex++}: src="${src}", length=${body.length} chars, snippet: ${body.substring(0, 80).replace(/\s+/g, ' ')}`);
  }

  // Check style tags
  const styleRegex = /<style\b([^>]*)>([\s\S]*?)<\/style>/gi;
  let stIndex = 0;
  while ((match = styleRegex.exec(content)) !== null) {
    const body = match[2];
    console.log(`Style ${stIndex++}: length=${body.length} chars, snippet: ${body.substring(0, 80).replace(/\s+/g, ' ')}`);
  }

  // Check key AASHA markers
  const markers = [
    'window.WM', 'aasha_dictionary_db', 'wordDialog', 'rt(', 'speakWord',
    'fitCanvas', 'preset-bar', 'concept-def', 'sim-canvas', 'bottom-nav', 'nav-bar',
    'WHAT', 'WHY', 'HOW', 'SHOW', 'TRY', 'FEEDBACK', 'CONNECT', 'NAME',
    'KaTeX', 'JSXGraph', 'JXG', 'AudioContext', 'webkitAudioContext',
    'H5P', 'pie-item-player', 'math-var', '__AASHA_MATH_'
  ];
  console.log('--- Key Markers Check ---');
  markers.forEach(m => {
    const count = (content.match(new RegExp(m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;
    console.log(`  "${m}": ${count} occurrences`);
  });
}

analyzeFile(fractionsPath, 'Fractions Reference V5/V6');
analyzeFile(rationalPath, 'RationalNumbers Class 8');
analyzeFile(rationalAdPath, 'RationalNumbers Class 8 AD');
