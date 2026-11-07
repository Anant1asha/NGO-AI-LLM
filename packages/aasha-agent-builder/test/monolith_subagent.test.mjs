import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';

import {
  CHILD_HTML5_BUNDLE_MAX_BYTES,
  escAttr,
  escJsStr,
  verifyMonolithBundle,
  assembleChapterMonolith,
  monolithSubagent
} from '../src/monolith_subagent.mjs';
import { resolveWorkspaceRoot } from '../src/ingest_subagent.mjs';

test('escAttr and escJsStr properly sanitize HTML attributes and string literals', () => {
  assert.equal(escAttr('<div class="test">\'hello\' & "world"</div>'), '&lt;div class=&quot;test&quot;&gt;&#39;hello&#39; &amp; &quot;world&quot;&lt;/div&gt;');
  assert.equal(escAttr(null), '');
  assert.equal(escAttr(undefined), '');

  assert.equal(escJsStr("hello 'world'\nline 2"), "hello \\'world\\'\\nline 2");
  assert.equal(escJsStr(null), '');
});

test('verifyMonolithBundle catches CDN leaks and size violations', () => {
  const leakingHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <!-- cdnjs.cloudflare.com leak marker -->
      <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/test/1.0/test.css">
    </head>
    <body><div>Test</div></body>
    </html>
  `;
  const res = verifyMonolithBundle(leakingHtml);
  assert.equal(res.valid, false);
  assert.ok(res.violations.some(v => v.rule === 'ZERO_CDN_VIOLATION'));
  assert.ok(res.violations.some(v => v.rule === 'TOUCH_TARGET_INVARIANT'));
});

test('verifyMonolithBundle certifies valid chapter bundle', () => {
  const root = resolveWorkspaceRoot();
  const targetHtmlPath = path.resolve(root, 'Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html');
  assert.ok(fs.existsSync(targetHtmlPath), 'Target chapter HTML must exist');

  const content = fs.readFileSync(targetHtmlPath, 'utf-8');
  const audit = verifyMonolithBundle(content);

  assert.equal(audit.valid, true, `Audit should pass with 0 violations. Violations: ${JSON.stringify(audit.violations)}`);
  assert.ok(audit.byteSize < CHILD_HTML5_BUNDLE_MAX_BYTES, 'Must be under 20 MB ceiling');
  assert.ok(audit.byteSize > 10000, 'Must have substantial content');
});

test('assembleChapterMonolith executes multi-agent pipeline and returns complete chapter spec', async () => {
  const result = await monolithSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml',
    outputPath: 'Aasha-AI/chapters/SquareCubeRoots_Class8_Gamified_v5_Enhanced_v6.html'
  });

  assert.equal(result.success, true);
  assert.equal(result.verification.offlineReady, true);
  assert.equal(result.verification.scopeLockedSizeUnder20MB, true);
  assert.equal(result.verification.zeroSpoilersCertified, true);
  assert.equal(result.assessmentTotalQuestions, 34);
  assert.ok(result.byteSize > 50000);
});
