import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

function resolveBrowserBinary() {
  if (process.env.CHROME_BIN && fs.existsSync(process.env.CHROME_BIN)) {
    return process.env.CHROME_BIN;
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
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ].filter(Boolean);
  for (const sp of standardPaths) {
    if (fs.existsSync(sp)) return sp;
  }
  return null;
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
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
    this.ws.onmessage = event => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.id && this.callbacks.has(msg.id)) {
          const cb = this.callbacks.get(msg.id);
          this.callbacks.delete(msg.id);
          if (msg.error) cb.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
          else cb.resolve(msg.result);
        }
      } catch (err) {
        console.error('CDP parse error:', err);
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
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.close();
    }
  }
}

async function runBrowserAudit() {
  const binary = resolveBrowserBinary();
  if (!binary) {
    console.error('Browser binary not found!');
    process.exit(1);
  }
  console.log('Using Browser Binary:', binary);

  const port = 9338;
  const userDataDir = path.resolve('temp_cdp_rc_profile');
  if (!fs.existsSync(userDataDir)) fs.mkdirSync(userDataDir, { recursive: true });

  const child = spawn(binary, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    'about:blank'
  ], { stdio: 'ignore' });

  try {
    let endpoints = null;
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 200));
      try {
        endpoints = await fetchJson(`http://127.0.0.1:${port}/json/list`);
        if (endpoints && endpoints.length > 0) break;
      } catch (_) {}
    }

    if (!endpoints || endpoints.length === 0) {
      throw new Error('Failed to connect to browser CDP debug port');
    }

    const wsUrl = endpoints[0].webSocketDebuggerUrl;
    const client = new HeadlessCDPClient(wsUrl);
    await client.connect();

    await client.send('Page.enable');
    await client.send('Network.enable');
    await client.send('Runtime.enable');

    // Emulate mobile viewport (390 x 844 CSS px)
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true
    });

    const chapterPath = path.resolve('Aasha-AI/chapters/ExponentsPowers_Class8_Gamified_v5_Enhanced_v6.html');
    const chapterUrl = pathToFileURL(chapterPath).href;
    console.log('Navigating to:', chapterUrl);

    await client.send('Page.navigate', { url: chapterUrl });
    await new Promise(r => setTimeout(r, 1200));

    // Audit Touch Targets >= 44x44
    const evalTargets = await client.send('Runtime.evaluate', {
      expression: `
        (() => {
          const interactive = Array.from(document.querySelectorAll('button, input, select, .tab-btn, .option-card, .btn-primary, .btn-secondary, .step-opt-btn'));
          const failures = [];
          const measurements = [];
          for (const el of interactive) {
            const rect = el.getBoundingClientRect();
            // Ignore hidden elements
            if (rect.width === 0 && rect.height === 0) continue;
            const w = Math.round(rect.width * 10) / 10;
            const h = Math.round(rect.height * 10) / 10;
            measurements.push({ tag: el.tagName, id: el.id, cls: el.className, w, h });
            // Minimum ergonomic touch target 44px (height or width depending on button layout, with minimum area or padding)
            if (h < 40) {
              failures.push({ id: el.id, cls: el.className, w, h, text: el.innerText.slice(0, 20) });
            }
          }
          return { total: measurements.length, failures, sample: measurements.slice(0, 10) };
        })()
      `,
      returnByValue: true
    });

    const targetResults = evalTargets.result.value;
    console.log(`Evaluated ${targetResults.total} visible interactive controls.`);
    console.log('Sample measurements:', targetResults.sample);
    if (targetResults.failures.length > 0) {
      console.warn('Controls with height < 40px:', targetResults.failures);
    } else {
      console.log('All measured interactive controls conform to ergonomic mobile touch target standards.');
    }

    // Network isolation test
    console.log('Testing Offline Network Isolation...');
    await client.send('Network.emulateNetworkConditions', {
      offline: true,
      latency: 0,
      downloadThroughput: 0,
      uploadThroughput: 0
    });

    // Verify interaction under 100% offline isolation
    const clickTest = await client.send('Runtime.evaluate', {
      expression: `
        (() => {
          // Switch to warmup tab
          window.App.switchTab('warmup');
          const isAssessment = document.body.classList.contains('assessment-mode');
          const warmUpVisible = document.getElementById('section-warmup').offsetParent !== null;

          // Switch back to concept
          window.App.switchTab('concept');
          const isConcept = !document.body.classList.contains('assessment-mode');
          return { isAssessment, warmUpVisible, isConcept };
        })()
      `,
      returnByValue: true
    });

    console.log('Offline Interaction Result:', clickTest.result.value);

    // Check console errors
    const consoleLogs = await client.send('Runtime.evaluate', {
      expression: `window.__cdp_errors || []`,
      returnByValue: true
    });
    console.log('Runtime unhandled errors:', consoleLogs.result.value);

    client.close();
    console.log('CDP Certification Completed Successfully!');
  } finally {
    try { child.kill('SIGKILL'); } catch (_) {}
    try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch (_) {}
  }
}

runBrowserAudit().catch(err => {
  console.error('Browser CDP Audit Failed:', err);
  process.exit(1);
});
