# Suggested Commands

## Chapter & Contract CLI
- Initialize Chapter Contract: `npm run chapter:init -- <Subject> <Class> <Topic>`
- Match Foundations: `npm run admin:match -- <Subject> <Class> <Topic>`
- Graphify Update (AST): `graphify update .`
- Graphify Query: `graphify query "<question>"`

## Benchmarks & Certification
- QA L-Truth Benchmark: `node benchmarks/qa_ltruth_benchmark.js`
- Automated Browser CDP Audit: `node automated_browser_verification.js`

## Windows / PowerShell Notes
- Use verbatim here-strings (`@' ... '@ | Set-Content -Encoding UTF8`) for PowerShell file creation with backticks or LaTeX.
- Avoid raw destructive shell commands (`Remove-Item`, `rm -rf`) without verification.
