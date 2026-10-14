import { spawn, spawnSync } from 'child_process';
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
  /**
   * Resiliently discovers a working Python interpreter across virtual environments,
   * Windows Python launcher (py.exe), and system PATH.
   */
  public static resolvePython(options?: PipelineRunOptions): string {
    const pipelineDir = options?.pipelineDir || path.resolve(__dirname, '../../Aasha-AI/aasha-pipeline-with-master-json');

    // 1. Explicit option
    if (options?.pythonPath && fs.existsSync(options.pythonPath)) {
      return options.pythonPath;
    }

    // 2. Local pipeline virtualenv
    const venvPython = process.platform === 'win32'
      ? path.join(pipelineDir, 'venv', 'Scripts', 'python.exe')
      : path.join(pipelineDir, 'venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) {
      return venvPython;
    }

    // 3. Workspace root virtualenv
    // pipelineDir is <repo>/Aasha-AI/aasha-pipeline-with-master-json, so the
    // workspace-root .venv is two levels up from the repo root's Aasha-AI/: verified
    // resolving to <repo>/.venv/Scripts/python.exe.
    const rootVenv = process.platform === 'win32'
      ? path.resolve(pipelineDir, '../../.venv/Scripts/python.exe')
      : path.resolve(pipelineDir, '../../.venv/bin/python');
    if (fs.existsSync(rootVenv)) {
      return rootVenv;
    }

    // 4. Windows py launcher
    if (process.platform === 'win32') {
      try {
        const check = spawnSync('py', ['-3', '-c', 'import sys; print(sys.executable)'], { encoding: 'utf-8' });
        if (check.status === 0 && check.stdout) {
          const exe = check.stdout.trim().split(/\r?\n/)[0].trim();
          if (exe && fs.existsSync(exe)) return exe;
        }
      } catch {}
    }

    // 5. System python / python3 from PATH
    for (const cmd of ['python', 'python3']) {
      try {
        const check = spawnSync(cmd, ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf-8' });
        if (check.status === 0 && check.stdout) {
          const exe = check.stdout.trim().split(/\r?\n/)[0].trim();
          if (exe && fs.existsSync(exe)) return exe;
        }
      } catch {}
    }

    throw new Error(
      `Python interpreter not found. Please install Python 3.10+ or initialize virtualenv at: ${path.join(pipelineDir, 'venv')}`
    );
  }

  /**
   * Resolves credentials from local BYOK vault (~/.aasha/config.json) or Aasha-AI/.env
   */
  public static resolveEnvironment(pipelineDir: string): NodeJS.ProcessEnv {
    const env: NodeJS.ProcessEnv = { ...process.env };

    // 1. Check BYOK vault
    const configDir = path.join(process.env.USERPROFILE || process.env.HOME || '.', '.aasha');
    const configFile = path.join(configDir, 'config.json');
    if (fs.existsSync(configFile)) {
      try {
        const cfg = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
        if (cfg.openrouter_key && !env.OPENROUTER_API_KEY) env.OPENROUTER_API_KEY = cfg.openrouter_key;
        if (cfg.gemini_key && !env.GEMINI_API_KEY) env.GEMINI_API_KEY = cfg.gemini_key;
      } catch {}
    }

    // 2. Check Aasha-AI/.env
    const aashaEnvFile = path.resolve(pipelineDir, '../.env');
    if (fs.existsSync(aashaEnvFile)) {
      try {
        const content = fs.readFileSync(aashaEnvFile, 'utf-8');
        for (const line of content.split(/\r?\n/)) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith('#')) continue;
          const eqIdx = trimmed.indexOf('=');
          if (eqIdx > 0) {
            const key = trimmed.slice(0, eqIdx).trim();
            const val = trimmed.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '');
            if (!env[key] && val) env[key] = val;
          }
        }
      } catch {}
    }

    return env;
  }

  public static async run(options: PipelineRunOptions): Promise<PipelineResult> {
    const pipelineDir = options.pipelineDir || path.resolve(__dirname, '../../Aasha-AI/aasha-pipeline-with-master-json');
    const pythonExe = this.resolvePython(options);
    const env = this.resolveEnvironment(pipelineDir);

    const hasLlmCredentials = !!(env.OPENROUTER_API_KEY || env.OPENAI_API_KEY || env.GEMINI_API_KEY || env.ANTHROPIC_API_KEY);
    if (!hasLlmCredentials) {
      console.log(chalk.yellow('[PipelineRunner] Note: No LLM credentials detected in vault (~/.aasha/config.json) or .env.'));
      console.log(chalk.gray('                  Deterministic extraction runs offline. Set keys with: aasha config openrouter_key <key>\n'));
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
    console.log(chalk.gray(`Interpreter: ${pythonExe}`));
    console.log(chalk.gray(`Command:     ${pythonExe} ${args.join(' ')}\n`));

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const child = spawn(pythonExe, args, { cwd: pipelineDir, env, stdio: ['ignore', 'pipe', 'pipe'] });

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
