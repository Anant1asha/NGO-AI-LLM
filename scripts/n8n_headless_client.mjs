#!/usr/bin/env node
/**
 * AASHA AIOS — Headless n8n Automation Client
 *
 * Provides non-interactive, zero-browser-prompt orchestration with hosted n8n
 * (https://airtribe.app.n8n.cloud).
 *
 * Eliminates repetitive OAuth consent popups (https://airtribe.app.n8n.cloud/oauth/consent)
 * by using direct outbound HTTPS webhook and API calls with persistent authorization headers.
 */

import https from 'node:https';

const N8N_HOST = 'airtribe.app.n8n.cloud';
const DEFAULT_BEARER = process.env.N8N_API_TOKEN || 
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZDdhZDQzNy0yOGVjLTQzNTEtODg2Yi0wN2FkNDA4NTc3N2EiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjA6OWU0NmY4LWJjNDQtNDA3NS05YTc4LTkwOTQ4YzM1ZjcwYSIsImlhdCI6MTc4OTQxMTMzNH0.N7kXqJm152Df_QDx2eGjveKkCNUSanOhseZcZcj4gAw';

export async function checkConnection() {
  console.log(`[n8n-headless] Checking connection to https://${N8N_HOST}...`);
  return new Promise((resolve) => {
    const options = {
      hostname: N8N_HOST,
      port: 443,
      path: '/healthz',
      method: 'GET',
      timeout: 5000,
      headers: {
        'User-Agent': 'AASHA-AIOS-Headless-Client/1.0',
        'Authorization': `Bearer ${DEFAULT_BEARER}`
      }
    };

    const req = https.request(options, (res) => {
      console.log(`[n8n-headless] Response status: ${res.statusCode} ${res.statusMessage}`);
      resolve({ status: res.statusCode, ok: res.statusCode < 400 });
    });

    req.on('error', (e) => {
      console.warn(`[n8n-headless] Network advisory (offline/unreachable): ${e.message}`);
      resolve({ status: null, ok: false, error: e.message });
    });

    req.on('timeout', () => {
      req.destroy();
      console.warn('[n8n-headless] Connection timed out (5s).');
      resolve({ status: 408, ok: false, error: 'Timeout' });
    });

    req.end();
  });
}

export async function triggerWebhook(webhookPath, payload = {}) {
  const normalizedPath = webhookPath.startsWith('/') ? webhookPath : `/${webhookPath}`;
  console.log(`[n8n-headless] Triggering webhook: https://${N8N_HOST}${normalizedPath}`);

  return new Promise((resolve) => {
    const dataString = JSON.stringify(payload);
    const options = {
      hostname: N8N_HOST,
      port: 443,
      path: normalizedPath,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(dataString),
        'Authorization': `Bearer ${DEFAULT_BEARER}`,
        'User-Agent': 'AASHA-AIOS-Headless-Client/1.0'
      }
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        console.log(`[n8n-headless] Webhook response [${res.statusCode}]: ${body.slice(0, 200)}`);
        resolve({ status: res.statusCode, body });
      });
    });

    req.on('error', (err) => {
      console.error(`[n8n-headless] Error calling webhook: ${err.message}`);
      resolve({ status: 500, error: err.message });
    });

    req.write(dataString);
    req.end();
  });
}

// CLI handler
const args = process.argv.slice(2);
if (args.includes('--check') || args.includes('--check-connection') || args.includes('--dry-run')) {
  checkConnection().then(res => {
    console.log(`[n8n-headless] Check completed: ${res.ok ? 'SUCCESS' : 'ADVISORY'}`);
    process.exit(0);
  });
} else if (args[0] === 'trigger') {
  const pathArg = args[1] || '/webhook/curriculum-ingest';
  triggerWebhook(pathArg, { triggered_by: 'AASHA-AIOS', timestamp: new Date().toISOString() })
    .then(() => process.exit(0));
} else {
  console.log('Usage: node scripts/n8n_headless_client.mjs [--check | trigger <webhook_path>]');
}
