# 5-Component Handoff Report — Challenger 2 (Delta Route Adversarial Stress Tester)

## 1. Observation
1. **Adversarial Injections & HTTP Methods**:
   - Executed `run_function` on `proj_wDCbCrGwuVqy` with `query: { chapter: "' OR 1=1--" }`: returned HTTP 404 with body `{"error": "chapter_not_found", "requested": "' OR 1=1--", "available": ["c6_fractions", "c7_perimeter_area", "c8_rational_linear"]}` in 9ms.
   - Executed `run_function` with `query: { chapter: "<script>alert(1)</script>" }`: returned HTTP 404 with body `{"error": "chapter_not_found", "requested": "<script>alert(1)</script>", "available": [...]}` in 7ms.
   - Executed `run_function` with `query: { grade: "<script>alert('xss')</script>" }`: returned HTTP 404 with body `{"error": "grade_not_found", "requestedGrade": null, "availableGrades": [6, 7, 8]}` in 8ms.
   - Executed `run_function` with `query: { grade: "99999999999999999999999999999999999999" }`: returned HTTP 404 with `requestedGrade: 1.0e+38` in 9ms.
   - Executed `run_function` with `query: { grade: "-1" }`: returned HTTP 404 with `requestedGrade: -1` in 11ms.
   - Executed `run_function` with `method: "POST"`: returned HTTP 405 with headers `{"allow": "GET"}` and body `{"error": "Method POST not allowed"}` in 8ms.
   - Across all 27 adversarial invocations, zero HTTP 500 internal server errors or unhandled exceptions occurred.
2. **Bandwidth Profiling**:
   - `GET /api/chapters/deltas` (Manifest): 739 bytes minified, 1,842 bytes formatted (10ms).
   - `GET /api/chapters/deltas?grade=6`: 11,850 bytes minified, 42,966 bytes formatted (11ms).
   - `GET /api/chapters/deltas?grade=7`: 11,540 bytes minified, 40,639 bytes formatted (16ms).
   - `GET /api/chapters/deltas?grade=8`: 13,820 bytes minified, 46,184 bytes formatted (18ms).
   - All single-grade payloads remain under the 50 KB mobile hotspot ceiling.
3. **Client Synchronization Emulation (`version=3` vs `v=3`)**:
   - `GET /api/chapters/deltas?chapter=c6_fractions&version=3`: returned HTTP 200 with body `{"chapterId": "c6_fractions", "version": 3, "upToDate": true, "updatedAt": "2026-09-17T03:00:00Z"}` (101 bytes, 8ms).
   - `GET /api/chapters/deltas?grade=6&version=3`: returned HTTP 200 with body `{"grade": 6, "version": 3, "upToDate": true, "updatedAt": "2026-09-17T03:00:00Z"}` (97 bytes, 6ms).
   - `GET /api/chapters/deltas?chapter=c6_fractions&v=3`: returned HTTP 200 with `upToDate: false` and the entire 36,454-byte chapter body (9ms).
   - `GET /api/chapters/deltas?grade=6&v=3`: returned HTTP 200 with `upToDate: false` and the entire 42,966-byte grade payload (8ms).
4. **Code Inspection**:
   - Inspected `api/chapters/deltas.js` lines 1074–1090:
     ```javascript
     const { chapter, grade, version } = req.query || {};
     // ...
     const clientVer = parseInt(version, 10);
     if (!isNaN(clientVer) && clientVer === match.version) { ... }
     ```
     Parameter `v` is completely absent from query destructuring.
5. **Error Schema Inspection**:
   - Inspected lines 1081–1085 and lines 1118–1122: error objects contain `"error": "chapter_not_found"` or `"error": "grade_not_found"`, but lack the mandated `"code"` property.

## 2. Logic Chain
1. From Observation 1, the deployed endpoint is robust against malicious injections (SQLi, XSS, prototype pollution, type overflows) and enforces strict HTTP method whitelisting with zero server crashes or 500s.
2. From Observation 2, by hoisting manipulative specifications and bilingual vocabulary to chapter scope, all single-grade payloads (11.5–13.8 KB minified) safely pass the <50 KB constraint.
3. From Observation 3 and Observation 4, when mobile clients attempt sync emulation using the standard parameter `v=3`, `deltas.js` ignores `v`, evaluates `clientVer` as `NaN`, and transmits the full 36–43 KB question bank instead of the compact `<200B` `{ upToDate: true }` response. This directly violates the client synchronization requirement in the authoritative task assignment.
4. From Observation 5, error responses omit the `code` attribute required by `{ error, code }`.
5. Therefore, the deployment must be evaluated as **REJECT** until Worker 1 aliases `v || version` and adds `code` to the error schemas.

## 3. Caveats
- The project `proj_wDCbCrGwuVqy` is on the personal tier, so tests were run via the in-process execution bridge `run_function(..., as: "public")`. This faithfully models server handler behavior. If direct browser access from unauthenticated clients is required, the project owner must toggle visibility to public in the Hatchable console.
- No other caveats. All empirical observations are directly reproducible.

## 4. Conclusion
**Verdict**: **REJECT**.  
Worker 1's deployment v7 successfully passes security fuzzing, zero-spoiler pedagogical verification, and bandwidth limits. However, it fails client synchronization emulation because `?v=3` does not trigger the compact `{ upToDate: true }` packet, causing unnecessary bandwidth re-transmission on mobile devices, and error payloads lack the `code` property. 

Worker 1 must apply a 5-line patch in `api/chapters/deltas.js` (aliasing `v || version` and adding `code` to 404 responses) and redeploy as v8.

## 5. Verification Method
Any peer agent or auditor can verify this failure empirically by executing:

```javascript
// Test 1: v=3 cache failure (returns full payload instead of <200B)
call_mcp_tool({
  ServerName: "hatchable",
  ToolName: "run_function",
  Arguments: {
    project_id: "proj_wDCbCrGwuVqy",
    path: "/api/chapters/deltas",
    method: "GET",
    as: "public",
    query: { chapter: "c6_fractions", v: "3" }
  }
});
// Actual: returns 36,454 bytes, upToDate: false.
// Expected per spec: <200 bytes, upToDate: true.

// Test 2: Error code missing
call_mcp_tool({
  ServerName: "hatchable",
  ToolName: "run_function",
  Arguments: {
    project_id: "proj_wDCbCrGwuVqy",
    path: "/api/chapters/deltas",
    method: "GET",
    as: "public",
    query: { chapter: "nonexistent" }
  }
});
// Actual: {"error": "chapter_not_found", "requested": "nonexistent"}
// Expected per spec: {"error": "chapter_not_found", "code": "CHAPTER_NOT_FOUND"}
```
