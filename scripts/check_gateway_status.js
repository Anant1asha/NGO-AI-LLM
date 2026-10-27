/**
 * AASHA Learning Ecosystem — Gateway Status Check
 * Verifies local 9Router connectivity and .env configuration cleanly without inline escaping issues.
 */

const path = require('path');
const http = require('http');
const dotenvPath = path.resolve(__dirname, '../Aasha-AI/.env');
require('../Aasha-AI/node_modules/dotenv').config({ path: dotenvPath });

const baseUrl = process.env.NINEROUTER_BASE_URL || 'http://localhost:20128/v1';
const apiKey = process.env.NINEROUTER_API_KEY;
const isConfigured = Boolean(apiKey);

async function checkGateway() {
  console.log('====================================================');
  console.log('       AASHA 9ROUTER GATEWAY STATUS CHECK           ');
  console.log('====================================================');
  console.log(`- 9Router API Key Configured : ${isConfigured ? '✅ YES' : '❌ NO'}`);
  console.log(`- Base URL                   : ${baseUrl}`);
  console.log(`- Default Provider           : ${process.env.DEFAULT_LLM_PROVIDER || '9router'}`);

  const probeUrl = `${baseUrl.replace(/\/+$/, '')}/models`;
  const start = Date.now();
  let isLive = false;
  let statusText = 'OFFLINE / STANDBY';

  try {
    const res = await new Promise((resolve, reject) => {
      const u = new URL(probeUrl);
      const req = http.request({
        hostname: u.hostname,
        port: u.port || 80,
        path: u.pathname,
        method: 'GET',
        headers: apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {},
        timeout: 2000
      }, resolve);
      req.on('timeout', () => { req.destroy(); reject(new Error('TIMEOUT')); });
      req.on('error', reject);
      req.end();
    });

    const latency = Date.now() - start;
    if (res.statusCode >= 200 && res.statusCode < 400) {
      isLive = true;
      statusText = `ACTIVE (HTTP ${res.statusCode}, ${latency}ms latency)`;
    } else {
      statusText = `RESPONDING (HTTP ${res.statusCode}, ${latency}ms)`;
    }
  } catch (err) {
    statusText = `OFFLINE (${err.message || 'Connection refused'}) -> Direct Tier 1 Fallback Ready`;
  }

  console.log(`- Live Gateway Connectivity  : ${isLive ? '✅ ' : 'ℹ️ '}${statusText}`);
  console.log('====================================================');
  process.exit(0);
}

checkGateway();
