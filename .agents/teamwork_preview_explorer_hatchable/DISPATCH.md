# Task Assignment for Explorer 1 (Hatchable Investigator)

## Identity
- TypeName: teamwork_preview_explorer
- Role: Hatchable Project Investigator
- Working Directory: c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_hatchable
- Parent: teamwork_preview_orchestrator_4

## Objective
Investigate the live Hatchable project `proj_wDCbCrGwuVqy`.
Examine existing files, API endpoints, project configuration, and understand how Hatchable functions are defined, routed, and exported.

## Instructions & Scope
1. Use Hatchable MCP tools (e.g. `call_mcp_tool` with `ServerName: "hatchable"`, using tools such as `get_project`, `list_files`, `read_file`, etc.) to inspect project `proj_wDCbCrGwuVqy`.
2. Check existing routes under `api/`, especially whether any `api/chapters/` exists, how `export const access = "public"` is used in existing files, how query parameters are received (e.g., standard request object, query object, URL parsing), and response formatting.
3. Check the deployment status and environment settings of `proj_wDCbCrGwuVqy`.
4. Check how `run_function` works for testing Hatchable functions.
5. Write your complete findings and technical recommendations into `c:\Users\admin\Downloads\NGO AI LLM\.agents\teamwork_preview_explorer_hatchable\report.md` and `handoff.md`.

## 2026-09-16T20:50:00Z
Received dispatch:
Investigate the live Hatchable project proj_wDCbCrGwuVqy.
Thoroughly inspect:
1. Project structure, configuration, package.json or dependencies.
2. Existing API routes in api/. Handler syntax, query parsing, access exports.
3. Existing files, routes, or deployments in proj_wDCbCrGwuVqy.
4. run_function usage for testing functions.
5. Code templates and recommendations for api/chapters/deltas.js.
