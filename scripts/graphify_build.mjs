#!/usr/bin/env node
// Resolves the graphify CLI, which is only installed inside the pipeline Python
// venv. A bare `graphify build` fails whenever that venv is not on PATH.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pipelineDir = path.join(repoRoot, 'Aasha-AI', 'aasha-pipeline-with-master-json');

const candidates = process.platform === 'win32'
  ? [
      path.join(pipelineDir, 'venv', 'Scripts', 'graphify.exe'),
      path.join(pipelineDir, '.venv', 'Scripts', 'graphify.exe'),
    ]
  : [
      path.join(pipelineDir, 'venv', 'bin', 'graphify'),
      path.join(pipelineDir, '.venv', 'bin', 'graphify'),
    ];

const venvBinary = candidates.find((p) => fs.existsSync(p));
const exe = venvBinary || (process.platform === 'win32' ? 'graphify.exe' : 'graphify');

// This graphify build has no `build` subcommand; `update <path>` is the AST-only
// re-extraction + graph refresh.
const args = process.argv.slice(2);
const result = spawnSync(exe, args.length > 0 ? args : ['update', '.'], {
  cwd: repoRoot,
  stdio: 'inherit',
  shell: false,
});

if (result.error) {
  console.error(`[graphify:build] Could not launch graphify (${exe}): ${result.error.message}`);
  console.error('[graphify:build] Expected the CLI at one of:');
  for (const c of candidates) console.error(`  - ${c}`);
  console.error('[graphify:build] Install it with: uv tool install graphify-cli');
  process.exit(1);
}

process.exit(result.status ?? 1);
