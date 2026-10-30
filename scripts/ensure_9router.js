/**
 * scripts/ensure_9router.js
 * AASHA Learning Ecosystem — 9Router Gateway Resilience & Auto-Starter
 * 
 * Invariants:
 * 1. Checks local port 20128 gateway connectivity.
 * 2. If offline or unresponsive, automatically spawns 9Router headless daemon in background.
 * 3. Enforces unref() and detached mode to comply with the Daemon Process Invariant.
 * 4. Resolves 127.0.0.1 directly to avoid Windows IPv6 resolution latency.
 * 5. Provides both programmatic API (ensure9Router) and standalone CLI execution.
 * 6. Auto-registers Windows Logon auto-start hook in HKCU Run registry wrapped in try/catch.
 */

const http = require('http');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

const DEFAULT_PORT = 20128;
const DEFAULT_HOST = '127.0.0.1';

/**
 * Fast probe of the 9Router gateway.
 * Tests root path '/' first (immediate 307) then returns responsiveness.
 */
function probeGateway(host = DEFAULT_HOST, port = DEFAULT_PORT, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const req = http.request({
      hostname: host,
      port: port,
      path: '/',
      method: 'GET',
      timeout: timeoutMs
    }, (res) => {
      const latency = Date.now() - start;
      if (res.statusCode >= 200 && res.statusCode < 400) {
        resolve({ active: true, statusCode: res.statusCode, latency });
      } else {
        resolve({ active: true, statusCode: res.statusCode, latency });
      }
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ active: false, error: 'TIMEOUT' });
    });

    req.on('error', (err) => {
      resolve({ active: false, error: err.code || err.message });
    });

    req.end();
  });
}

/**
 * Locate 9Router custom-server.js or CLI in the system.
 */
function find9RouterServerPath() {
  const candidates = [];
  const appData = process.env.APPDATA;
  if (appData) {
    candidates.push(path.join(appData, 'npm', 'node_modules', '9router', 'app', 'custom-server.js'));
    candidates.push(path.join(appData, 'npm', 'node_modules', '9router', 'cli.js'));
  }
  const userProfile = process.env.USERPROFILE;
  if (userProfile) {
    candidates.push(path.join(userProfile, 'AppData', 'Roaming', 'npm', 'node_modules', '9router', 'app', 'custom-server.js'));
  }

  for (const c of candidates) {
    if (fs.existsSync(c)) {
      return c;
    }
  }
  return null;
}

/**
 * Register Windows User Logon Auto-Start hook in HKCU Run registry (wrapped in try/catch).
 */
function ensureWindowsStartupHook() {
  if (process.platform !== 'win32') return;
  try {
    const hiddenScript = path.resolve(__dirname, 'start_9router_hidden.ps1');
    if (!fs.existsSync(hiddenScript)) return;

    const psCmd = `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "${hiddenScript}"`;
    const regCheckCmd = `powershell -NoProfile -Command "Get-ItemPropertyValue -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name 'AASHA_9Router_Gateway' -ErrorAction SilentlyContinue"`;
    let currentVal = '';
    try {
      currentVal = execSync(regCheckCmd, { encoding: 'utf-8', stdio: 'pipe' }).trim();
    } catch {}

    if (currentVal !== psCmd) {
      const setRegCmd = `powershell -NoProfile -Command "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name 'AASHA_9Router_Gateway' -Value '${psCmd.replace(/'/g, "''")}'"`;
      execSync(setRegCmd, { stdio: 'pipe' });
    }
  } catch (err) {
    // Advisory note as per Windows Registry Environment Access Invariant
  }
}

/**
 * Launch 9Router as an unreferenced, detached background daemon.
 */
function launch9RouterDaemon(serverPath) {
  const packageDir = path.resolve(path.dirname(serverPath), '..');
  const workingDir = fs.existsSync(packageDir) ? packageDir : path.dirname(serverPath);

  const child = spawn(process.execPath, [serverPath], {
    cwd: workingDir,
    env: {
      ...process.env,
      PORT: String(DEFAULT_PORT),
      HOSTNAME: DEFAULT_HOST
    },
    detached: true,
    stdio: 'ignore',
    windowsHide: true
  });

  // Strict Daemon Process Invariant: unref() detached child process
  if (child.unref) {
    child.unref();
  }
  return child;
}

/**
 * Ensure 9Router is active and responsive.
 * If offline, boots the daemon and polls until active or timeout.
 */
async function ensure9Router(options = {}) {
  const { maxWaitMs = 18000, pollIntervalMs = 600, silent = false } = options;

  // 0. Ensure persistent startup hook
  ensureWindowsStartupHook();

  // 1. Initial quick probe
  const initial = await probeGateway(DEFAULT_HOST, DEFAULT_PORT, 2500);
  if (initial.active) {
    if (!silent) {
      console.log(`[9Router Gateway] Already active on http://${DEFAULT_HOST}:${DEFAULT_PORT} (${initial.latency}ms latency).`);
    }
    return { active: true, started: false, latency: initial.latency };
  }

  // 2. Gateway is down — locate script
  const serverPath = find9RouterServerPath();
  if (!serverPath) {
    const msg = `[9Router Gateway] ⚠️ 9Router package not found in npm global modules. Direct Tier 1 OpenRouter fallback active.`;
    if (!silent) console.warn(msg);
    return { active: false, started: false, error: 'SERVER_NOT_FOUND' };
  }

  if (!silent) {
    console.log(`[9Router Gateway] ℹ️ 9Router offline on port ${DEFAULT_PORT}. Auto-starting background daemon...`);
  }

  launch9RouterDaemon(serverPath);

  // 3. Poll for readiness (allows Next.js cold start up to maxWaitMs)
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    await new Promise((r) => setTimeout(r, pollIntervalMs));
    const probe = await probeGateway(DEFAULT_HOST, DEFAULT_PORT, 2000);
    if (probe.active) {
      const totalTime = Date.now() - startTime;
      if (!silent) {
        console.log(`[9Router Gateway] ✅ Successfully auto-enabled and responsive on http://${DEFAULT_HOST}:${DEFAULT_PORT} in ${totalTime}ms.`);
      }
      return { active: true, started: true, bootTimeMs: totalTime, latency: probe.latency };
    }
  }

  const failMsg = `[9Router Gateway] ⚠️ Auto-start timed out after ${maxWaitMs}ms. Tier 1 OpenRouter free pool fallback active.`;
  if (!silent) console.warn(failMsg);
  return { active: false, started: true, error: 'BOOT_TIMEOUT' };
}

module.exports = {
  probeGateway,
  ensure9Router,
  find9RouterServerPath,
  ensureWindowsStartupHook
};

// Standalone execution
if (require.main === module) {
  (async () => {
    const result = await ensure9Router({ silent: false });
    process.exit(result.active ? 0 : 1);
  })();
}
