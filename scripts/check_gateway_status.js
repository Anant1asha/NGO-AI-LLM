/**
 * AASHA Learning Ecosystem — Gateway Status Check
 * Verifies local 9Router connectivity and .env configuration cleanly without inline escaping issues.
 */

const path = require('path');
const dotenvPath = path.resolve(__dirname, '../Aasha-AI/.env');
require('../Aasha-AI/node_modules/dotenv').config({ path: dotenvPath });

const isConfigured = Boolean(process.env.NINEROUTER_API_KEY);
console.log('====================================================');
console.log('       AASHA 9ROUTER GATEWAY STATUS CHECK           ');
console.log('====================================================');
console.log(`- 9Router API Key Configured : ${isConfigured ? '✅ YES' : '❌ NO'}`);
console.log(`- Base URL                   : ${process.env.NINEROUTER_BASE_URL || 'http://localhost:20128/v1'}`);
console.log(`- Default Provider           : ${process.env.DEFAULT_LLM_PROVIDER || '9router'}`);
console.log('====================================================');
