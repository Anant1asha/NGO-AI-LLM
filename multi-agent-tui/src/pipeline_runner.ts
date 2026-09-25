import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import chalk from 'chalk';

export interface PipelineEvent {
  event: string;
  job_id?: string;
  message?: string;
  status?: string;
  duration?: number;
  cost_usd?: number;
  html_path?: string;
  error_stage?: string;
  error_message?: string;
  [key: string]: any;
}

export interface PipelineRunOptions {
  pdfPath: string;
  subject: string;
  grade: number;
  mode?: 'full-synthesis' | 'v5-engine';
  pythonPath?: string;
  pipelineDir?: string;
  onEvent?: (event: PipelineEvent) => void;
}

export interface PipelineResult {
  success: boolean;
  htmlPath: string;
  workDir: string;
  costUsd: number;
  durationSeconds: number;
  errorMessage?: string;
}

export class PipelineRunner {
  public static async run(options: PipelineRunOptions): Promise<PipelineResult> {
    const pipelineDir = options.pipelineDir || path.resolve(__dirname, '../../Aasha-AI/aasha-pipeline-with-master-json');
    const pythonExe = options.pythonPath || (process.platform === 'win32'
      ? path.join(pipelineDir, 'venv', 'Scripts', 'python.exe')
      : path.join(pipelineDir, 'venv', 'bin', 'python'));

    if (!fs.existsSync(pythonExe)) {
      throw new Error(`Python interpreter not found at: ${pythonExe}`);
    }

    const args = [
      '-m', 'aasha.cli',
      '--pdf', options.pdfPath,
      '--subject', options.subject,
      '--grade', options.grade.toString(),
      '--mode', options.mode || 'full-synthesis',
      '--json-events'
    ];

    console.log(chalk.cyan(`[PipelineRunner] Launching AASHA Multi-Agent Pipeline (Streaming JSON IPC)...`));
    console.log(chalk.gray(`Command: ${pythonExe} ${args.join(' ')}\n`));

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const child = spawn(pythonExe, args, { cwd: pipelineDir, stdio: ['ignore', 'pipe', 'pipe'] });

      let outputText = '';
      let errorText = '';
      let buffer = '';
      let eventHtmlPath = '';
      let eventCostUsd = 0;
      let eventDuration = 0;
      let isSuccess = false;
      let eventErrorMsg = '';

      child.stdout.on('data', (data) => {
        const text = data.toString();
        outputText += text;
        buffer += text;

        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
            try {
              const event: PipelineEvent = JSON.parse(trimmed);
              if (options.onEvent) {
                options.onEvent(event);
              }

              if (event.event === 'job_created') {
                console.log(chalk.blue(`[IPC] Job Created: ${event.job_id} (${event.subject} Grade ${event.grade})`));
              } else if (event.event === 'log') {
                console.log(chalk.gray(`  • ${event.message}`));
              } else if (event.event === 'pipeline_complete') {
                isSuccess = true;
                eventHtmlPath = event.html_path || '';
                eventCostUsd = event.cost_usd || 0;
                eventDuration = event.duration || 0;
              } else if (event.event === 'pipeline_failed') {
                isSuccess = false;
                eventErrorMsg = event.error_message || `Failed at stage: ${event.error_stage}`;
              }
              continue;
            } catch {
              // Not valid JSON event, fall through to text logging
            }
          }

          process.stdout.write(chalk.white(line + '\n'));
        }
      });

      child.stderr.on('data', (data) => {
        const text = data.toString();
        errorText += text;
        process.stderr.write(chalk.yellow(text));
      });

      child.on('close', (code) => {
        const durationSeconds = eventDuration || ((Date.now() - startTime) / 1000);
        const htmlMatch = outputText.match(/Output:\s*([^\r\n]+)/);
        const costMatch = outputText.match(/LLM Cost:\s*\$([0-9.]+)/);
        const htmlPath = eventHtmlPath || (htmlMatch ? htmlMatch[1].trim() : '');
        const costUsd = eventCostUsd || (costMatch ? parseFloat(costMatch[1]) : 0);
        const workDir = htmlPath ? path.dirname(htmlPath) : '';

        const success = (code === 0 || isSuccess) && !!htmlPath && fs.existsSync(htmlPath);

        if (success) {
          resolve({
            success: true,
            htmlPath,
            workDir,
            costUsd,
            durationSeconds
          });
        } else {
          resolve({
            success: false,
            htmlPath,
            workDir,
            costUsd,
            durationSeconds,
            errorMessage: eventErrorMsg || errorText || 'Pipeline exited with non-zero code.'
          });
        }
      });

      child.on('error', (err) => {
        reject(new Error(`Failed to spawn pipeline: ${err.message}`));
      });
    });
  }
}
