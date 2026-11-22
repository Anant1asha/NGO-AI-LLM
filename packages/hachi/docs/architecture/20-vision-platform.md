# 20 — Vision Platform

> Phase 2 / Gate B. Initiative **G**. **Depends on B** ([15](15-model-routing.md)) — it is the
> first consumer of capability routing. Seams are `file:line`.

## 1. Problem

`view_image` (`tools/vision_tools.py:97`) loads/resizes an image and formats a provider-aware
block, but it uses the **session model** (`vision_tools.py:222-239`): if that model lacks vision,
the image is sent anyway and rejected, or a plaintext fallback is returned. The brief's headline
G requirement is the opposite: **vision work must never fail for lack of vision** — auto-route to
a vision-capable model and fold the result back.

## 2. Contract

No new provider type — vision is an **LLM capability**, so it rides the model router:

```python
# capability metadata already on the descriptor (14):
ModelDescriptor(..., capabilities={..., Capability.VISION})

# the router resolves a vision client regardless of the session model:
resolved = router.select(Capability.VISION, RouteConstraints(needs_vision=True))
answer   = resolved.client.generate(messages_with_image_block)
```

`BaseLLMClient` gains an optional `supports_vision` property (derived from the descriptor) so
callers can check without string-matching `provider_kind`.

## 3. The auto-route flow (the G fix)

```
view_image(path|url):
  1. load + permission-gate + SSRF-validate + Pillow-resize  (unchanged, vision_tools.py:64-203)
  2. build the image block
  3. IF session model has VISION → inline (today's fast path, no extra call)
     ELSE → router.select(VISION): send {image + question} to the vision model,
            return its textual analysis folded back into the turn as the tool result
  4. IF no vision model is configured anywhere → today's graceful text fallback
     (vision_tools.py:235), now with a clear "configure a vision model to enable analysis" hint
```

The main reasoning model stays in control of the turn; the vision model is a *capability call*,
not a takeover — mirroring how a sub-agent returns a report. The routed call is a
`ResilientClient`, so a vision-provider blip falls back per the chain.

## 4. One implementation

Reuse the existing `view_image` machinery; add the router branch. With Anthropic Opus (vision) as
the session model, step 3 is inline (zero change). With Haiku (no vision) as the session model and
a configured `vision` candidate (e.g. `gpt-4o` or Opus), step 3 routes — **the exact scenario
that fails today now works.**

## 5. What it touches

`tools/vision_tools.py:97,222` (router branch; drop the `provider_kind` string gate in favor of
descriptor capability); `core/llm.py:106` (`supports_vision` from descriptor);
`gateway/orchestrator.py` (`BootDeps` already gains `router` from [15](15-model-routing.md));
`core/settings.py` (`[routing.capabilities].vision` candidates). No new package.

## 6. What could break (and the guard)

- **Behavior improves where it used to fail** (a change). *Guard:* E2E — Haiku session +
  `view_image` + configured vision candidate → routed and analyzed; no candidate → graceful
  fallback (today's behavior); Opus session → inline (no extra call). All three asserted.
- **Extra cost/latency for the routed call.** *Guard:* only incurred when the session model lacks
  vision *and* a candidate is configured; the routed call is cost-tracked and attributed.
- **Image-block format differences across providers.** *Guard:* the existing provider-aware
  formatting (`vision_tools.py:248-272`) is retained per resolved provider; covered by format
  tests for Anthropic vs OpenAI-compat blocks.

## 7. Deferred (seam only, per §4a)

Dedicated vision pipelines (OCR, document/diagram structure parsing), multi-image reasoning depth,
screenshot-understanding flows. Each is a new tool or extractor on top of the capability-routed
vision client — no router or contract change.
