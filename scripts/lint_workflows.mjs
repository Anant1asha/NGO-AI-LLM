/**
 * @file lint_workflows.mjs
 * @description Audits GitHub Actions workflows across root and sub-repos for common syntax pitfalls,
 * deprecated ${{ }} inside if: conditionals, and direct secret access patterns that cause IDE schema warnings.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const searchDirs = [
  path.join(rootDir, '.github', 'workflows'),
  path.join(rootDir, 'aasha-studio', '.github', 'workflows')
];

let totalIssues = 0;
let totalChecked = 0;

console.log('🔍 Auditing GitHub Actions workflows for syntax & schema resilience...\n');

for (const dir of searchDirs) {
  if (!fs.existsSync(dir)) continue;

  const files = fs.readdirSync(dir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));

  for (const file of files) {
    totalChecked++;
    const filePath = path.join(dir, file);
    const relPath = path.relative(rootDir, filePath).replace(/\\/g, '/');
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split(/\r?\n/);
    const fileIssues = [];

    lines.forEach((line, idx) => {
      const lineNum = idx + 1;
      const trimmed = line.trim();

      // Check 1: ${{ }} inside if: conditional
      if (/^\s*if:\s*.*\$\{\{.*\}\}/.test(line)) {
        fileIssues.push({
          line: lineNum,
          rule: 'no-expression-in-if',
          msg: 'Deprecated ${{ }} inside "if:" conditional. Remove ${{ and }} wrapper.'
        });
      }

      // Check 2: Direct secrets.CUSTOM_KEY without indirection
      // Excludes GITHUB_TOKEN which is standard and statically typed
      const directSecretMatch = line.match(/secrets\.(?!GITHUB_TOKEN)([a-zA-Z0-9_]+)/);
      if (directSecretMatch && !line.includes('toJSON(secrets)')) {
        fileIssues.push({
          line: lineNum,
          rule: 'prefer-dynamic-secret-indirection',
          msg: `Direct secret access "${directSecretMatch[0]}" can trigger IDE schema warning "Context access might be invalid". Consider: fromJSON(toJSON(secrets))['${directSecretMatch[1]}']`
        });
      }

      // Check 3: Trailing whitespace
      if (/\s+$/.test(line)) {
        fileIssues.push({
          line: lineNum,
          rule: 'no-trailing-whitespace',
          msg: 'Trailing whitespace detected.'
        });
      }
    });

    if (fileIssues.length > 0) {
      console.log(`⚠️  ${relPath} (${fileIssues.length} issues):`);
      for (const issue of fileIssues) {
        console.log(`   L${issue.line}: [${issue.rule}] ${issue.msg}`);
      }
      totalIssues += fileIssues.length;
    } else {
      console.log(`✅ ${relPath} (Clean)`);
    }
  }
}

console.log('\n----------------------------------------');
console.log(`Workflows checked: ${totalChecked}`);
console.log(`Issues detected:   ${totalIssues}`);
console.log('----------------------------------------');

if (totalIssues > 0) {
  console.log('❌ Workflow linting finished with warnings/issues.');
  process.exit(1);
} else {
  console.log('✨ All workflows passed CI syntax and schema resilience audit!');
  process.exit(0);
}
