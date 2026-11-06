import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import * as http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import {
  generateSimulationScript,
  simulationSubagent
} from '../src/simulation_subagent.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../..');

const CHILD_HTML5_BUNDLE_MAX_BYTES = 20971520; // 20 MiB strict ceiling

function resolveBrowserExecutable() {
  const envVars = ['CHROME_PATH', 'CHROME_BIN', 'PUPPETEER_EXECUTABLE_PATH', 'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', 'BROWSER_PATH'];
  for (const v of envVars) {
    if (process.env[v] && fs.existsSync(process.env[v])) return process.env[v];
  }
  const localAppData = process.env.LOCALAPPDATA || '';
  if (localAppData) {
    const pwDir = path.join(localAppData, 'ms-playwright');
    if (fs.existsSync(pwDir)) {
      try {
        const dirs = fs.readdirSync(pwDir).filter(d => d.startsWith('chromium-')).sort().reverse();
        for (const d of dirs) {
          const p1 = path.join(pwDir, d, 'chrome-win64', 'chrome.exe');
          if (fs.existsSync(p1)) return p1;
          const p2 = path.join(pwDir, d, 'chrome-win', 'chrome.exe');
          if (fs.existsSync(p2)) return p2;
        }
      } catch (_) {}
    }
  }
  const standardPaths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    localAppData ? path.join(localAppData, 'Google', 'Chrome', 'Application', 'chrome.exe') : '',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium'
  ].filter(Boolean);
  for (const sp of standardPaths) {
    if (fs.existsSync(sp)) return sp;
  }
  return null;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(new Error(`Failed to parse: ${data}`)); }
      });
    }).on('error', reject);
  });
}

class HeadlessCDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 1;
    this.callbacks = new Map();
    this.events = [];
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(msg.error);
        else resolve(msg.result);
      } else if (msg.method) {
        this.events.push(msg);
      }
    };
  }

  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    if (this.ws) {
      try { this.ws.close(); } catch (_) {}
    }
  }
}

function generateCompleteStandaloneHtml(spec) {
  const scriptContent = generateSimulationScript(spec);
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${spec.title}</title>
  <style>
    body {
      margin: 0;
      padding: 16px;
      font-family: system-ui, -apple-system, sans-serif;
      background: #f1f5f9;
    }
  </style>
</head>
<body>
  <aasha-sim></aasha-sim>
  <script>
${scriptContent}
  </script>
</body>
</html>`;
}

test('Batch C Byte Footprint: Standalone HTML5 bundle complies with strict 20 MiB scope-locked ceiling', async () => {
  const gnomonResult = await simulationSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml',
  });
  assert.strictEqual(gnomonResult.success, true);

  const standaloneHtml = generateCompleteStandaloneHtml(gnomonResult.simulationSpec);
  const bundleSizeBytes = Buffer.byteLength(standaloneHtml, 'utf-8');

  // Assert strictly under 20 MiB ceiling
  assert.ok(bundleSizeBytes < CHILD_HTML5_BUNDLE_MAX_BYTES, `Bundle size ${bundleSizeBytes} must be < ${CHILD_HTML5_BUNDLE_MAX_BYTES}`);
  assert.ok(bundleSizeBytes < 100000, `Lightweight bundle ${bundleSizeBytes} must be < 100 KB`);

  // Assert zero external URLs in generated standalone HTML bundle
  assert.strictEqual(standaloneHtml.includes('http://'), false, 'Zero http:// external links allowed');
  assert.strictEqual(standaloneHtml.includes('https://'), false, 'Zero https:// external links allowed');
});

test('Batch C Headless Chrome CDP: Touch targets >= 44x44px and offline execution', async () => {
  const browserPath = resolveBrowserExecutable();
  if (!browserPath) {
    console.log('[SKIP] No Chromium/Edge executable found on system. Skipping live browser CDP test.');
    return;
  }

  // Create temporary standalone bundle
  const spec = {
    id: 'sim_cdp_live_test',
    title: 'CDP Live Verification',
    modelType: 'SquareGnomonModel',
    initialState: { side: 5 }
  };
  const htmlContent = generateCompleteStandaloneHtml(spec);
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aasha-sim-cdp-'));
  const htmlPath = path.join(tempDir, 'index.html');
  fs.writeFileSync(htmlPath, htmlContent, 'utf-8');

  const fileUrl = `file:///${htmlPath.replace(/\\/g, '/')}`;
  const cdpPort = 9223;
  const userDataDir = path.join(tempDir, 'user-data');
  fs.mkdirSync(userDataDir, { recursive: true });

  const chromeProc = spawn(browserPath, [
    `--remote-debugging-port=${cdpPort}`,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    `--user-data-dir=${userDataDir}`,
    fileUrl
  ], { stdio: 'ignore' });

  let client = null;
  try {
    // Wait for CDP server to bind
    let connected = false;
    for (let i = 0; i < 20; i++) {
      await sleep(250);
      try {
        const pages = await fetchJson(`http://localhost:${cdpPort}/json/list`);
        const targetPage = pages.find(p => p.type === 'page');
        if (targetPage && targetPage.webSocketDebuggerUrl) {
          client = new HeadlessCDPClient(targetPage.webSocketDebuggerUrl);
          await client.connect();
          connected = true;
          break;
        }
      } catch (_) {}
    }

    assert.strictEqual(connected, true, 'Headless Chrome CDP WebSocket connection established');

    // 1. Enable domains
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Network.enable');

    // 2. Emulate strictly OFFLINE network condition
    await client.send('Network.emulateNetworkConditions', {
      offline: true,
      latency: 0,
      downloadThroughput: 0,
      uploadThroughput: 0
    });

    // 3. Emulate mobile viewport (390x844 CSS px)
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true
    });

    await sleep(500);

    // 4. Measure getBoundingClientRect() across all interactive buttons and inputs
    const measurementResult = await client.send('Runtime.evaluate', {
      expression: `
        (() => {
          const sim = document.querySelector('aasha-sim');
          const root = sim ? (sim.shadowRoot || sim) : document;
          const interactiveElements = Array.from(root.querySelectorAll('button, input, select, textarea, [role="button"], .btn-touch, .slider-touch'));

          const measurements = interactiveElements.map(el => {
            const rect = el.getBoundingClientRect();
            return {
              id: el.id,
              tag: el.tagName.toLowerCase(),
              width: Math.round(rect.width * 10) / 10,
              height: Math.round(rect.height * 10) / 10,
              classes: el.className
            };
          });

          return {
            totalControls: measurements.length,
            measurements
          };
        })()
      `,
      returnByValue: true
    });

    const data = measurementResult.result.value;
    assert.ok(data.totalControls >= 5, `Must find at least 5 controls, found ${data.totalControls}`);

    // Assert every interactive touch target satisfies >= 44x44 CSS pixels
    for (const ctrl of data.measurements) {
      assert.ok(
        ctrl.width >= 44,
        `Control #${ctrl.id || ctrl.tag} width (${ctrl.width}px) is less than required 44px`
      );
      assert.ok(
        ctrl.height >= 44,
        `Control #${ctrl.id || ctrl.tag} height (${ctrl.height}px) is less than required 44px`
      );
    }
  } finally {
    if (client) client.close();
    chromeProc.kill('SIGKILL');
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (_) {}
  }
});
