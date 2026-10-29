import readline from 'readline';
import chalk from 'chalk';
import path from 'path';
import fs from 'fs';
import * as dotenv from 'dotenv';
import { PedagogicalAuditor } from './pedagogical_auditor';
import { ScorecardTUI } from './scorecard_tui';
import { PipelineRunner } from './pipeline_runner';
import { RemediationEngine } from './remediation';

dotenv.config();

async function handleAudit(htmlPath: string) {
  const absPath = path.resolve(process.cwd(), htmlPath);
  if (!fs.existsSync(absPath)) {
    console.error(chalk.red(`Error: HTML file not found at ${absPath}`));
    process.exit(1);
  }

  const intermediatesDir = path.dirname(absPath);
  let report = PedagogicalAuditor.audit(absPath, intermediatesDir);

  const onPatch = async () => {
    report = await RemediationEngine.quickInlinePatch(report);
    await ScorecardTUI.show(report, undefined, onPatch);
  };

  await ScorecardTUI.show(report, undefined, onPatch);
}

async function handleRun(pdfPath: string, subject: string, grade: number) {
  const absPdf = path.resolve(process.cwd(), pdfPath);
  if (!fs.existsSync(absPdf)) {
    console.error(chalk.red(`Error: PDF not found at ${absPdf}`));
    process.exit(1);
  }

  console.log(chalk.cyan.bold('\n=== AASHA Autonomous Chapter Generation ===\n'));
  console.log(chalk.yellow('Interactive Hotkeys: [p] Pause  [r] Resume  [a] Approve HIL Override  [q] Inspect Quarantine\n'));

  let activeWorkDir = '';
  let activeJobId = '';

  const onKeypress = (_str: string, key: any) => {
    if (!key) return;
    if (key.ctrl && key.name === 'c') {
      if (activeWorkDir) {
        PipelineRunner.sendControlSignal(activeWorkDir, 'abort', 'tui_user', 'Interrupted via Ctrl+C');
      }
      process.exit(0);
    }

    const char = (key.name || '').toLowerCase();
    if (char === 'p') {
      if (activeWorkDir) {
        PipelineRunner.sendControlSignal(activeWorkDir, 'pause', 'tui_user');
        console.log(chalk.yellow('\n⏸ [TUI] Pause signal sent to orchestrator.'));
      }
    } else if (char === 'r') {
      if (activeWorkDir) {
        PipelineRunner.sendControlSignal(activeWorkDir, 'resume', 'tui_user');
        console.log(chalk.green('\n▶ [TUI] Resume signal sent to orchestrator.'));
      }
    } else if (char === 'a') {
      if (activeWorkDir) {
        PipelineRunner.sendControlSignal(activeWorkDir, 'approve_intervention', 'tui_educator', 'Approved in Multi-Agent TUI');
        console.log(chalk.cyan('\n✔ [TUI] Human Intervention Approved! Quarantine cleared.'));
      }
    } else if (char === 'q') {
      if (activeWorkDir) {
        const packet = PipelineRunner.getQuarantinePacket(activeWorkDir);
        if (packet) {
          console.log(chalk.red.bold('\n╔═══════════════════════════════════════════════════════════════════╗'));
          console.log(chalk.red.bold('║                QUARANTINE DIAGNOSTIC PACKET                       ║'));
          console.log(chalk.red.bold('╚═══════════════════════════════════════════════════════════════════╝'));
          console.log(chalk.white(JSON.stringify(packet, null, 2)));
          console.log(chalk.yellow('Press [a] to approve human intervention override.\n'));
        } else {
          console.log(chalk.gray('\n[TUI] No active quarantine packet found for current job.'));
        }
      }
    }
  };

  if (process.stdin.isTTY) {
    try {
      readline.emitKeypressEvents(process.stdin);
      process.stdin.setRawMode(true);
      process.stdin.on('keypress', onKeypress);
    } catch {}
  }

  let result;
  try {
    result = await PipelineRunner.run({
      pdfPath: absPdf,
      subject,
      grade,
      mode: 'full-synthesis',
      onJobStarted: (jobId, workDir) => {
        activeJobId = jobId;
        activeWorkDir = workDir;
      }
    });
  } finally {
    if (process.stdin.isTTY) {
      try {
        process.stdin.removeListener('keypress', onKeypress);
        process.stdin.setRawMode(false);
      } catch {}
    }
  }

  if (result.quarantined) {
    console.log(chalk.red.bold('\n╔═══════════════════════════════════════════════════════════════════╗'));
    console.log(chalk.red.bold('║  ⛔ QUARANTINE ACTIVATED — Bounded Self-Repair Budget Exhausted    ║'));
    console.log(chalk.red.bold('╚═══════════════════════════════════════════════════════════════════╝'));
    console.log(chalk.yellow(`Job ID: ${activeJobId}`));
    console.log(chalk.yellow(`Reason: ${result.errorMessage}`));
    if (result.quarantinePacket) {
      console.log(chalk.white(`Violations: ${JSON.stringify(result.quarantinePacket.violations || result.quarantinePacket, null, 2)}`));
    }
    console.log(chalk.cyan('\nTo approve and release downstream bundle via API:'));
    console.log(chalk.gray(`curl -X POST http://localhost:3000/api/jobs/${activeJobId}/control -H "Content-Type: application/json" -d '{"action": "approve_intervention"}'\n`));
    process.exit(1);
  }

  if (!result.success) {
    console.error(chalk.red(`\nPipeline failed: ${result.errorMessage}`));
    process.exit(1);
  }

  console.log(chalk.green(`\n✔ Generation complete in ${result.durationSeconds.toFixed(1)}s (Cost: $${result.costUsd.toFixed(4)})`));
  console.log(chalk.cyan('Launching AASHA Pedagogical Scorecard for Educator Audit...\n'));

  await handleAudit(result.htmlPath);
}

function showInteractiveMenu() {
  console.log(chalk.cyan.bold('\n╔═══════════════════════════════════════════════════════════════════╗'));
  console.log(chalk.cyan.bold('║       AASHA MULTI-AGENT TUI: EDUCATOR STANDARDS & READINESS       ║'));
  console.log(chalk.cyan.bold('╚═══════════════════════════════════════════════════════════════════╝'));
  console.log(chalk.white('1. Audit & Sign-Off Existing Chapter HTML (ऑडिट और शिक्षक सत्यापन)'));
  console.log(chalk.white('2. Generate New Chapter from School PDF & Audit (किताब से नया चैप्टर)'));
  console.log(chalk.gray('3. Exit (बाहर निकलें)\n'));

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  rl.question(chalk.green('Select option (1-3) › '), async (choice) => {
    rl.close();
    if (choice.trim() === '1') {
      const rl2 = readline.createInterface({ input: process.stdin, output: process.stdout });
      rl2.question(chalk.cyan('Enter path to chapter.html › '), async (p) => {
        rl2.close();
        if (p.trim()) await handleAudit(p.trim());
      });
    } else if (choice.trim() === '2') {
      const rl3 = readline.createInterface({ input: process.stdin, output: process.stdout });
      rl3.question(chalk.cyan('Enter path to chapter PDF › '), async (pdf) => {
        rl3.question(chalk.cyan('Enter subject (e.g. math, science) › '), async (subj) => {
          rl3.question(chalk.cyan('Enter grade (e.g. 4) › '), async (gr) => {
            rl3.close();
            await handleRun(pdf.trim(), subj.trim() || 'math', parseInt(gr.trim() || '4', 10));
          });
        });
      });
    } else {
      console.log(chalk.gray('Goodbye!'));
    }
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    showInteractiveMenu();
    return;
  }

  const command = args[0].toLowerCase();
  if (command === 'audit') {
    const htmlPath = args[1];
    if (!htmlPath) {
      console.error(chalk.red('Usage: npm start -- audit <path-to-chapter.html>'));
      process.exit(1);
    }
    await handleAudit(htmlPath);
  } else if (command === 'run') {
    let pdf = '';
    let subject = 'math';
    let grade = 4;
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--pdf' && args[i + 1]) pdf = args[++i];
      if (args[i] === '--subject' && args[i + 1]) subject = args[++i];
      if (args[i] === '--grade' && args[i + 1]) grade = parseInt(args[++i], 10);
    }
    if (!pdf) {
      console.error(chalk.red('Usage: npm start -- run --pdf <path.pdf> --subject <subj> --grade <gr>'));
      process.exit(1);
    }
    await handleRun(pdf, subject, grade);
  } else {
    showInteractiveMenu();
  }
}

main().catch((err) => {
  console.error(chalk.red(`Fatal error: ${err.message}`));
  process.exit(1);
});
