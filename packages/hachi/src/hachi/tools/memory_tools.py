"""
Core Memory Tools

Provides the LLM-facing tool bindings for all memory subsystems:
  - core_save_memory / core_search_memory / core_delete_memory  → workspace facts
  - core_save_user_profile / core_search_user_profile            → bounded user identity
  - core_search_sessions                                        → cross-session history search

The save_memory tool performs intelligent consolidation via the durable job queue:
it finds conflicting facts, atomizes compound statements, and deletes superseded
entries — all without blocking the main agent loop.

MR-7 / UC-MEM-001 / UC-MEM-006 — loud failure contract:
    ``core_save_memory`` MUST NOT claim success unless the write was durably
    enqueued.  If the job queue is absent or the enqueue call raises, the tool
    returns a clear FAILURE string so the agent cannot falsely claim it remembered.
    Daemon-thread fallbacks are prohibited here.
"""

import json
import logging

from hachi.core.loop import ToolRegistry
from hachi.core.memory_vault import MemoryVault

logger = logging.getLogger(__name__)


def register_memory_tools(
    registry: ToolRegistry,
    vault: MemoryVault,
    job_queue=None,
    profile_store=None,
) -> None:
    """Mount all memory operations into the LLM's active toolset.

    Args:
        registry:     The tool registry to populate.
        vault:        A live ``MemoryVault`` instance (may be ``None`` for in-memory mode).
        job_queue:    Optional durable job queue; ``core_save_memory`` requires it.
        profile_store: Optional ``UserProfileStore`` instance for the structured profile tool.
            When ``None`` and ``vault`` is live, one is constructed automatically so
            callers that only pass ``vault`` get the full tool surface for free.
    """

    # ==========================================
    # Shared Helpers
    # ==========================================

    def _parse_llm_json(raw: str) -> dict | None:
        """Extract JSON from an LLM response that may be fenced in ```json blocks."""
        text = raw.strip()
        if text.startswith("```json"):
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif text.startswith("```"):
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        return json.loads(text)

    # ==========================================
    # Core Memory (Workspace Facts)
    # ==========================================

    def _enqueue_memory_job(name: str, func, args: tuple) -> str | None:
        """Attempt to enqueue a memory job via the durable queue.

        Returns:
            The job ID string on success, or ``None`` if the queue is absent
            or the enqueue call raised.  Callers MUST treat ``None`` as a
            durable failure — no silent thread fallback is permitted.
        """
        if not job_queue:
            return None

        try:
            from hachi.jobs.queue import Job, JobStatus

            job = Job(
                job_id="",
                name=name,
                status=JobStatus.PENDING,
                func=func,
                args=args,
                job_type="persist",
            )
            job_id = job_queue.enqueue(job)
            return job_id
        except Exception as exc:
            logger.error(
                "core_save_memory: failed to enqueue job %r — write NOT persisted: %s",
                name,
                exc,
            )
            return None

    def save_memory(facts: list) -> str:
        """Save one or more workspace facts with intelligent dedup and contradiction resolution."""
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        if not facts:
            return "No facts provided."

        def _smart_upsert(fact_batch: list):
            for fact in fact_batch:
                content = fact.get("content")
                category = fact.get("category", "workspace_state")
                if not content:
                    continue

                try:
                    results = vault.semantic_search(content, top_k=3)
                    if not results:
                        vault.upsert_fact(content, category)
                        continue

                    snippet = "\n".join(f"[{r['id']}] {r['raw_content']}" for r in results)

                    from hachi.core.llm import AnthropicClient
                    from hachi.core.llm import Message as LLMMessage

                    client = AnthropicClient()
                    prompt = (
                        "You are a memory consolidation engine.\n"
                        f"New Compound Fact to save: '{content}'\n\n"
                        "Existing Facts in Database:\n"
                        f"{snippet}\n\n"
                        "Analyze if the New Fact completely supersedes, contradicts, or overlaps "
                        "with any Existing Facts. "
                        "CRITICAL: Break the New Fact into STRICTLY ATOMIC components. "
                        "For example: 'Mike is my boss and his email is X' -> "
                        "['User\\'s boss is Mike', 'Mike\\'s email is X'].\n"
                        "If an atomic component supersedes an old fact "
                        "(e.g. Boss was X, now Boss is Y), add the old fact's ID to 'delete_ids'.\n"
                        'Output pure JSON only: {"delete_ids": ["id1", "id2"], '
                        '"save_contents": ["atomic fact 1", "atomic fact 2"]}'
                    )

                    response = client.generate(
                        messages=[LLMMessage(role="user", content=prompt)],
                        system_prompt="You are a data merger. Output pure JSON only.",
                    )

                    data = _parse_llm_json(response.content)

                    for did in data.get("delete_ids", []):
                        if did and did not in ("null", "None", None):
                            vault.delete_fact(did)

                    for s_content in data.get("save_contents", [content]):
                        vault.upsert_fact(s_content, category)
                except Exception:
                    # FIX 3: Do NOT fall back to a bare upsert_fact here.
                    # The bare fallback bypassed _smart_upsert consolidation/dedup
                    # on any exception (e.g. LLM error, JSON parse failure) and
                    # silently wrote the raw compound fact — creating near-duplicate
                    # entries that _smart_upsert was designed to prevent.
                    # Log at WARNING so operators can diagnose consolidation failures,
                    # but skip the write so we never create a known near-duplicate.
                    logger.warning(
                        "_smart_upsert: consolidation failed for fact %.80r — "
                        "skipping write to avoid near-duplicate. "
                        "Retry core_save_memory to persist this fact.",
                        content,
                        exc_info=True,
                    )

        job_id = _enqueue_memory_job("memory_smart_upsert", _smart_upsert, (facts,))
        if job_id is None:
            # Queue absent or enqueue failed — do NOT fall back to a daemon thread
            # that would silently lose the write.  Report failure loudly so the
            # agent cannot falsely claim it remembered.
            if not job_queue:
                return (
                    "MEMORY WRITE FAILED: no job queue is configured. "
                    f"{len(facts)} fact(s) were NOT saved. "
                    "The agent cannot claim these were remembered."
                )
            return (
                "MEMORY WRITE FAILED: could not enqueue the write job. "
                f"{len(facts)} fact(s) were NOT saved. "
                "Check logs for the enqueue error. "
                "The agent cannot claim these were remembered."
            )
        return (
            f"{len(facts)} fact(s) queued for intelligent long-term consolidation (job {job_id})."
        )

    def search_memory(query: str, top_k: int = 5) -> str:
        """Semantic search against the workspace memory vault."""
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        try:
            results = vault.semantic_search(query, top_k)
            if not results:
                return f"No relevant memories found for query: '{query}'"

            formatted = ["Found the following relevant memories:"]
            for r in results:
                formatted.append(f"- [{r['category']}] (ID: {r['id']}) {r['content']}")
            return "\n".join(formatted)
        except Exception as e:
            return f"Failed to search memory: {str(e)}"

    def delete_memory(fact_id: str) -> str:
        """Delete a workspace fact by ID from ALL storage backends.

        Removes the fact from:
          - Chroma core_memory collection (primary semantic store)
          - FTS5 graph index (if attached) so forgotten facts cannot resurface
            via keyword search (UC-MEM-004)

        The operation is idempotent — deleting an absent ID returns a success
        confirmation rather than an error, so callers may safely retry.
        """
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        ok = vault.delete_fact(fact_id)
        if ok:
            return (
                f"Memory fact {fact_id} has been removed from all backends "
                "(Chroma + FTS5 index). It will not appear in future searches."
            )
        return (
            f"MEMORY DELETE FAILED: could not remove fact {fact_id} from Chroma. "
            "The fact may still be retrievable. Check logs for details."
        )

    # ==========================================
    # User Profile (Bounded Identity Store)
    # ==========================================

    def save_user_profile(facts: list) -> str:
        """Save one or more user identity facts into the bounded profile collection."""
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        if not facts:
            return "No facts provided."

        saved_ids = []
        for fact in facts:
            content = fact.get("content")
            category = fact.get("category", "preference")
            if not content:
                continue

            result = vault.upsert_user_fact(content, category)
            if result == "LIMIT_REACHED":
                stats = vault.get_profile_stats()
                return (
                    f"Saved {len(saved_ids)} facts. Stopped because user profile is full "
                    f"({stats['entries']}/{stats['max_entries']} entries). "
                    "Use core_search_user_profile to find outdated facts, "
                    "then core_delete_user_profile "
                    "to remove them before saving new ones."
                )
            if result.startswith("BLOCKED:"):
                return (
                    f"Saved {len(saved_ids)} facts. Stopped because content was rejected "
                    f"by security scanner: {result}"
                )

            saved_ids.append(result)

        return f"Successfully saved {len(saved_ids)} user profile facts."

    def search_user_profile(query: str, top_k: int = 10) -> str:
        """Semantic search against the user profile collection."""
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        try:
            results = vault.search_user_profile(query, top_k)
            if not results:
                return f"No user profile facts found for: '{query}'"

            stats = vault.get_profile_stats()
            header = f"User Profile ({stats['entries']}/{stats['max_entries']} slots used):"
            lines = [header]
            for r in results:
                lines.append(f"- [{r['category']}] (ID: {r['id']}) {r['raw_content']}")
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to search user profile: {str(e)}"

    def delete_user_profile(fact_id: str) -> str:
        """Delete a user identity fact by ID."""
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
        if vault.delete_user_fact(fact_id):
            return f"Successfully deleted user profile fact: {fact_id}"
        return f"Failed to delete user profile fact: {fact_id}. It may not exist."

    def save_agent_profile(facts: list[str]) -> str:
        """Saves a batch of behavioral directives to the agent persona vault."""
        if not vault:
            return "ERROR: MemoryVault is not connected."

        results = []
        for fact in facts:
            fact_id = vault.upsert_agent_fact(fact, category="directive")
            results.append(f"- Fact: '{fact[:50]}...' -> ID: {fact_id}")

        return "Saved the following directives to Agent Profile Vault:\n" + "\n".join(results)

    def delete_agent_profile(fact_id: str) -> str:
        """Deletes a directive from the bounded agent persona vault."""
        if not vault:
            return "ERROR: MemoryVault is not connected."

        success = vault.delete_agent_fact(fact_id)
        if success:
            return f"Successfully removed directive {fact_id} from Agent Profile."
        return f"Failed to remove directive {fact_id}."

    def get_memory_stats() -> str:
        """Retrieves capacity stats for bounded identity vaults."""
        if not vault:
            return "ERROR: MemoryVault is not connected."

        # User stats
        user_stats = vault.get_profile_stats()
        user_count = user_stats["entries"]
        user_max = user_stats["max_entries"]

        # Agent stats
        agent_count = vault.agent_profile.count() if vault.agent_profile else 0

        return (
            f"User Profile Capacity: {user_count}/{user_max} entries used.\n"
            f"Agent Profile Capacity: {agent_count}/{user_max} entries used."
        )

    # ==========================================
    # Tool Registration
    # ==========================================

    registry.register(
        {
            "name": "core_save_memory",
            "description": (
                "Save an atomic, dense fact into the user's Long-Term Memory Vault. "
                "Use this to permanently store preferences, relationships, API keys, or context."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "facts": {
                        "type": "array",
                        "description": "List of atomic workspace facts to save.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": (
                                        "The exact fact to save. Make it highly descriptive "
                                        "(e.g. 'Project uses FastAPI 0.115')."
                                    ),
                                },
                                "category": {
                                    "type": "string",
                                    "description": (
                                        "Optional category tag "
                                        "(e.g., 'workspace_state', 'architecture', 'bug_history')"
                                    ),
                                },
                            },
                            "required": ["content"],
                        },
                    }
                },
                "required": ["facts"],
            },
        },
        save_memory,
    )

    registry.register(
        {
            "name": "core_search_memory",
            "description": (
                "Perform a semantic search against the Long-Term Memory Vault. "
                "Use this before asking the user a clarifying question "
                "to see if you already know the answer."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The semantic query (e.g., 'Who is the user's boss?')",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                    },
                },
                "required": ["query"],
            },
        },
        search_memory,
    )

    registry.register(
        {
            "name": "core_delete_memory",
            "description": "Remove an outdated or incorrect fact from the Memory Vault.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": (
                            "The exact ID of the fact to delete, obtained from core_search_memory."
                        ),
                    }
                },
                "required": ["fact_id"],
            },
        },
        delete_memory,
    )

    registry.register(
        {
            "name": "core_save_user_profile",
            "description": (
                "Save a user identity or preference fact into the PERMANENT user profile. "
                "Use this for things that define WHO the user is: their name, role, timezone, "
                "communication style, coding preferences, or personal relationships. "
                "This store is bounded (max 25 entries) — be precise and atomic. "
                "For workspace/project facts, use core_save_memory instead."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "facts": {
                        "type": "array",
                        "description": "List of atomic identity facts to save.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": (
                                        "The atomic identity fact "
                                        "(e.g., 'User's name is Aarav', "
                                        "'User prefers TypeScript')."
                                    ),
                                },
                                "category": {
                                    "type": "string",
                                    "description": (
                                        "Category: name, role, preference, habit, "
                                        "relationship, timezone, style, identity."
                                    ),
                                    "enum": [
                                        "name",
                                        "role",
                                        "preference",
                                        "habit",
                                        "relationship",
                                        "timezone",
                                        "style",
                                        "identity",
                                    ],
                                },
                            },
                            "required": ["content"],
                        },
                    }
                },
                "required": ["facts"],
            },
        },
        save_user_profile,
    )

    registry.register(
        {
            "name": "core_search_user_profile",
            "description": (
                "Search the user's permanent identity profile. Returns user-specific facts like "
                "name, role, preferences, and habits. Shows capacity stats (used/max slots)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What to look up "
                            "(e.g., 'user preferences', 'user's name', 'coding style')."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
        search_user_profile,
    )

    registry.register(
        {
            "name": "core_delete_user_profile",
            "description": (
                "Remove an outdated or incorrect fact from the bounded User Profile store."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": (
                            "The exact ID of the user profile fact to delete, "
                            "obtained from core_search_user_profile."
                        ),
                    }
                },
                "required": ["fact_id"],
            },
        },
        delete_user_profile,
    )

    # ==========================================
    # Structured User Profile (P1-7)
    # ==========================================

    # Lazily resolve or construct the UserProfileStore so callers that don't
    # pass profile_store explicitly still get the tool when vault is live.
    _profile_store = profile_store
    if _profile_store is None and vault is not None:
        try:
            from hachi.core.user_profile import UserProfileStore

            _profile_store = UserProfileStore(vault)
        except Exception as _ps_err:
            logger.warning("register_memory_tools: could not build UserProfileStore: %s", _ps_err)

    def save_user_profile_structured(category: str, value: str) -> str:
        """Save a structured user profile fact under one of the four P1-7 categories.

        Writes through to ``UserProfileStore.set``, which stamps the P1-7 category
        in metadata and enforces the vault's 25-entry cap and MemoryGuard scanning.

        Args:
            category: One of identity | preferences | routines | knowledge.
            value: The atomic profile fact to store.

        Returns:
            Human-readable result string.
        """
        if not _profile_store:
            return (
                "Structured user profile is not available "
                "(vault not connected or profile store unavailable)."
            )
        try:
            result = _profile_store.set(category, value)
        except ValueError as exc:
            return f"Invalid category: {exc}"
        except Exception as exc:
            logger.error("save_user_profile_structured: unexpected error: %s", exc)
            return f"Failed to save profile fact: {exc}"

        if result == "LIMIT_REACHED":
            stats = vault.get_profile_stats() if vault else {}
            entries = stats.get("entries", "?")
            max_e = stats.get("max_entries", 25)
            return (
                f"Profile is full ({entries}/{max_e} entries). "
                "Use core_search_user_profile to find outdated facts and "
                "core_delete_user_profile to remove them before saving new ones."
            )
        if result.startswith("BLOCKED:"):
            return f"Content rejected by security scanner: {result}"
        if result.startswith("ERROR:"):
            return f"Storage error: {result}"
        return (
            f"Saved [{category}] profile fact (id: {result[:12]}…). "
            "This will be recalled in future sessions."
        )

    registry.register(
        {
            "name": "core_save_user_profile_structured",
            "description": (
                "Save a structured user profile fact under one of the four P1-7 categories: "
                "identity (name, role, location), preferences (tools, style, dark mode), "
                "routines (recurring habits, schedule patterns), or "
                "knowledge (domain expertise the user has declared). "
                "Use this instead of core_save_user_profile when you want the fact "
                "categorised for structured retrieval. "
                "The profile is bounded (max 25 entries total) — be precise and atomic."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": (
                            "Category bucket: identity | preferences | routines | knowledge."
                        ),
                        "enum": ["identity", "preferences", "routines", "knowledge"],
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "The atomic profile fact "
                            '(e.g. "User\'s name is Aarav", '
                            '"User prefers TypeScript over JavaScript", '
                            '"User holds a daily standup at 9 am").'
                        ),
                    },
                },
                "required": ["category", "value"],
            },
        },
        save_user_profile_structured,
    )


def register_session_tools(registry: ToolRegistry, session_store) -> None:
    """Mount session history search tools into the LLM's toolset.

    Separated from register_memory_tools because SessionStore is initialized
    independently from MemoryVault in the boot sequence.

    Args:
        registry: The tool registry to register into.
        session_store: A SessionStore instance for cross-session search.
    """

    def search_sessions(query: str, limit: int = 10) -> str:
        """Search across all past session transcripts."""
        try:
            results = session_store.search_sessions(query, limit)
            if not results:
                return f"No past sessions found matching: '{query}'"

            lines = [f"Found {len(results)} match(es) across past sessions:"]
            for r in results:
                lines.append(
                    f"- [{r['session_date'][:10]}] [{r['role']}] "
                    f"(session {r['session_id']}): {r['snippet']}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Session search failed: {str(e)}"

    registry.register(
        {
            "name": "core_search_sessions",
            "description": (
                "Search across ALL past conversation sessions. Use this to recall what "
                "was discussed in previous sessions, find past decisions, or locate "
                "information the user shared days or weeks ago."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The keyword or phrase to search for across past sessions.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
        search_sessions,
    )
