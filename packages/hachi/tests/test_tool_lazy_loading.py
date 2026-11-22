"""Tests for per-turn lazy tool-loading: curated core + on-demand groups.

Invariant under test: only "core" tools are sent by default, optional groups are
unlocked mid-turn via use_tools()/load_skill(), and no tool is ever permanently
uncallable.
"""

from __future__ import annotations

from hachi.core.llm import LLMResponse, TokenUsage, ToolCall
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory
from hachi.tools.og_tools import USE_TOOLS_SCHEMA, _make_use_tools

_EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": []}


def _tool(name: str) -> dict:
    return {"name": name, "description": name, "input_schema": _EMPTY_SCHEMA}


def _grouped_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(_tool("read_file"), lambda **_k: "ok")  # default -> core
    reg.register(USE_TOOLS_SCHEMA, _make_use_tools(reg), group="core")
    reg.register(_tool("load_skill"), lambda **_k: "loaded", group="core")
    reg.register(_tool("schedule_task"), lambda **_k: "scheduled", group="schedule")
    reg.register(_tool("python_sandbox"), lambda **_k: "ran", group="sandbox")
    reg.register(_tool("fetch_wiki_summary"), lambda **_k: "wiki", group="wiki")
    return reg


class _RecordingLLM:
    """Scripted LLM that records the tool names it was offered on each call."""

    model = "fake-model"

    def __init__(self, script: list[list[ToolCall]]) -> None:
        self._script = script
        self._i = 0
        self.tools_seen: list[set[str]] = []

    def generate(self, **kwargs) -> LLMResponse:
        self.tools_seen.append({t["name"] for t in (kwargs.get("tools") or [])})
        calls = self._script[self._i] if self._i < len(self._script) else []
        self._i += 1
        return LLMResponse(content="" if calls else "done", tool_calls=calls, usage=TokenUsage())

    def generate_stream(self, **kwargs):
        response = self.generate(**kwargs)
        return response
        yield  # makes this a generator function


# --- ToolRegistry unit tests ---------------------------------------------


def test_get_schemas_filters_by_active_groups() -> None:
    reg = _grouped_registry()
    all_names = {s["name"] for s in reg.get_schemas(None)}
    core = {s["name"] for s in reg.get_schemas(set())}
    assert {"read_file", "use_tools", "load_skill"} <= core
    assert "schedule_task" not in core and "python_sandbox" not in core
    sched = {s["name"] for s in reg.get_schemas({"schedule"})}
    assert "schedule_task" in sched and "python_sandbox" not in sched
    assert core < all_names  # strict subset — gating actually reduces the set


def test_classify_assigns_groups_and_preserves_explicit_stamps() -> None:
    reg = ToolRegistry()
    reg.register(_tool("read_file"), lambda **_k: "")  # register default -> core
    reg.register(_tool("schedule_task"), lambda **_k: "")  # default core, reclassified
    reg.register(_tool("fetch_wiki_summary"), lambda **_k: "", group="wiki")  # explicit
    reg.register(_tool("slack_post"), lambda **_k: "")  # unmapped -> default fallback
    reg.classify(
        core_names={"read_file"},
        group_by_name={"schedule_task": "schedule"},
        default="integrations",
    )
    assert reg._groups["read_file"] == "core"
    assert reg._groups["schedule_task"] == "schedule"
    assert reg._groups["fetch_wiki_summary"] == "wiki"  # explicit stamp preserved
    assert reg._groups["slack_post"] == "integrations"  # fallback applied (not stuck core)
    assert reg.available_groups() == {"core", "schedule", "wiki", "integrations"}


def test_no_tool_is_permanently_hidden() -> None:
    reg = _grouped_registry()
    all_names = {s["name"] for s in reg.get_schemas(None)}
    reachable = {s["name"] for s in reg.get_schemas(reg.available_groups() - {"core"})}
    assert reachable == all_names  # activating every group reveals everything


# --- ExecutionLoop integration tests -------------------------------------


def _loop(reg: ToolRegistry, llm: _RecordingLLM) -> ExecutionLoop:
    return ExecutionLoop(llm, reg, SubAgentMemory(), base_system_prompt="x")


def test_use_tools_unlocks_group_mid_turn() -> None:
    reg = _grouped_registry()
    llm = _RecordingLLM(
        [
            [ToolCall(id="a", name="use_tools", input={"group": "schedule"})],
            [ToolCall(id="b", name="schedule_task", input={})],
            [],
        ]
    )
    loop = _loop(reg, llm)
    loop.add_user_message("schedule something")
    loop.run(max_iterations=5)
    assert "schedule" in loop._active_groups
    assert "schedule_task" not in llm.tools_seen[0]  # gated before activation
    assert "schedule_task" in llm.tools_seen[1]  # available after activation


def test_load_skill_auto_activates_its_group() -> None:
    reg = _grouped_registry()
    llm = _RecordingLLM(
        [
            [ToolCall(id="a", name="load_skill", input={"name": "wiki"})],
            [],
        ]
    )
    loop = _loop(reg, llm)
    loop.add_user_message("look up sunflowers")
    loop.run(max_iterations=5)
    assert "wiki" in loop._active_groups
    assert "fetch_wiki_summary" not in llm.tools_seen[0]
    assert "fetch_wiki_summary" in llm.tools_seen[1]


def test_active_groups_reset_between_turns() -> None:
    reg = _grouped_registry()
    activate = _RecordingLLM(
        [[ToolCall(id="a", name="use_tools", input={"group": "schedule"})], []]
    )
    loop = _loop(reg, activate)
    loop.add_user_message("go")
    loop.run(max_iterations=5)
    assert "schedule" in loop._active_groups

    # New turn: groups must reset; the first call sees only core again.
    llm2 = _RecordingLLM([[]])
    loop.llm_client = llm2
    loop.add_user_message("go again")
    loop.run(max_iterations=5)
    assert loop._active_groups == set()
    assert "schedule_task" not in llm2.tools_seen[0]


# --- Orchestrator taxonomy guard -----------------------------------------


def test_core_tool_set_size_guard() -> None:
    from hachi.gateway.orchestrator import _CORE_TOOL_NAMES

    assert 18 <= len(_CORE_TOOL_NAMES) <= 24  # budget can't silently regress
    assert "use_tools" in _CORE_TOOL_NAMES
    assert "browse_web" in _CORE_TOOL_NAMES


def test_rare_tools_trimmed_from_core_to_lazy_groups() -> None:
    # Cost trim: rare flagship tools moved out of the always-on core set to cut the
    # per-turn tool-schema footprint (~1.3K tokens). Still reachable via use_tools().
    from hachi.gateway.orchestrator import _CORE_TOOL_NAMES, _GROUP_BY_TOOL_NAME

    moved = {
        "delegate_task": "delegation",
        "list_roles": "delegation",
        "save_skill": "authoring",
        "skill_changelog": "authoring",
    }
    for name, group in moved.items():
        assert name not in _CORE_TOOL_NAMES, f"{name} should be lazy, not core"
        assert _GROUP_BY_TOOL_NAME.get(name) == group

    # Skill-routing CONTRACT + safety tools must remain always-on: brain.og requires
    # skill_dependencies / check_skill_assertions right after load_skill, and
    # rollback_changes is the file-edit undo. Hiding these would break those flows.
    for name in (
        "skill_dependencies",
        "check_skill_assertions",
        "rollback_changes",
        "search_skills",
        "peek_skill",
        "load_skill",
        "use_tools",
    ):
        assert name in _CORE_TOOL_NAMES


def test_classify_routes_trimmed_tools_to_their_groups() -> None:
    from hachi.gateway.orchestrator import _CORE_TOOL_NAMES, _GROUP_BY_TOOL_NAME

    reg = ToolRegistry()
    for nm in ("read_file", "delegate_task", "save_skill", "skill_dependencies"):
        reg.register(_tool(nm), lambda **_k: "")
    reg.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        default="integrations",
    )
    core = {s["name"] for s in reg.get_schemas(set())}
    assert {"read_file", "skill_dependencies"} <= core  # contract tool stays core
    assert "delegate_task" not in core and "save_skill" not in core  # trimmed out
    # Unlocking the group surfaces the moved tool again — never permanently hidden.
    assert "delegate_task" in {s["name"] for s in reg.get_schemas({"delegation"})}
    assert "save_skill" in {s["name"] for s in reg.get_schemas({"authoring"})}
