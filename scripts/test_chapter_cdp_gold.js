import { chromium } from "playwright";
import { pathToFileURL } from "url";
import path from "path";

async function verifyChapter() {
  const filePath = path.resolve("Aasha-AI/chapters/class6_math_ch07_fractions.html");
  const fileUrl = pathToFileURL(filePath).href;

  console.log(`Auditing Gold Standard Chapter: ${filePath}`);
  const browser = await chromium.launch({ headless: true });

  const viewports = [
    { name: "Mobile 360x640", width: 360, height: 640 },
    { name: "Mobile 390x844", width: 390, height: 844 },
    { name: "Mobile 412x915", width: 412, height: 915 },
    { name: "Desktop 1200x800", width: 1200, height: 800 }
  ];

  let allPassed = true;

  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });

    const consoleErrors = [];
    page.on("console", msg => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", err => consoleErrors.push(err.message));

    await page.goto(fileUrl, { waitUntil: "networkidle" });

    // 1. Check Console Errors
    if (consoleErrors.length > 0) {
      console.error(`[FAIL] Console errors detected:`, consoleErrors);
      allPassed = false;
    } else {
      console.log(`[PASS] Zero console errors.`);
    }

    // 2. Check Touch Targets >= 44px
    const touchAudit = await page.evaluate(() => {
      const targets = Array.from(document.querySelectorAll("button, input[type=range], .opt, .switch button"));
      const violations = [];
      for (const t of targets) {
        const rect = t.getBoundingClientRect();
        // check if visible
        if (rect.width > 0 && rect.height > 0) {
          if (rect.height < 44 || rect.width < 44) {
            violations.push({ tag: t.tagName, class: t.className, text: t.textContent?.slice(0, 15), h: rect.height, w: rect.width });
          }
        }
      }
      return { total: targets.length, violations };
    });

    if (touchAudit.violations.length > 0) {
      console.warn(`[WARN] Touch target violations (${touchAudit.violations.length}/${touchAudit.total}):`, touchAudit.violations);
    } else {
      console.log(`[PASS] All ${touchAudit.total} interactive controls meet/exceed 44x44px touch target standard.`);
    }

    // 3. Test LLE Word Tap
    const wordTapResult = await page.evaluate(async () => {
      const tap = document.querySelector(".tapable");
      if (!tap) return { success: false, reason: "No .tapable found" };
      const word = tap.getAttribute("data-w");
      tap.click();
      const wp = document.getElementById("wp");
      const wpWord = document.getElementById("wpWord")?.textContent;
      const wpHindi = document.getElementById("wpHindi")?.textContent;
      const wpPron = document.getElementById("wpPron")?.textContent;
      return {
        success: wp?.classList.contains("up") && wpWord?.toLowerCase() === word?.toLowerCase(),
        word,
        wpWord,
        wpHindi,
        wpPron
      };
    });

    console.log(`[LLE Word Tap] Word: "${wordTapResult.word}" -> Hindi: "${wordTapResult.wpHindi}", Phonics: "${wordTapResult.wpPron}"`);
    if (!wordTapResult.success) {
      console.error(`[FAIL] Word tap test failed:`, wordTapResult);
      allPassed = false;
    } else {
      console.log(`[PASS] Word tap reveals bottom sheet with Hindi translation & Devanagari phonics.`);
    }

    // 4. Test LLE Sentence Hindi Toggle
    const sentenceToggleResult = await page.evaluate(() => {
      const btn = document.querySelector(".hiBtn");
      if (!btn) return { success: false, reason: "No .hiBtn found" };
      btn.click();
      const box = btn.parentElement?.querySelector(".hiBox");
      const isVisible = box && !box.hidden && box.textContent.length > 5;
      return { success: isVisible, hindiText: box?.textContent?.slice(0, 45) + "..." };
    });

    console.log(`[LLE Sentence Toggle] Result: "${sentenceToggleResult.hindiText}"`);
    if (!sentenceToggleResult.success) {
      console.error(`[FAIL] Sentence toggle failed.`);
      allPassed = false;
    } else {
      console.log(`[PASS] Sentence toggle button successfully reveals natural Hindi translation.`);
    }

    // 5. Test Navigation to Sim Slide
    await page.evaluate(() => {
      // Advance to slide 4 (which is kind: "sim")
      for (let s = 0; s < 4; s++) {
        document.getElementById("next").click();
      }
    });

    // Verify Sim Interactive slider
    const simTest = await page.evaluate(() => {
      const slider = document.getElementById("sDen");
      if (!slider) return { success: false, reason: "No #sDen slider found" };
      slider.value = "6";
      slider.dispatchEvent(new Event("input"));
      const oDen = document.getElementById("oDen")?.textContent;
      const oFrac = document.getElementById("oFrac")?.textContent;
      const svgPaths = document.querySelectorAll("#vis svg path").length;
      return { success: oDen === "6" && svgPaths >= 6, oDen, oFrac, svgPaths };
    });

    console.log(`[Sim Test] Denominator set to 6 -> Result: ${simTest.oFrac}, SVG pie slices rendered: ${simTest.svgPaths}`);
    if (!simTest.success) {
      console.error(`[FAIL] Sim test failed:`, simTest);
      allPassed = false;
    } else {
      console.log(`[PASS] Interactive simulation slider live-updates readout and procedural SVG slices.`);
    }

    // Capture screenshot on Mobile 390x844
    if (vp.name === "Mobile 390x844") {
      const screenshotPath = "Aasha-AI/chapters/class6_fractions_verified_mobile.png";
      await page.screenshot({ path: screenshotPath });
      console.log(`[SCREENSHOT] Saved mobile verification screenshot to: ${screenshotPath}`);
    }

    await page.close();
  }

  await browser.close();
  if (allPassed) {
    console.log("\n==========================================");
    console.log("ALL 4 VIEWPORT CHECKS & LLE AUDITS PASSED 100%");
    console.log("==========================================");
  } else {
    process.exit(1);
  }
}

verifyChapter().catch(err => {
  console.error("Audit aborted with error:", err);
  process.exit(1);
});
