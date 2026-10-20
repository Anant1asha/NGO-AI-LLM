#!/usr/bin/env node
/**
 * AASHA AIOS — Laya System 1 Default Environment Setup
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const classifierPath = path.join(repoRoot, 'Aasha-AI', 'scripts', 'laya_task_classifier.py');

if (fs.existsSync(classifierPath)) {
  console.log(`[PASS] Laya System 1 Task Classifier located at: ${classifierPath}`);
  console.log('Zero-token Indic script isolation and pre-routing ready.');
} else {
  console.warn(`[WARN] Laya classifier not found at ${classifierPath}`);
}
