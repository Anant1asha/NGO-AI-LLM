import fs from 'fs';
import readline from 'readline';
import chalk from 'chalk';
import { AuditReport, PedagogicalAuditor } from './pedagogical_auditor';

export class RemediationEngine {
  /**
   * Interactive inline text patcher directly in terminal for educators.
   */
  public static async quickInlinePatch(report: AuditReport): Promise<AuditReport> {
    console.log(chalk.bold.blue('\n=== AASHA Quick Inline Terminal Patch ==='));
    console.log(chalk.gray('Search for text in the chapter to replace (e.g. spoiler text or phrasing):'));

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const askQuestion = (query: string): Promise<string> => {
      return new Promise((res) => rl.question(query, res));
    };

    const targetText = await askQuestion(chalk.cyan('Search text to replace › '));
    if (!targetText.trim()) {
      console.log(chalk.yellow('Patch canceled: empty search string.'));
      rl.close();
      return report;
    }

    const html = fs.readFileSync(report.htmlPath, 'utf-8');
    if (!html.includes(targetText)) {
      console.log(chalk.red(`Search text not found in ${report.htmlPath}.`));
      rl.close();
      return report;
    }

    const replacementText = await askQuestion(chalk.cyan('Replacement text › '));
    rl.close();

    const updatedHtml = html.replace(new RegExp(this.escapeRegExp(targetText), 'g'), replacementText);
    fs.writeFileSync(report.htmlPath, updatedHtml, 'utf-8');
    console.log(chalk.green('✔ Successfully patched chapter HTML!'));

    // Re-run audit
    return PedagogicalAuditor.audit(report.htmlPath);
  }

  private static escapeRegExp(string: string): string {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
}
