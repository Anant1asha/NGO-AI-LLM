/**
 * @file scripts/hachi_bridge.mjs
 * @description Node.js Bridge for Hachi ObjectGraph (.og) engine and multi-agent delegation.
 * Enforces 100% pure ECMAScript ESM JavaScript. Zero TypeScript syntax.
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const pythonExe = path.join(projectRoot, 'packages', 'hachi', '.venv', 'Scripts', 'python.exe');
const hachiSrc = path.join(projectRoot, 'packages', 'hachi', 'src');

/**
 * Executes a Hachi command via python in packages/hachi/.venv
 * @param {string[]} pyArgs - Python command arguments
 * @returns {{ stdout: string, stderr: string, status: number }}
 */
export function runHachiPython(pyArgs) {
  const result = spawnSync(pythonExe, pyArgs, {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: hachiSrc,
    },
    encoding: 'utf-8',
    windowsHide: true,
  });

  return {
    stdout: result.stdout || '',
    stderr: result.stderr || '',
    status: result.status ?? 1,
  };
}

/**
 * Search Hachi ObjectGraph skills
 * @param {string} query
 * @returns {object}
 */
export function searchSkills(query) {
  const pyCode = `
import sys, json
sys.path.insert(0, r'${hachiSrc}')
from hachi.mcp_server import hachi_search_skills
print(hachi_search_skills(${JSON.stringify(query)}))
`;
  const res = runHachiPython(['-c', pyCode]);
  try {
    return JSON.parse(res.stdout);
  } catch {
    return { status: 'error', output: res.stdout, error: res.stderr };
  }
}

/**
 * Peek skill dense view and token estimate (~30 tokens)
 * @param {string[]} names
 * @returns {object}
 */
export function peekSkill(names) {
  const pyCode = `
import sys, json
sys.path.insert(0, r'${hachiSrc}')
from hachi.mcp_server import hachi_peek_skill
print(hachi_peek_skill(${JSON.stringify(names)}))
`;
  const res = runHachiPython(['-c', pyCode]);
  try {
    return JSON.parse(res.stdout);
  } catch {
    return { status: 'error', output: res.stdout, error: res.stderr };
  }
}

/**
 * Load skill nodes/blocks
 * @param {string} name
 * @param {string[]|null} [blocks=null]
 * @returns {string}
 */
export function loadSkill(name, blocks = null) {
  const pyCode = `
import sys
sys.path.insert(0, r'${hachiSrc}')
from hachi.mcp_server import hachi_load_skill
print(hachi_load_skill(${JSON.stringify(name)}, ${blocks ? JSON.stringify(blocks) : 'None'}))
`;
  const res = runHachiPython(['-c', pyCode]);
  return res.stdout || res.stderr;
}

/**
 * List subagent roles
 * @returns {object}
 */
export function listRoles() {
  const pyCode = `
import sys, json
sys.path.insert(0, r'${hachiSrc}')
from hachi.mcp_server import hachi_list_roles
print(hachi_list_roles())
`;
  const res = runHachiPython(['-c', pyCode]);
  try {
    return JSON.parse(res.stdout);
  } catch {
    return { status: 'error', output: res.stdout, error: res.stderr };
  }
}

/**
 * Run Hachi Doctor diagnostic report
 * @returns {object}
 */
export function doctor() {
  const pyCode = `
import sys, json
sys.path.insert(0, r'${hachiSrc}')
from hachi.mcp_server import hachi_doctor
print(hachi_doctor())
`;
  const res = runHachiPython(['-c', pyCode]);
  try {
    return JSON.parse(res.stdout);
  } catch {
    return { status: 'error', output: res.stdout, error: res.stderr };
  }
}

// CLI Execution Support
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const command = process.argv[2] || 'doctor';
  if (command === 'doctor') {
    console.log(JSON.stringify(doctor(), null, 2));
  } else if (command === 'roles') {
    console.log(JSON.stringify(listRoles(), null, 2));
  } else if (command === 'search') {
    const q = process.argv.slice(3).join(' ') || 'coder';
    console.log(JSON.stringify(searchSkills(q), null, 2));
  } else if (command === 'peek') {
    const names = process.argv.slice(3);
    console.log(JSON.stringify(peekSkill(names.length ? names : ['coder:execution-protocol']), null, 2));
  } else if (command === 'load') {
    const name = process.argv[3] || 'coder:execution-protocol';
    console.log(loadSkill(name));
  } else {
    console.log(`Unknown command: ${command}. Use: doctor | roles | search <q> | peek <name> | load <name>`);
  }
}
