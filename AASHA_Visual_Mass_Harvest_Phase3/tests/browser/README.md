# Browser Smoke Harness

Playwright + system Chromium 144.

Procedure:
1. Serve the resources locally.
2. Launch headless Chromium.
3. Load every resource.
4. Verify stage and controls.
5. Trigger one interaction.
6. Inspect `window.__AASHA_EVENTS__`.
7. Verify monotonic event sequence.
8. Record page and console errors.

Certification result:
- 21 resources attempted.
- Chromium executable available.
- Navigation was blocked by the execution environment with `ERR_BLOCKED_BY_ADMINISTRATOR`.
- Browser certification therefore remains NOT_CERTIFIED.
- No browser PASS is claimed.
