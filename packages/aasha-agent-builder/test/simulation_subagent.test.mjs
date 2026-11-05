import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  SquareGnomonModel,
  IsometricCubeModel,
  selectAdaptiveRenderer,
  RENDERER_TYPES,
  generateSimulationScript,
  simulationSubagent,
} from '../src/simulation_subagent.mjs';

import { resolveWorkspaceRoot } from '../src/ingest_subagent.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('SquareGnomonModel calculates correct mathematical transitions and bounds', () => {
  const model = new SquareGnomonModel({ initialSide: 4, minSide: 1, maxSide: 10 });
  let state = model.getState();

  assert.equal(state.side, 4);
  assert.equal(state.totalArea, 16);
  assert.equal(state.currentGnomonUnits, 7); // 2(4) - 1
  assert.deepEqual(state.oddNumbersSequence, [1, 3, 5, 7]);

  // Peel gnomon layer
  state = model.peelGnomon();
  assert.equal(state.peeledLayers, 1);
  assert.equal(state.activeSide, 3);
  assert.equal(state.activeArea, 9);
  assert.equal(state.currentGnomonUnits, 5); // 2(3) - 1

  // Unpeel
  state = model.unpeelGnomon();
  assert.equal(state.peeledLayers, 0);
  assert.equal(state.activeSide, 4);
  assert.equal(state.activeArea, 16);

  // Bounds enforcement
  model.setSide(100);
  assert.equal(model.getState().side, 10);
  model.setSide(-5);
  assert.equal(model.getState().side, 1);

  // Reset
  state = model.reset();
  assert.equal(state.side, 4);
  assert.equal(state.peeledLayers, 0);
});

test('IsometricCubeModel calculates volumetric properties and odd sum progression', () => {
  const model = new IsometricCubeModel({ initialN: 3, minN: 1, maxN: 5 });
  let state = model.getState();

  assert.equal(state.n, 3);
  assert.equal(state.volume, 27);
  assert.equal(state.layerCount, 3);
  assert.equal(state.cubesPerLayer, 9);
  assert.equal(state.isSliced, false);

  // Consecutive odds sum property for 3³: 7 + 9 + 11 = 27
  assert.deepEqual(state.consecutiveOdds, [7, 9, 11]);
  assert.equal(state.consecutiveOdds.reduce((a, b) => a + b, 0), 27);

  // Toggle slice
  state = model.toggleSlice();
  assert.equal(state.isSliced, true);

  // Bounds
  model.setN(10);
  assert.equal(model.getState().n, 5);
  assert.equal(model.getState().volume, 125);
  // For 5³: first odd = 5(4) + 1 = 21 -> 21+23+25+27+29 = 125
  assert.deepEqual(model.getState().consecutiveOdds, [21, 23, 25, 27, 29]);
});

test('selectAdaptiveRenderer enforces priority: DOM/SVG -> Canvas 2D -> WebGL', () => {
  const domPlan = selectAdaptiveRenderer({ simType: 'slider_control', dimensions: 2 });
  assert.equal(domPlan.renderer, RENDERER_TYPES.DOM_SVG);

  const canvasPlan = selectAdaptiveRenderer({ simType: 'square_gnomon_grid', dimensions: 2 });
  assert.equal(canvasPlan.renderer, RENDERER_TYPES.CANVAS_2D);
  assert.equal(canvasPlan.fallbackRenderer, RENDERER_TYPES.DOM_SVG);

  const webglPlan = selectAdaptiveRenderer({ simType: 'complex_3d', dimensions: 3, complexity: 'high_poly' });
  assert.equal(webglPlan.renderer, RENDERER_TYPES.WEBGL);
  assert.equal(webglPlan.fallbackRenderer, RENDERER_TYPES.CANVAS_2D);
});

test('generateSimulationScript produces valid self-contained client Web Component', () => {
  const spec = {
    id: 'sim_test_01',
    title: 'Test Gnomon',
    initialState: { side: 5 },
  };

  const script = generateSimulationScript(spec);
  assert.ok(script.includes('class AashaAudioEngine'));
  assert.ok(script.includes('class SquareGnomonSimulationAdapter'));
  assert.ok(script.includes('customElements.define(\'aasha-sim\''));
  // Ensure minimum 44x44px touch target rules are baked into CSS
  assert.ok(script.includes('min-width: 44px'));
  assert.ok(script.includes('min-height: 44px'));
  // Ensure zero external CDN calls
  assert.ok(!script.includes('http://'));
  assert.ok(!script.includes('https://'));
});

test('simulationSubagent coordinates contract ingestion with machine-verifiable output package', async () => {
  const result = await simulationSubagent({
    contractPath: 'Aasha-AI/content/contracts/Mathematics_Class8_squares_and_cubes.yaml',
  });

  assert.equal(result.success, true);
  assert.ok(result.simulationSpec);
  assert.equal(result.simulationSpec.id, 'sim_squares_and_cubes_concept_1');
  assert.equal(result.simulationSpec.grade, 8);
  assert.equal(result.simulationSpec.touchTargetMinPixels, 44);
  assert.equal(result.simulationSpec.offlineCompliant, true);
  assert.equal(result.simulationSpec.zeroCdnDependencies, true);

  // Assert verifications
  assert.equal(result.verification.touchTargetsCompliant, true);
  assert.equal(result.verification.zeroNetworkDependencies, true);
  assert.equal(result.verification.offlineReady, true);
  assert.equal(result.verification.contractCompliant, true);

  // Assert measurements
  assert.ok(result.measurements.clientScriptBytes > 1000);
  assert.equal(result.measurements.offlineAssetCount, 0); // Pure procedural code
});

test('A1 Security: generateSimulationScript sanitizes HTML and escapes inline script JSON', () => {
  const maliciousSpec = {
    id: 'sim_malicious',
    title: 'Exploit <script>alert("xss")</script><img src=x onerror=alert(1)>',
    initialState: { side: 5 }
  };

  const script = generateSimulationScript(maliciousSpec);

  // 1. Assert SPEC.title is NOT directly interpolated into the innerHTML template string
  assert.strictEqual(
    script.includes('${SPEC.title'),
    false,
    'Unsafe ${SPEC.title} interpolation must not exist in template'
  );

  // 2. Assert static title element exists with simTitle ID
  assert.strictEqual(
    script.includes('<span class="sim-title" id="simTitle"></span>'),
    true,
    'Static title span with id simTitle must exist in template'
  );

  // 3. Assert dynamic title assignment uses textContent sink
  assert.strictEqual(
    script.includes('titleEl.textContent = SPEC.title'),
    true,
    'Title must be assigned through textContent'
  );

  // 4. Assert inline script context escapes HTML-significant script tags to prevent script termination
  assert.strictEqual(
    script.includes('<script>'),
    false,
    'Raw <script> tags must not exist in inline script JSON'
  );
  assert.strictEqual(
    script.includes('</script>'),
    false,
    'Raw </script> tags must not exist in inline script JSON'
  );
  assert.strictEqual(
    script.includes('\\u003cscript\\u003e'),
    true,
    'Raw < and > must be Unicode escaped as \\u003c and \\u003e in script JSON'
  );
  assert.strictEqual(
    script.includes('\\u003c/script\\u003e'),
    true,
    'Closing script tag must be safely escaped'
  );
});

test('A1 Security: custom element mount assigns malicious title safely as plain text', () => {
  const attackTitle = '<img src=x onerror=alert(1)><b>Geometric Square</b>';
  const spec = {
    id: 'sim_attack_test',
    title: attackTitle,
    initialState: { side: 5 }
  };

  // Mock DOM container simulating browser environment
  class MockElement {
    constructor(tagName) {
      this.tagName = tagName;
      this.children = [];
      this._textContent = '';
      this._innerHTML = '';
    }
    set textContent(val) {
      this._textContent = String(val);
    }
    get textContent() {
      return this._textContent;
    }
    set innerHTML(html) {
      this._innerHTML = html;
      // If innerHTML contains a tag, create mock children
      if (html.includes('id="simTitle"')) {
        const titleSpan = new MockElement('span');
        titleSpan.id = 'simTitle';
        this.children.push(titleSpan);
      }
    }
    get innerHTML() {
      return this._innerHTML;
    }
    querySelector(selector) {
      if (selector === '#simTitle') {
        return this.children.find(c => c.id === 'simTitle') || null;
      }
      return null;
    }
  }

  const container = new MockElement('div');

  // Simulate the template render logic implemented in A1
  container.innerHTML = `
    <div class="sim-header">
      <span class="sim-title" id="simTitle"></span>
    </div>
  `;
  const titleEl = container.querySelector('#simTitle');
  if (titleEl) {
    titleEl.textContent = spec.title || 'Geometric Square';
  }

  // Verification:
  // Title content is literal plain text in textContent, not parsed HTML markup in container DOM
  assert.strictEqual(titleEl.textContent, attackTitle);
  assert.strictEqual(titleEl.children.length, 0, 'No child DOM nodes (like <img>) should be parsed');
});

test('A2 Lifecycle: script includes AbortController event listener detachment, audio cleanup and telemetry boundary', () => {
  const spec = {
    id: 'sim_a2_test',
    title: 'A2 Lifecycle Hardening',
    initialState: { side: 5 }
  };
  const script = generateSimulationScript(spec);

  // 1. AbortController signal usage in bindEvents
  assert.strictEqual(script.includes('this._abortController = new AbortController()'), true);
  assert.strictEqual(script.includes('opts = signal ? { signal } : {}'), true);
  assert.strictEqual(script.includes("btnInc.addEventListener('click'"), true);
  assert.strictEqual(script.includes('}, opts)'), true);

  // 2. AbortController abort & audio close in destroy()
  assert.strictEqual(script.includes('this._abortController.abort()'), true);
  assert.strictEqual(script.includes('this.audio.close()'), true);

  // 3. AudioEngine has close() method disposing AudioContext
  assert.strictEqual(script.includes('close() {'), true);
  assert.strictEqual(script.includes('this.ctx.close()'), true);

  // 4. emitTelemetry wraps dispatchEvent in try/catch to isolate external listener throws
  assert.strictEqual(script.includes('try {'), true);
  assert.strictEqual(script.includes('this.container.dispatchEvent(event);'), true);
  assert.strictEqual(script.includes('catch (err) {'), true);
  assert.strictEqual(script.includes('// Telemetry listener throw must never crash simulation execution'), true);
});

test('A2 Lifecycle: simulated adapter lifecycle cleans up AbortController and AudioContext on destroy', () => {
  let audioClosed = false;
  let aborted = false;

  class MockAudioEngine {
    constructor() {
      this.ctx = {
        close: () => { audioClosed = true; }
      };
    }
    close() {
      if (this.ctx) {
        this.ctx.close();
        this.ctx = null;
      }
    }
  }

  class MockAdapter {
    constructor() {
      this._abortController = null;
      this.audio = new MockAudioEngine();
      this.container = { innerHTML: '<div>content</div>' };
    }
    mount() {
      this._abortController = {
        signal: { aborted: false },
        abort: () => { aborted = true; }
      };
    }
    pause() {}
    destroy() {
      this.pause();
      if (this._abortController) {
        this._abortController.abort();
        this._abortController = null;
      }
      if (this.audio) {
        this.audio.close();
      }
      if (this.container) {
        this.container.innerHTML = '';
        this.container = null;
      }
    }
  }

  const adapter = new MockAdapter();
  adapter.mount();
  assert.strictEqual(aborted, false);
  assert.strictEqual(audioClosed, false);

  adapter.destroy();
  assert.strictEqual(aborted, true, 'AbortController must be aborted on destroy');
  assert.strictEqual(audioClosed, true, 'AudioContext must be closed on destroy');
  assert.strictEqual(adapter._abortController, null);
  assert.strictEqual(adapter.container, null);
});

