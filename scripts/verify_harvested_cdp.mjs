/**
 * AASHA AIOS — Headless Chrome CDP Verification for 5 Newly Harvested Foundations
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const NEW_AVRS = [
  'AVR-P407-candle-flame-thermal-convection.html',
  'AVR-P408-biochemical-dropper-assay-lab.html',
  'AVR-P409-balance-scale-linear-equations.html',
  'AVR-P410-mendelian-genetics-punnett-matrix.html',
  'AVR-P411-fraction-pizza-and-3d-blocks.html',
];

function resolveBrowserBinary() {
  const custom = process.env.PLAYWRIGHT_CHROME_PATH || process.env.CHROME_BIN;
  if (custom && fs.existsSync(custom)) return custom;
  const localAppData = process.env.LOCALAPPDATA || '';
  const pwRoot = path.join(localAppData, 'ms-playwright');
  if (fs.existsSync(pwRoot)) {
    const entries = fs.readdirSync(pwRoot).sort().reverse();
    for (const ent of entries) {
      if (ent.startsWith('chromium-')) {
        const bin = path.join(pwRoot, ent, 'chrome-win64', 'chrome.exe');
        if (fs.existsSync(bin)) return bin;
      }
    }
  }
  return null;
}

class HeadlessCDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 1;
    this.callbacks = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((res, rej) => {
      this.ws.onopen = res;
      this.ws.onerror = rej;
    });
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(msg.error);
        else resolve(msg.result);
      }
    };
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const callId = this.id++;
      this.callbacks.set(callId, { resolve, reject });
      this.ws.send(JSON.stringify({ id: callId, method, params }));
    });
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

async function auditAvr(filename) {
  const browserBin = resolveBrowserBinary();
  const filePath = path.resolve(`assets/cdn/interactives/${filename}`);
  const fileStat = fs.statSync(filePath);
  const fileUrl = pathToFileURL(filePath).href;
  const cdpPort = 9240 + Math.floor(Math.random() * 50);
  const userDataDir = path.join(process.env.TEMP || '.', `cdp_avr_test_${Date.now()}_${Math.random()}`);

  const browserProc = spawn(browserBin, [
    `--remote-debugging-port=${cdpPort}`,
    `--user-data-dir=${userDataDir}`,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-extensions',
    fileUrl
  ]);

  let client = null;
  try {
    let wsUrl = null;
    for (let i = 0; i < 30; i++) {
      try {
        const res = await fetch(`http://127.0.0.1:${cdpPort}/json/list`);
        const list = await res.json();
        if (list && list.length > 0 && list[0].webSocketDebuggerUrl) {
          wsUrl = list[0].webSocketDebuggerUrl;
          break;
        }
      } catch (_) {}
      await new Promise(r => setTimeout(r, 200));
    }

    if (!wsUrl) throw new Error("Could not connect to CDP WebSocket.");
    client = new HeadlessCDPClient(wsUrl);
    await client.connect();

    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await new Promise(r => setTimeout(r, 400));

    // 1. Mobile Viewport 390x844
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true
    });

    // 2. Touch Target Ergonomics
    const touchAudit = await client.send('Runtime.evaluate', {
      expression: `(() => {
        const targets = Array.from(document.querySelectorAll("button, input[type=range]"));
        const violations = [];
        for (const t of targets) {
          const rect = t.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            if (rect.height < 44 || rect.width < 44) {
              violations.push({ tag: t.tagName, class: t.className, h: rect.height, w: rect.width });
            }
          }
        }
        return { total: targets.length, violationsCount: violations.length, violations };
      })()`,
      returnByValue: true
    });

    // 3. Canvas 2D & Telemetry Verification
    const canvasAudit = await client.send('Runtime.evaluate', {
      expression: `(() => {
        const c = document.querySelector("canvas");
        const hasAasha = Boolean(window.AASHA && window.__AASHA_EVENTS__);
        const eventsCount = window.__AASHA_EVENTS__ ? window.__AASHA_EVENTS__.length : 0;
        return {
          hasCanvas: Boolean(c && c.width > 0 && c.height > 0),
          hasAasha,
          eventsCount
        };
      })()`,
      returnByValue: true
    });

    return {
      file: filename,
      sizeBytes: fileStat.size,
      touch: touchAudit.result.value,
      canvas: canvasAudit.result.value,
      passed: touchAudit.result.value.violationsCount === 0 && canvasAudit.result.value.hasCanvas && canvasAudit.result.value.hasAasha
    };
  } finally {
    if (client) client.close();
    browserProc.kill();
    try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch (_) {}
  }
}

async function run() {
  console.log("=== AASHA AIOS — CDP Audit of Harvested Visual Foundations ===");
  let allPass = true;
  for (const avr of NEW_AVRS) {
    process.stdout.write(`Auditing [${avr}]... `);
    try {
      const res = await auditAvr(avr);
      if (res.passed) {
        console.log(`PASS (0 touch violations, Canvas 2D Active, ${(res.sizeBytes/1024).toFixed(1)} KB)`);
      } else {
        console.log(`FAIL`);
        allPass = false;
      }
    } catch (err) {
      console.log(`ERROR: ${err.message}`);
      allPass = false;
    }
  }

  console.log(`\nResult: ${allPass ? "100% ALL 5 HARVESTED FOUNDATIONS CERTIFIED" : "SOME FAILED"}`);
}

run();
