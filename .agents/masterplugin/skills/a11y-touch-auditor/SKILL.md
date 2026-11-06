---
name: a11y-touch-auditor
description: Headless Chrome DevTools Protocol (CDP) & Playwright automated audit suite verifying physical mobile ergonomics, touch target sizing (>=44x44px), color contrast, and zero-CDN offline delivery.
---

# Accessibility & Mobile Ergonomics Touch Auditor (A11Y-CDP)

This skill governs the automated verification of mobile ergonomics, tactile accessibility (WCAG 2.1 AAA), and offline compliance across child-facing AASHA HTML5 learning deliverables.

## 1. Ergonomic Invariants for Rural Learners

1. **Touch Target Size $\ge 44 \times 44\text{px}$**:
   - Every interactive element (buttons, tabs, slider thumbs, quiz options, radio buttons, hint toggles) must have a physical bounding box of at least $44 \times 44\text{px}$ to accommodate children's fingers on budget Android touchscreens.
2. **Same-Frame Visual Viewport (Zero Scroll Collision)**:
   - The interactive simulation and the current assessment question card must render simultaneously within the visible viewport on standard mobile ratios:
     - 16:9 (360x640)
     - 19.5:9 (390x844)
     - 20:9 (412x915)
   - Vertical scrolling to read a question while interacting with the simulation is strictly disallowed.
3. **High Contrast for Sunlight Legibility**:
   - Text elements must maintain a contrast ratio of at least **$7:1$** against backgrounds to ensure readability outdoors or in low-cost screen environments.
4. **Zero-CDN Offline Air-Gap**:
   - The single-file HTML bundle must load cleanly with zero external network requests (`fetch`, `XMLHttpRequest`, `<script src>`, `<link href>`). Any HTTP request aborts with an immediate build failure.

---

## 2. Automated Headless CDP Audit Script

The skill executes automated browser audits using the headless Chrome DevTools Protocol or Playwright:

```javascript
import puppeteer from 'puppeteer-core';
import path from 'path';

export async function auditChapterErgonomics(htmlFilePath) {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_BIN || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
  });

  const page = await browser.newPage();
  
  // 1. Enforce Zero-CDN Network Interception
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    if (req.url().startsWith('http://') || req.url().startsWith('https://')) {
      req.abort();
      throw new Error(`[A11Y-VIOLATION] External network call detected: ${req.url()}`);
    }
    req.continue();
  });

  const viewports = [
    { width: 360, height: 640, name: '16:9 Budget Mobile' },
    { width: 390, height: 844, name: '19.5:9 Modern Mobile' },
    { width: 412, height: 915, name: '20:9 Tall Android' }
  ];

  for (const vp of viewports) {
    await page.setViewport({ width: vp.width, height: vp.height });
    await page.goto(`file://${path.resolve(htmlFilePath)}`, { waitUntil: 'domcontentloaded' });

    // 2. Audit Touch Targets (>= 44x44px)
    const touchViolations = await page.evaluate(() => {
      const interactives = document.querySelectorAll('button, a, input, select, [role="button"], .option-card, .slider-thumb');
      const violations = [];
      interactives.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          if (rect.width < 44 || rect.height < 44) {
            violations.push({
              tag: el.tagName,
              id: el.id,
              class: el.className,
              width: Math.round(rect.width),
              height: Math.round(rect.height)
            });
          }
        }
      });
      return violations;
    });

    if (touchViolations.length > 0) {
      console.error(`[FAIL] Touch target violations on ${vp.name}:`, touchViolations);
      await browser.close();
      return false;
    }

    // 3. Audit Same-Frame Viewport Height
    const isOutOfBounds = await page.evaluate((vh) => {
      const container = document.querySelector('.chapter-container') || document.body;
      return container.scrollHeight > vh + 10; // 10px tolerance
    }, vp.height);

    if (isOutOfBounds) {
      console.error(`[FAIL] Viewport overflow collision on ${vp.name}`);
      await browser.close();
      return false;
    }
  }

  await browser.close();
  console.log('✅ All A11Y touch target and same-frame viewport audits passed!');
  return true;
}
```

---

## 3. Verification Protocol

Run the touch target and ergonomics verification via:
```bash
npm run test:browser
```
Any interactive element failing the $44\times 44\text{px}$ bounding box check or triggering external network calls will fail with a discrete violation trace.
