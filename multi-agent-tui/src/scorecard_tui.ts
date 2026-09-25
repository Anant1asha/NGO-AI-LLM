import chalk from 'chalk';
import readline from 'readline';
import { exec } from 'child_process';
import { AuditReport } from './pedagogical_auditor';

export class ScorecardTUI {
  /**
   * Render the AASHA Pedagogical Scorecard in the terminal and handle educator actions.
   */
  public static async show(report: AuditReport, onRepair?: () => Promise<void>, onPatch?: () => Promise<void>): Promise<boolean> {
    console.clear();
    this.renderHeader(report);
    this.renderPillars(report);
    this.renderExerciseUtilization(report);
    this.renderDefects(report);

    return new Promise((resolve) => {
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
      });

      const promptMenu = () => {
        console.log(chalk.cyan('\n─────────────────────────────────────────────────────────────'));
        console.log(chalk.bold('Educator Actions:'));
        if (report.signOffAllowed) {
          console.log(chalk.green('  [S] Sign-Off & Publish to Classrooms (Ready!)'));
        } else {
          console.log(chalk.gray('  [S] Sign-Off & Publish (🔒 Locked — resolve critical violations)'));
        }
        console.log(chalk.yellow('  [O] Open & Test HTML Build File in Browser (शिक्षक पूर्वावलोकन)'));
        console.log(chalk.magenta('  [R] Request Targeted Agent Auto-Repair'));
        console.log(chalk.blue('  [E] Quick Inline Terminal Patch'));
        console.log(chalk.white('  [V] View Full Details'));
        console.log(chalk.gray('  [Q] Exit to Batch Queue'));
        console.log(chalk.cyan('─────────────────────────────────────────────────────────────'));

        rl.question(chalk.bold('Select action › '), async (ans) => {
          const choice = ans.trim().toUpperCase();

          if (choice === 'S') {
            if (report.signOffAllowed) {
              console.log(chalk.green.bold('\n✔ Chapter Signed-Off and Certified for Classroom Deployment!'));
              rl.close();
              resolve(true);
            } else {
              console.log(chalk.red('\n✖ Cannot sign-off: Please resolve all critical violations first.'));
              promptMenu();
            }
          } else if (choice === 'O') {
            console.log(chalk.cyan(`\nOpening chapter in browser: ${report.htmlPath}...`));
            this.openInBrowser(report.htmlPath);
            promptMenu();
          } else if (choice === 'R') {
            if (onRepair) {
              console.log(chalk.magenta('\nTriggering targeted agent repair...'));
              rl.close();
              await onRepair();
              resolve(false);
            } else {
              console.log(chalk.yellow('Auto-repair handler not configured.'));
              promptMenu();
            }
          } else if (choice === 'E') {
            if (onPatch) {
              rl.close();
              await onPatch();
              resolve(false);
            } else {
              console.log(chalk.yellow('Inline patch handler not configured.'));
              promptMenu();
            }
          } else if (choice === 'V') {
            this.renderFullDetails(report);
            promptMenu();
          } else if (choice === 'Q') {
            rl.close();
            resolve(false);
          } else {
            console.log(chalk.red('Invalid option.'));
            promptMenu();
          }
        });
      };

      promptMenu();
    });
  }

  private static renderHeader(report: AuditReport) {
    const scoreColor = report.overallScore >= 90 ? chalk.green.bold : (report.overallScore >= 70 ? chalk.yellow.bold : chalk.red.bold);
    console.log(chalk.bold.cyan('╔═══════════════════════════════════════════════════════════════════╗'));
    console.log(chalk.bold.cyan('║          AASHA PEDAGOGICAL SCORECARD & READINESS CONSOLE          ║'));
    console.log(chalk.bold.cyan('╚═══════════════════════════════════════════════════════════════════╝'));
    console.log(`Chapter: ${chalk.bold.white(report.chapterTitle)}`);
    console.log(`Pedagogical Score: ${scoreColor(report.overallScore + '/100')}  |  Status: ${report.signOffAllowed ? chalk.green.bold('✔ READY') : chalk.red.bold('✖ BLOCKED')}`);
    console.log(chalk.gray(`File: ${report.htmlPath}\n`));
  }

  private static renderPillars(report: AuditReport) {
    console.log(chalk.bold('AASHA Teaching Guide Core Pillars:'));
    const pillars = [
      report.pillars.goldenFlow,
      report.pillars.twoLayerRigor,
      report.pillars.misconceptionsAndHints,
      report.pillars.airGappedSafety
    ];

    for (const p of pillars) {
      const icon = p.passed ? chalk.green('✔ PASS') : chalk.red('✖ FAIL');
      const scoreStr = p.score >= 90 ? chalk.green(`${p.score}%`) : (p.score >= 70 ? chalk.yellow(`${p.score}%`) : chalk.red(`${p.score}%`));
      console.log(`  ${icon}  ${p.name.padEnd(46)} [${scoreStr}]`);
    }
  }

  private static renderExerciseUtilization(report: AuditReport) {
    const eu = report.exerciseUtilization;
    const icon = eu.passed ? chalk.green('✔') : chalk.red('✖');
    console.log(chalk.bold('\nTextbook Exercise Utilization (100% Curriculum Scope):'));
    console.log(`  ${icon} ${eu.totalAssessed} of ${eu.totalExtracted} textbook exercises converted to 3-tier gamified levels (${chalk.bold(eu.percentage + '%')})`);
  }

  private static renderDefects(report: AuditReport) {
    if (report.criticalViolationsCount > 0) {
      console.log(chalk.red.bold(`\nCritical Violations (${report.criticalViolationsCount}) — Must be resolved before sign-off:`));
      const allCrit = [
        ...report.pillars.goldenFlow.criticalViolations,
        ...report.pillars.twoLayerRigor.criticalViolations,
        ...report.pillars.misconceptionsAndHints.criticalViolations,
        ...report.pillars.airGappedSafety.criticalViolations
      ];
      for (const cv of allCrit) {
        console.log(chalk.red(`  • ${cv}`));
      }
    }

    if (report.advisoriesCount > 0) {
      console.log(chalk.yellow.bold(`\nPedagogical Advisories (${report.advisoriesCount}) — Recommended improvements:`));
      const allAdv = [
        ...report.pillars.goldenFlow.advisories,
        ...report.pillars.twoLayerRigor.advisories,
        ...report.pillars.misconceptionsAndHints.advisories,
        ...report.pillars.airGappedSafety.advisories
      ];
      for (const adv of allAdv) {
        console.log(chalk.yellow(`  • ${adv}`));
      }
    }
  }

  private static renderFullDetails(report: AuditReport) {
    console.log(chalk.cyan('\n=== Full Pedagogical Audit Details ==='));
    console.log(JSON.stringify(report, null, 2));
  }

  private static openInBrowser(filePath: string) {
    const startCmd = process.platform === 'win32' ? `start "" "${filePath}"` : (process.platform === 'darwin' ? `open "${filePath}"` : `xdg-open "${filePath}"`);
    exec(startCmd, (err) => {
      if (err) {
        console.error(chalk.red(`Could not open browser: ${err.message}`));
      }
    });
  }
}
