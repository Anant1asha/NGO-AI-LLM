# Suggested Commands

## Chapter & Contract CLI
- Initialize Chapter Contract: `npm run chapter:init -- <Subject> <Class> <Topic>`
- Match Foundations: `npm run admin:match -- <Subject> <Class> <Topic>`
- Rule Parity & Schema Audit: `npm run lint:superbrain` (validates 1:1 cross-IDE parity and verifies 0 `!!seq` arrays in `.agents/rules/*.md`)
- Graphify Update (AST): `graphify update .`
- Graphify Query: `graphify query "<question>"`

## Benchmarks & Certification
- QA L-Truth Benchmark: `node benchmarks/qa_ltruth_benchmark.js`
- Automated Browser CDP Audit: `node automated_browser_verification.js`
- CI Workflow Linter & Sanitizer: `npm run lint:workflows`

## Autonomous Scaling & Cloud Execution
- Check Infinity Hub Status: `npm run infinity:status`
- Launch Cloud Codespace Runner: `npm run infinity:launch`
- Run Cloud Dispatch Engine: `npm run infinity:cloud`
- Continuous Engineering Loop: `node scripts/aasha_continuous_loop.mjs --once`

## Windows / PowerShell Notes
- Use verbatim here-strings (`@' ... '@ | Set-Content -Encoding UTF8`) for PowerShell file creation with backticks or LaTeX.
- Avoid raw destructive shell commands (`Remove-Item`, `rm -rf`) without verification.
