#!/usr/bin/env node
/**
 * AASHA AIOS — Unified Root Browser Verification Runner
 * Bridges directly to Aasha-AI/scripts/automated_browser_verification.js
 */
const path = require('path');
const target = path.resolve(__dirname, '../Aasha-AI/scripts/automated_browser_verification.js');
require(target);
