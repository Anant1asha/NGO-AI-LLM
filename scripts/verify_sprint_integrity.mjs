#!/usr/bin/env node
/**
 * scripts/verify_sprint_integrity.mjs
 * AASHA AIOS 5-Pillar Sprint Verification & Hardening Engine.
 *
 * Runs end-to-end audit suites:
 * 1. Concurrency Suite (RG-001)
 * 2. Synthetic Fault Injection (OI-003)
 * 3. Live USD Billing Telemetry (OI-001)
 * 4. Pre-Commit Zero-Secret Scanner (SEC-002)
 * 5. Superbrain 1:1 Rule Parity Audit
 *
 * Emits a structured Markdown scorecard (SPRINT_VERIFICATION_REPORT.md).
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const args = process.argv.slice(2);
const isQuick = args.includes('--quick');
const isJson = args.includes('--json');
const reportIdx = args.indexOf('--report');
const reportPath = reportIdx > -1 && args[reportIdx + 1]
  ? path.resolve(process.cwd(), args[reportIdx + 1])
  : path.resolve(process.cwd(), 'SPRINT_VERIFICATION_REPORT.md');

const CHECKS = [
  {
    id: 'SEC-002',
    pillar: 'Pillar 4: Zero Secrets',
    name: 'Pre-Commit Secret Scanner',
    targetInvariant: 'No uninsulated tokens or private credentials staged',
    command: 'node scripts/lint_staged_secrets.mjs',
    quickAllowed: true,
  },
  {
    id: 'RULE-PARITY',
    pillar: 'Pillar 5: Rule Parity',
    name: 'Superbrain Schema & Parity Audit',
    targetInvariant: '100% schema compliance, 0 !!seq errors, 1:1 cross-IDE sync',
    command: 'node scripts/lint_superbrain_parity.mjs',
    quickAllowed: true,
  },
  {
    id: 'CI-WORKFLOWS',
    pillar: 'CI Resilience',
    name: 'GitHub Actions Workflow Lint',
    targetInvariant: 'Zero expression syntax warnings, dynamic secret indirection',
    command: 'node scripts/lint_workflows.mjs',
    quickAllowed: true,
  },
  {
    id: 'RG-001',
    pillar: 'Pillar 1: Concurrency',
    name: 'Bounded Async Concurrency Suite',
    targetInvariant: 'Max 2 in-flight workers, 0 Windows process table thrashing',
    command: 'cd Aasha-AI && npx tsx tests/test_concurrency_wiring.ts',
    quickAllowed: false,
  },
  {
    id: 'OI-003',
    pillar: 'Pillar 2: Fault Quarantine',
    name: 'Synthetic Fault Injection Suite',
    targetInvariant: 'Complete 2-repair failure path and downstream stage blocking',
    command: 'cd Aasha-AI && npx tsx tests/test_fault_injection_hardening.ts',
    quickAllowed: false,
  },
  {
    id: 'OI-001',
    pillar: 'Pillar 3: Billing & Reserve',
    name: 'Live USD Billing Telemetry Suite',
    targetInvariant: 'Live dollar cost tracking, $1.00 daily spend cap (CON-008 / OI-001), high-worth task auth',
    command: 'cd Aasha-AI && npx tsx tests/test_billing_observability_and_gemini_authorization.ts',
    quickAllowed: false,
  },
];

function runCheck(check) {
  const start = performance.now();
  try {
    const stdout = execSync(check.command, {
      cwd: process.cwd(),
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, NODE_ENV: 'test', MEMO0_OFFLINE: '1' },
    });
    const durationMs = Math.round(performance.now() - start);
    return {
      id: check.id,
      pillar: check.pillar,
      name: check.name,
      targetInvariant: check.targetInvariant,
      passed: true,
      durationMs,
      output: stdout.trim(),
    };
  } catch (err) {
    const durationMs = Math.round(performance.now() - start);
    const stdout = err.stdout ? err.stdout.toString() : '';
    const stderr = err.stderr ? err.stderr.toString() : '';
    return {
      id: check.id,
      pillar: check.pillar,
      name: check.name,
      targetInvariant: check.targetInvariant,
      passed: false,
      durationMs,
      output: stdout.trim(),
      error: (stderr || err.message).trim(),
    };
  }
}

function formatMarkdownReport(results, overallPassed, totalDurationMs) {
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  const badge = overallPassed ? '✅ **SPRINT CERTIFIED (PASS)**' : '❌ **VERIFICATION FAILED**';

  let md = `# AASHA AIOS Sprint Verification Report\n\n`;
  md += `- **Timestamp**: \`${timestamp}\`\n`;
  md += `- **Mode**: \`${isQuick ? 'QUICK (Static Linters Only)' : 'FULL (5-Pillar Comprehensive)'}\`\n`;
  md += `- **Execution Time**: \`${(totalDurationMs / 1000).toFixed(2)}s\`\n`;
  md += `- **Overall Status**: ${badge}\n\n`;
  md += `## Scorecard\n\n`;
  md += `| Pillar | Check | Target Invariant | Result | Latency |\n`;
  md += `| :--- | :--- | :--- | :--- | :--- |\n`;

  for (const r of results) {
    const status = r.passed ? '✅ PASS' : '❌ FAIL';
    md += `| **${r.pillar}** | ${r.name} (\`${r.id}\`) | ${r.targetInvariant} | ${status} | \`${r.durationMs}ms\` |\n`;
  }

  md += `\n---\n\n`;
  md += `## Detailed Subsystem Logs\n\n`;

  for (const r of results) {
    md += `### [${r.passed ? 'PASS' : 'FAIL'}] ${r.pillar}: ${r.name} (\`${r.id}\`)\n\n`;
    md += `**Command**: \`${CHECKS.find(c => c.id === r.id)?.command}\`\n\n`;
    if (r.error) {
      md += `**Error Diagnostics**:\n\`\`\`\n${r.error.substring(0, 1500)}\n\`\`\`\n\n`;
    }
    if (r.output) {
      const trimmedOutput = r.output.length > 2000 ? r.output.substring(r.output.length - 2000) : r.output;
      md += `<details><summary>Output Log (Click to expand)</summary>\n\n\`\`\`\n${trimmedOutput}\n\`\`\`\n\n</details>\n\n`;
    }
  }

  return md;
}

function main() {
  console.log('\n======================================================================');
  console.log(` AASHA AIOS SPRINT VERIFIER (${isQuick ? 'QUICK MODE' : 'FULL 5-PILLAR MODE'})`);
  console.log('======================================================================\n');

  const selectedChecks = isQuick
    ? CHECKS.filter(c => c.quickAllowed)
    : CHECKS;

  const results = [];
  const overallStart = performance.now();

  for (const check of selectedChecks) {
    process.stdout.write(`Running [${check.id}] ${check.name}... `);
    const res = runCheck(check);
    results.push(res);
    if (res.passed) {
      console.log(`PASS (${res.durationMs}ms)`);
    } else {
      console.log(`FAIL (${res.durationMs}ms)`);
      if (res.error) console.error(`  ↳ ${res.error.split('\n')[0]}`);
    }
  }

  const totalDurationMs = Math.round(performance.now() - overallStart);
  const overallPassed = results.every(r => r.passed);

  if (isJson) {
    console.log(JSON.stringify({ overallPassed, totalDurationMs, results }, null, 2));
  } else {
    const markdown = formatMarkdownReport(results, overallPassed, totalDurationMs);
    try {
      fs.writeFileSync(reportPath, markdown, 'utf-8');
      console.log(`\n📄 Scorecard report saved to: ${path.relative(process.cwd(), reportPath)}`);
    } catch (err) {
      console.warn(`\n⚠️  Could not write report to ${reportPath}:`, err.message);
    }

    console.log('\n======================================================================');
    console.log(` VERIFICATION RESULT: ${overallPassed ? 'ALL CHECKS PASSED ✅' : 'FAILURES DETECTED ❌'} (${results.filter(r => r.passed).length}/${results.length} passed in ${(totalDurationMs / 1000).toFixed(2)}s)`);
    console.log('======================================================================\n');
  }

  process.exit(overallPassed ? 0 : 1);
}

main();
