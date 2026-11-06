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
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const N8N_HOST = 'airtribe.app.n8n.cloud';

// No literal credential may live in this file (public repo, zero-secret rule).
// Load Aasha-AI/.env so one file configures every n8n entry point; an already
// exported process env var still wins.
const ENV_FILE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', 'Aasha-AI', '.env'
);

export function loadEnvFile(file = ENV_FILE) {
  if (!fs.existsSync(file)) return false;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    const key = m[1];
    if (process.env[key]) continue; // real env wins
    let val = m[2].trim();
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    process.env[key] = val;
  }
  return true;
}

loadEnvFile();

const DEFAULT_BEARER = process.env.N8N_API_TOKEN || '';

// /healthz is a liveness endpoint: it answers 200 even with no credential, so it
// proves reachability only. `authenticated: true` probes a protected API path
// and is the only mode that can fail on a bad or missing token.
export async function checkConnection({ authenticated = false } = {}) {
  if (authenticated && !DEFAULT_BEARER) {
    console.error('[n8n-headless] Cannot verify auth: N8N_API_TOKEN is not set.');
    console.error('[n8n-headless] Set it in the environment or in Aasha-AI/.env.');
    return { status: null, ok: false, error: 'N8N_API_TOKEN missing', authenticated: true };
  }

  const probePath = authenticated ? '/rest/login' : '/healthz';
  console.log(
    `[n8n-headless] Checking ${authenticated ? 'AUTHENTICATED' : 'liveness'} connection ` +
    `to https://${N8N_HOST}${probePath}...`
  );
  return new Promise((resolve) => {
    const options = {
      hostname: N8N_HOST,
      port: 443,
      path: probePath,
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
if (args.includes('--auth')) {
  // Credential-bearing probe: the only mode that can prove the token works.
  checkConnection({ authenticated: true }).then(res => {
    console.log(`[n8n-headless] Auth check: ${res.ok ? 'SUCCESS' : 'FAILED'}`);
    process.exit(res.ok ? 0 : 1);
  });
} else if (args.includes('--check') || args.includes('--check-connection') || args.includes('--dry-run')) {
  // Liveness only. Exit non-zero on unreachable so CI cannot read a green tick
  // from a probe that never touched a credential.
  checkConnection().then(res => {
    console.log(`[n8n-headless] Check completed: ${res.ok ? 'SUCCESS' : 'FAILED'}`);
    process.exit(res.ok ? 0 : 1);
  });
} else if (args[0] === 'trigger') {
  const pathArg = args[1] || '/webhook/curriculum-ingest';
  triggerWebhook(pathArg, { triggered_by: 'AASHA-AIOS', timestamp: new Date().toISOString() })
    .then(() => process.exit(0));
} else {
  console.log('Usage: node scripts/n8n_headless_client.mjs [--check | --auth | trigger <webhook_path>]');
}
