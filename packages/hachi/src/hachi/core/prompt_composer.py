"""PromptComposer — single location for all system-prompt assembly.

All prompt ingredients flow through compose() / build_stable_base(); no other
module should concatenate system-prompt strings directly.
"""

from __future__ import annotations

import datetime


def _build_time_header() -> str:
    """Generate the dynamic time block (changes every turn — NOT cached)."""
    local_dt = datetime.datetime.now().astimezone()
    current_time = local_dt.strftime("%A, %Y-%m-%d %H:%M:%S")
    tz_offset = local_dt.strftime("%z")
    tz_fmt = f"{tz_offset[:3]}:{tz_offset[3:]}" if len(tz_offset) == 5 else tz_offset
    return (
        "--- CURRENT TIME AND DATE ---\n"
        f"The current local time is: {current_time}\n"
        f"Your Local Timezone Offset is: {tz_fmt}\n"
        "Use this context to resolve relative times like 'today' or 'tomorrow', "
        "and ALWAYS append the timezone offset when creating ISO strings.\n"
    )


def build_stable_base(
    brain_text: str,
    skill_count: int = 0,
    integration_count: int = 0,
    permission_block: str = "",
    capability_block: str = "",
    tool_groups: list[str] | None = None,
) -> str:
    """Build the stable session-level system prompt (called once at boot).

    Returns a string that becomes the base for every turn's cacheable prefix.

    Args:
        brain_text: The raw brain/.og prompt text.
        skill_count: Number of .og skill files loaded.
        integration_count: Number of live service tools connected.
        permission_block: Output of runtime_gate.get_system_prompt_injection().
        capability_block: Stringified capability status snapshot.
        tool_groups: Optional domain tool group names available on demand.

    Returns:
        The fully assembled stable base prompt string.
    """
    parts = [brain_text]

    if skill_count > 0:
        parts.append(
            "\n\n--- IMPORTANT: ObjectGraph Skills Available (3-pass loading) ---\n"
            f"You have {skill_count} skill(s) loaded from .og files. Read them in three passes "
            "so you only spend tokens on what you actually need:\n"
            "1. `search_skills` (Pass 1) — ALWAYS call first to find relevant skills by keyword.\n"
            "2. `peek_skill` (Pass 2) — read the candidates' compressed summaries cheaply to pick "
            "the right one; don't load blind.\n"
            "3. `load_skill` (Pass 3) — load the chosen skill's full instructions (optionally "
            "narrowing to specific `blocks`), then follow them precisely.\n"
            "If a skill has ASSERTIONS, you MUST run each assertion command and verify it passes "
            "before continuing.\n"
        )

    if integration_count > 0:
        parts.append(
            "\n--- IMPORTANT: Live Service Integrations Active ---\n"
            f"You have {integration_count} live service tool(s) connected.\n"
            "These are REAL tools with persistent connections (e.g., email, calendar, APIs).\n"
            "Use them directly when the user's request matches their purpose.\n"
            "Do NOT write scripts or use run_terminal_command for tasks these tools handle.\n"
        )

    if permission_block:
        parts.append(permission_block)

    if capability_block:
        parts.append(
            "\n--- OPTIONAL CAPABILITIES ---\n"
            "Only use tools from capabilities that are enabled and configured.\n"
            f"Status: {capability_block}\n"
        )

    if tool_groups:
        domain_groups_str = ", ".join(sorted(tool_groups))
        parts.append(
            "\n--- OPTIONAL TOOL GROUPS (lazy-loaded) ---\n"
            "To keep your context lean, only core tools are shown by default. These extra "
            f"groups are available on demand: {domain_groups_str}.\n"
            'Call use_tools(group="<name>") to activate a group for the rest of the turn. '
            "load_skill(name=...) auto-activates that skill's own tools.\n"
        )

    return "".join(parts)


def compose(
    stable_base: str,
    user_profile_snapshot: str | None = None,
    agent_profile_snapshot: str | None = None,
    recalled_context: str | None = None,
) -> tuple[str, str]:
    """Compose the cache-aware (cacheable, dynamic) prompt split for a turn.

    Args:
        stable_base: The stable session prompt (from build_stable_base).
        user_profile_snapshot: Session-frozen user profile facts (goes in cacheable).
        agent_profile_snapshot: Session-frozen agent persona (goes in cacheable).
        recalled_context: Per-query vault recall (goes in dynamic — changes every turn).

    Returns:
        (cacheable_system, dynamic_system) where cacheable carries the cache breakpoint
        and dynamic sits after it so volatile content never invalidates the cache.
    """
    # Cacheable prefix: stable across the session.
    cacheable_parts = [stable_base]
    if user_profile_snapshot:
        cacheable_parts.append(
            f"\n\n--- USER PROFILE (captured for this session) ---\n{user_profile_snapshot}"
        )
    if agent_profile_snapshot:
        cacheable_parts.append(
            f"\n\n--- AGENT PROFILE (captured for this session) ---\n{agent_profile_snapshot}"
        )
    cacheable = "".join(cacheable_parts)

    # Dynamic tail: changes every turn — must sit AFTER the cache breakpoint.
    dynamic_parts = [_build_time_header()]
    if recalled_context:
        dynamic_parts.append(f"\n\n--- RECALLED CONTEXT ---\n{recalled_context}")
    dynamic = "".join(dynamic_parts)

    return cacheable, dynamic
