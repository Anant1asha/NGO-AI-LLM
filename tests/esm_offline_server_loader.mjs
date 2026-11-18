// ESM loader hook for offline sandbox testing of Aasha-AI/server/server.js
// Maps fastify, @fastify/cors, and better-sqlite3 to real local HTTP + Python SQLite3 drivers
// when node_modules is absent in offline sandbox.
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const SHIM_DIR = path.dirname(fileURLToPath(import.meta.url));

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'fastify') {
    return { shortCircuit: true, url: pathToFileURL(path.join(SHIM_DIR, 'offline_shims/fastify_http_shim.mjs')).href };
  }
  if (specifier === '@fastify/cors') {
    return { shortCircuit: true, url: pathToFileURL(path.join(SHIM_DIR, 'offline_shims/cors_shim.mjs')).href };
  }
  if (specifier === 'better-sqlite3') {
    return { shortCircuit: true, url: pathToFileURL(path.join(SHIM_DIR, 'offline_shims/better_sqlite3_shim.mjs')).href };
  }
  return nextResolve(specifier, context);
}
