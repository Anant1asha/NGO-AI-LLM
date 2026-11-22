> **Historical document.** Written before the rename to Hachi. References to
> the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

Design a terminal-first product experience for Hachi, an operator console for an autonomous AI agent runtime.

Do not create wireframes.
Do not prescribe exact visual styling, colors, spacing, or fixed layouts.
Focus on capabilities, information architecture, and interaction behavior.

Product context:
- Hachi is a session-based agent runtime with tool-calling, skill retrieval, sub-agent delegation, long-term memory, and safety gating.
- It runs locally or through a gateway API.
- Primary users are developers, operators, and solution engineers who need execution visibility, safe intervention, and troubleshooting controls.

Design goals:
1. Operational clarity during live execution.
2. End-to-end traceability across sessions, turns, tools, jobs, permissions, and delegations.
3. Safe human-in-the-loop intervention for sensitive actions.
4. Fast diagnosis and recovery from failures.
5. Continuity across restarts and reconnects.

Core user goals:
1. Start and manage runtime sessions.
2. Send prompts and observe execution in real time.
3. Understand tool activity and model progress.
4. Approve or deny sensitive operations.
5. Monitor jobs, failures, retries, and integration health.
6. Inspect memory, prior sessions, and delegation outcomes.
7. Configure provider, safety, and memory settings.
8. Run setup and diagnostics when environment/config is incomplete.

System entities to represent in the product model:
- Session
- Turn
- Runtime event
- Tool invocation
- Job
- Permission request and permission decision
- Memory fact
- Sub-agent report
- MCP server and tool inventory
- Capability
- Provider config
- Setup plan and setup state
- Security finding

Global product requirements:
1. Always-visible runtime identity and context:
- Workspace or project identity
- Active session id
- Current provider and model
- Current permission tier
- Runtime status: booting, ready, degraded, failed
2. Persistent state signals:
- Running jobs count
- Pending approvals count
- Recent warnings and errors indicator
- Event stream connectivity signal
3. Immediate operator controls:
- Interrupt active execution
- Refresh current data
- Jump to setup, config, diagnostics
4. Universal inspectability:
- Drill from summary to latest event, job, approval, tool call, and failure record

Required product areas:
1. Session area:
- Prompt input
- Transcript
- Streamed intermediate output
- Execution timeline
- Current execution state
2. Operations area:
- Active jobs
- Failed jobs
- Runtime events
- MCP inventory
3. Memory and history area:
- Task ledger
- Semantic recall results
- Session history search
4. Integrations and capabilities area:
- MCP servers and tool inventory
- Capability readiness states
- Setup hints for unavailable paths
5. Settings and config area:
- Effective runtime config snapshot
- Provider controls
- Permission tier controls
- Memory controls
- Validation feedback
6. Setup area:
- Tiered onboarding
- Resumable progress
- Step status and apply outcomes
7. Diagnostics and audit area:
- Runtime doctor checks
- Security findings with severity and remediation guidance

Execution and interaction requirements:
1. Support event-driven updates and cursor-based replay.
2. Show lifecycle transitions clearly:
- idle
- running
- waiting-approval
- completed
- failed
- suspended
3. Enable operator interrupt during active execution.
4. Provide explicit approval actions:
- approve
- allow once
- deny
- rationale capture
5. Preserve state across restart and reconnect:
- last active area
- draft input
- setup resume context
6. Keep errors actionable by linking them to related job, event, config, permission, integration, or delegation records.

Observability requirements:
1. Expose boot progression and blockers.
2. Expose session lifecycle and per-turn state.
3. Expose streamed model deltas.
4. Expose tool started and completed records with previews.
5. Expose permission requests and decisions.
6. Expose sub-agent lifecycle and report metadata.
7. Expose job lifecycle, retries, and failures.
8. Expose MCP lifecycle and inventory.
9. Expose memory recall, task ledger, and history search results.
10. Expose config mutation and validation outcomes.
11. Expose diagnostics and security findings.

Human-in-the-loop safety requirements:
1. Permission denials may trigger operator approval workflow.
2. Approval dismiss or timeout defaults to deny with rationale.
3. Operator can intervene, then return to normal execution flow.
4. Sensitive operations must remain explicitly gated by policy tier and approval path.

Information architecture constraints:
1. Keep internals abstracted by default:
- hide full raw prompt composition internals
- hide low-level storage or queue engine internals
- hide full untruncated payloads unless expanded on demand
- expose memory-guard outcomes, not detector rule internals
2. Prioritize operator-relevant facts over implementation detail.
3. Optimize for scanability first, deep-inspection second.

Design intent and constraints:
1. Keep implementation-oriented fidelity to the capabilities above.
2. Prioritize operational clarity, traceability, and safe intervention.
3. Avoid copying existing CLI product interfaces.
4. You are free to be creative in layout and visual language as long as all required states and capabilities are represented clearly.

If you want, I can also generate a second version optimized for shorter prompt length while preserving the same requirement coverage for faster iteration in Stitch.