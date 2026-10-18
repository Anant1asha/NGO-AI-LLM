#!/usr/bin/env node

/**
 * AASHA Learning Ecosystem — Unified Root Orchestrator
 * Connects Aasha-AI, aasha-studio, and multi-agent-tui into a single terminal hub.
 */

const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

const ROOT_DIR = path.resolve(__dirname, '..');

const COMMANDS = {
  '1': { label: 'AASHA Studio UI (Vite + React on :5173)', cmd: 'npm', args: ['--prefix', 'aasha-studio/apps/studio-ui', 'run', 'dev'] },
  '2': { label: 'Student Learner Web App (PWA on :4173)', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'run', 'dev:learner'] },
  '3': { label: 'Multi-Agent TUI Terminal Console', cmd: 'npm', args: ['--prefix', 'multi-agent-tui', 'run', 'dev'] },
  '4': { label: 'Super Admin Status & Memory Audit', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'run', 'admin:status'] },
  '5': { label: 'L-Truth 100/100 Anti-Spoiler Benchmark', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'run', 'validate'] },
  '6': { label: 'Master E2E Multi-Chapter Suite', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'run', 'test:master'] },
  '7': { label: 'Test All Repositories & Workspaces', cmd: 'npm', args: ['run', 'test:all'] },
  '8': { label: 'Build & Package Studio (Tauri / Zero-Rust)', cmd: 'npm', args: ['--prefix', 'aasha-studio', 'run', 'build'] },
  '9': { label: 'Setup Native Rust Toolchain for Windows (.exe / .msi)', cmd: 'powershell', args: ['-ExecutionPolicy', 'Bypass', '-File', './scripts/setup_rust_windows.ps1'] },
  '10': { label: 'Laya System 1 Pre-Router Dual-Path Audit (Zero-Token Bleed)', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'exec', '--', 'tsx', 'Aasha-AI/tests/laya_router.test.ts'] },
  '11': { label: 'Compile Standalone Beta Chapter (V6 Engine <20MB Bundle)', cmd: 'npm', args: ['--prefix', 'Aasha-AI', 'run', 'build:chapter'] },
  '12': { label: 'Audit Local 9Router Gateway Status', cmd: 'node', args: ['scripts/check_gateway_status.js'] }
};

function printBanner() {
  console.clear();
  console.log('======================================================================');
  console.log('       🌟 AASHA LEARNING & IMPACT ECOSYSTEM — ROOT ORCHESTRATOR 🌟    ');
  console.log('======================================================================');
  console.log('  Unified control plane across Aasha-AI, aasha-studio, and multi-agent-tui');
  console.log('----------------------------------------------------------------------');
  Object.keys(COMMANDS).forEach((k) => {
    console.log(`  [${k}] ${COMMANDS[k].label}`);
  });
  console.log('  [0] Exit');
  console.log('======================================================================');
}

function runTask(task, callback) {
  console.log(`\n🚀 Launching: ${task.label}...\n`);
  const child = spawn(task.cmd, task.args, {
    cwd: ROOT_DIR,
    stdio: 'inherit',
    shell: true
  });

  child.on('close', (code) => {
    console.log(`\n✓ Process finished with exit code: ${code}`);
    if (callback) {
      setTimeout(() => callback(code), 1200);
    }
  });
}

const directArg = process.argv[2];
if (directArg) {
  if (COMMANDS[directArg]) {
    runTask(COMMANDS[directArg], (code) => process.exit(code ?? 0));
  } else {
    // Check shortcuts
    const shortcuts = {
      'studio': COMMANDS['1'],
      'learner': COMMANDS['2'],
      'tui': COMMANDS['3'],
      'status': COMMANDS['4'],
      'test': COMMANDS['5'],
      'master': COMMANDS['6'],
      'all': COMMANDS['7'],
      'build': COMMANDS['8'],
      'rust': COMMANDS['9'],
      'laya': COMMANDS['10'],
      'compile': COMMANDS['11'],
      'gateway': COMMANDS['12']
    };
    if (shortcuts[directArg]) {
      runTask(shortcuts[directArg], (code) => process.exit(code ?? 0));
    } else {
      console.log(`Unknown command: ${directArg}`);
      console.log('Available arguments: studio, learner, tui, status, test, master, all, build, rust, laya, compile, gateway');
      process.exit(1);
    }
  }
} else {
  // Interactive Mode
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  function promptMenu() {
    printBanner();
    rl.question('\nSelect an option [1-12, 0 to exit]: ', (ans) => {
      const choice = ans.trim();
      if (choice === '0' || choice.toLowerCase() === 'q') {
        console.log('\nGoodbye!\n');
        rl.close();
        process.exit(0);
      } else if (COMMANDS[choice]) {
        runTask(COMMANDS[choice], () => {
          promptMenu();
        });
      } else {
        console.log('\nInvalid selection. Try again.');
        setTimeout(promptMenu, 1000);
      }
    });
  }

  promptMenu();
}
