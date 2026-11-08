#!/usr/bin/env node
import { spawnSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..', '..', '..', '..');

const args = process.argv.slice(2);
const cliPath = path.join(ROOT_DIR, 'scripts', 'aasha_orchestrator_cli.mjs');

spawnSync(process.execPath, [cliPath, ...args], { stdio: 'inherit', shell: false });
