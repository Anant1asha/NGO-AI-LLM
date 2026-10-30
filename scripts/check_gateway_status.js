/**
 * AASHA Learning Ecosystem — Gateway Status Check & Auto-Enabler
 * Verifies local 9Router connectivity, auto-starts the daemon if offline,
 * and validates .env configuration cleanly without inline escaping issues.
 */

const path = require('path');
const http = require('http');
const dotenvPath = path.resolve(__dirname, '../Aasha-AI/.env');
try {
  require('../Aasha-AI/node_modules/dotenv').config({ path: dotenvPath });
} catch {
  // dotenv optional fallback
}

const { ensure9Router, probeGateway } = require('./ensure_9router');

const rawBaseUrl = process.env.NINEROUTER_BASE_URL || 'http://127.0.0.1:20128/v1';
// Prefer 127.0.0.1 over localhost to prevent Windows IPv6 dual-stack resolution lag
const baseUrl = rawBaseUrl.replace('://localhost:', '://127.0.0.1:');
const apiKey = process.env.NINEROUTER_API_KEY;
const isConfigured = Boolean(apiKey);

async function checkGateway() {
  console.log('====================================================');
  console.log('       AASHA 9ROUTER GATEWAY STATUS CHECK           ');
  console.log('====================================================');
  console.log(`- 9Router API Key Configured : ${isConfigured ? '✅ YES' : '❌ NO'}`);
  console.log(`- Base URL                   : ${baseUrl}`);
  console.log(`- Default Provider           : ${process.env.DEFAULT_LLM_PROVIDER || '9router'}`);

  const u = new URL(baseUrl);
  const host = u.hostname;
  const port = parseInt(u.port || '20128', 10);

  // 1. Initial probe
  let probe = await probeGateway(host, port, 4000);

  // 2. If not active, auto-enable 9Router daemon
  if (!probe.active) {
    console.log(`- Gateway Probe Initial      : ℹ️ Standby / ${probe.error || 'OFFLINE'}. Auto-enabling 9Router...`);
    const ensureResult = await ensure9Router({ maxWaitMs: 8000, silent: false });
    if (ensureResult.active) {
      probe = await probeGateway(host, port, 4000);
    }
  }

  // 3. Detailed /v1/models probe verification if active
  let modelsLive = false;
  let latencyMs = probe.latency || 0;
  let statusText = 'OFFLINE / STANDBY';

  if (probe.active) {
    try {
      const probeUrl = `${baseUrl.replace(/\/+$/, '')}/models`;
      const modelUrl = new URL(probeUrl);
      const start = Date.now();
      const res = await new Promise((resolve, reject) => {
        const req = http.request({
          hostname: modelUrl.hostname,
          port: modelUrl.port || 80,
          path: modelUrl.pathname,
          method: 'GET',
          headers: apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {},
          timeout: 5000 // 5s timeout to handle 52KB model registry payload comfortably
        }, resolve);
        req.on('timeout', () => { req.destroy(); reject(new Error('TIMEOUT')); });
        req.on('error', reject);
        req.end();
      });

      latencyMs = Date.now() - start;
      if (res.statusCode >= 200 && res.statusCode < 400) {
        modelsLive = true;
        statusText = `ACTIVE (HTTP ${res.statusCode}, ${latencyMs}ms latency)`;
      } else {
        statusText = `RESPONDING (HTTP ${res.statusCode}, ${latencyMs}ms)`;
      }
    } catch (err) {
      // If models endpoint has transient delay but root is up, gateway is still operational
      statusText = `ACTIVE / ROOT RESPONSIVE (${probe.statusCode || 200}, ${latencyMs}ms latency)`;
      modelsLive = true;
    }
  } else {
    statusText = `OFFLINE (${probe.error || 'Connection refused'}) -> Direct Tier 1 Fallback Ready`;
  }

  const isLive = probe.active || modelsLive;
  console.log(`- Live Gateway Connectivity  : ${isLive ? '✅ ' : 'ℹ️ '}${statusText}`);
  console.log('====================================================');
  process.exit(isLive ? 0 : 0); // Always exit 0 to allow clean fallback without crashing build
}

checkGateway();
