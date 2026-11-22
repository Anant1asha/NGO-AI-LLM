# Serena Memory: hachi_governance
- Engine: Hachi Governed Agent System (packages/hachi)
- Virtual Environment: packages/hachi/.venv (managed via uv)
- Server Entrypoint: packages/hachi/src/hachi/mcp_server.py
- Tools Exposed:
  1. hachi_search_skills (Pass 1: BM25 ranked candidate discovery)
  2. hachi_peek_skill (Pass 2: ultra-dense ~30 token summary & block manifest)
  3. hachi_load_skill (Pass 3: surgical block retrieval for 97.6% token savings)
  4. hachi_list_skills (60 bundled .og skills across general, technical, google, notion, slack, roles)
  5. hachi_check_assertions (Machine-checkable preconditions)
  6. hachi_save_skill (Semver bumping & auditable changelog updates)
  7. hachi_import_skill_md (SKILL.md to .og converter)
  8. hachi_list_roles (coder, researcher, analyst, devops, emailer)
  9. hachi_delegate_task (isolated context sub-agent with write-target locks & <200 word report)
  10. hachi_doctor (diagnostics & health checks)
- Bridge: scripts/hachi_bridge.mjs
- Mechanical Guardrails: 8-layer framework (Gate, Locks, Rails, Net, Plan, Hygiene, Map, Memory)
