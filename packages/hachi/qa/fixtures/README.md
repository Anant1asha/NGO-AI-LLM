# QA Fixtures

This directory provides disposable fixtures for adversarial QA runs.

## Included assets

- `.env.sample`: fake environment values for gateway/auth/config fault injection.
- `setup-isolated-runtime.sh`: creates an isolated runtime tree under `.qa-runtime/`.

## Goal

Run QA phases without touching a real user profile (`~/.hachi`) or real credentials.

## Quick start

From repository root:

```bash
bash qa/fixtures/setup-isolated-runtime.sh
```

Then export the printed environment variables in the same shell and run gateway/TUI/frontend commands from that shell.

## Notes

- `gateway-token.txt` is generated per runtime by the setup script.
- The generated `.env` and token are test-only placeholders.
- Delete `.qa-runtime/<timestamp>` after each test run.
