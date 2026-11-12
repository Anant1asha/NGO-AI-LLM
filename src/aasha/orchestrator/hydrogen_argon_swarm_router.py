"""
Hydrogen <-> Argon Auto-Switch Swarm Router (`/swarm`).

Implements the two-plane autonomous orchestration contract from MASTER_PROMPT_v6:
  - Hydrogen (Master Orchestrator): Planning (`/plan`), self-critique (`/grill-me`),
    W0 live reconciliation, dependency-aware DAG construction, WorkerTaskContract packaging,
    independent verification dispatch (never self-certified by the builder worker), and HIL escalation.
  - Argon (Specialist Execution Swarm): Bounded specialist execution (RECON, CURRICULUM_TLN,
    LLE_DICTIONARY, SIM_VISUAL, ASSESSMENT_TEAS, OFFLINE_HTML5, BACKEND_SQLITE, INDEPENDENT_QA)
    with isolated write scopes and maximum 2 autonomous repair attempts per defect class.

Auto-Switch Rules:
  - `/swarm` or `/plan` / `/grill-me` enters `HYDROGEN_ORCHESTRATE`.
  - Once Hydrogen packages a validated `WorkerTaskContract` with non-overlapping `allowed_paths`,
    execution auto-switches to `ARGON_EXECUTE`.
  - Upon Argon completion, control auto-switches back to `HYDROGEN_ORCHESTRATE` (`INDEPENDENT_QA` gate)
    so a separate verifier checks outputs before any checkpoint/cursor advances.
  - After 2 failed repair attempts on the same defect class, auto-switches to `BLOCKED_HIL` (stops).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class SwarmRole(str, Enum):
    HYDROGEN_ORCHESTRATE = "HYDROGEN_ORCHESTRATE"
    ARGON_EXECUTE = "ARGON_EXECUTE"
    HYDROGEN_INDEPENDENT_QA = "HYDROGEN_INDEPENDENT_QA"
    BLOCKED_HIL = "BLOCKED_HIL"
    CERTIFIED_CHECKPOINT = "CERTIFIED_CHECKPOINT"


class SpecialistFamily(str, Enum):
    RECON = "RECON"
    CURRICULUM_TLN = "CURRICULUM_TLN"
    LLE_DICTIONARY = "LLE_DICTIONARY"
    SIM_VISUAL = "SIM_VISUAL"
    ASSESSMENT_TEAS = "ASSESSMENT_TEAS"
    OFFLINE_HTML5 = "OFFLINE_HTML5"
    BACKEND_SQLITE = "BACKEND_SQLITE"
    INDEPENDENT_QA = "INDEPENDENT_QA"


@dataclass
class WorkerTaskContract:
    task_id: str
    goal: str
    specialist: SpecialistFamily
    allowed_paths: List[str]
    acceptance_criteria: List[str]
    authorization_class: str = "WRITE"  # READ | PROPOSE | WRITE
    dependencies: List[str] = field(default_factory=list)
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            raw = f"{self.task_id}:{self.specialist.value}:{','.join(sorted(self.allowed_paths))}"
            self.idempotency_key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class WorkerResult:
    task_id: str
    worker_id: str
    status: str  # PASS | FAIL
    files_changed: List[str]
    raw_evidence: Dict[str, Any]
    defect_class: Optional[str] = None


class HydrogenArgonSwarmRouter:
    """Deterministic state machine that auto-switches between Hydrogen and Argon under `/swarm`."""

    MAX_REPAIRS_PER_DEFECT = 2

    def __init__(self, repo_root: Path | str = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state: SwarmRole = SwarmRole.HYDROGEN_ORCHESTRATE
        self.repair_counts: Dict[str, int] = {}
        self.transition_log: List[Dict[str, Any]] = []

    def _record(self, from_role: SwarmRole, to_role: SwarmRole, reason: str, task_id: str = "") -> None:
        self.transition_log.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "from": from_role.value,
            "to": to_role.value,
            "reason": reason,
            "task_id": task_id,
        })
        self.state = to_role

    def parse_command_mode(self, prompt: str) -> Dict[str, Any]:
        lower = prompt.lower()
        has_swarm = "/swarm" in lower
        has_plan = "/plan" in lower
        has_grill = "/grill-me" in lower
        return {
            "entry_role": SwarmRole.HYDROGEN_ORCHESTRATE.value,
            "auto_switch_enabled": has_swarm,
            "planning_requested": has_plan,
            "self_critique_requested": has_grill,
        }

    def validate_isolated_contracts(self, contracts: List[WorkerTaskContract]) -> None:
        """Prevents shared-file contention across parallel Argon WRITE tasks."""
        seen_paths: Dict[str, str] = {}
        for c in contracts:
            if c.authorization_class == "READ":
                continue
            for p in c.allowed_paths:
                norm = str(Path(p))
                if norm in seen_paths and seen_paths[norm] != c.task_id:
                    raise ValueError(
                        f"Write-scope contention on '{norm}' between {seen_paths[norm]} and {c.task_id}"
                    )
                seen_paths[norm] = c.task_id

    def run_bounded_cycle(
        self,
        contract: WorkerTaskContract,
        argon_executor: Callable[[WorkerTaskContract], WorkerResult],
        independent_verifier: Callable[[WorkerTaskContract, WorkerResult], WorkerResult],
    ) -> Dict[str, Any]:
        """Executes Hydrogen -> Argon -> Hydrogen Independent QA with 2-attempt repair cap."""
        self.validate_isolated_contracts([contract])
        self._record(self.state, SwarmRole.ARGON_EXECUTE, "Contract validated; dispatching Argon specialist", contract.task_id)

        while True:
            worker_res = argon_executor(contract)
            # Enforce allowed_paths confinement
            allowed = {str(Path(p)) for p in contract.allowed_paths}
            for changed in worker_res.files_changed:
                if str(Path(changed)) not in allowed:
                    raise PermissionError(f"Argon worker modified unauthorized path: {changed}")

            # Auto-switch back to Hydrogen for independent QA (never self-certify)
            self._record(SwarmRole.ARGON_EXECUTE, SwarmRole.HYDROGEN_INDEPENDENT_QA, "Argon finished; switching to Hydrogen independent QA", contract.task_id)
            qa_res = independent_verifier(contract, worker_res)

            if qa_res.worker_id == worker_res.worker_id:
                raise RuntimeError("Independent QA violation: verifier must be distinct from builder worker")

            if qa_res.status == "PASS":
                self._record(SwarmRole.HYDROGEN_INDEPENDENT_QA, SwarmRole.CERTIFIED_CHECKPOINT, "Independent QA passed", contract.task_id)
                return {
                    "final_state": self.state.value,
                    "task_id": contract.task_id,
                    "idempotency_key": contract.idempotency_key,
                    "repair_attempts": self.repair_counts,
                    "transitions": self.transition_log,
                    "qa_evidence": qa_res.raw_evidence,
                }

            defect = qa_res.defect_class or "UNKNOWN_DEFECT"
            self.repair_counts[defect] = self.repair_counts.get(defect, 0) + 1
            if self.repair_counts[defect] > self.MAX_REPAIRS_PER_DEFECT:
                self._record(
                    SwarmRole.HYDROGEN_INDEPENDENT_QA,
                    SwarmRole.BLOCKED_HIL,
                    f"Exceeded max {self.MAX_REPAIRS_PER_DEFECT} repairs for {defect}; escalating to HIL",
                    contract.task_id,
                )
                return {
                    "final_state": self.state.value,
                    "task_id": contract.task_id,
                    "blocked_defect": defect,
                    "repair_attempts": self.repair_counts,
                    "transitions": self.transition_log,
                    "qa_evidence": qa_res.raw_evidence,
                }

            self._record(
                SwarmRole.HYDROGEN_INDEPENDENT_QA,
                SwarmRole.ARGON_EXECUTE,
                f"Repair attempt {self.repair_counts[defect]}/{self.MAX_REPAIRS_PER_DEFECT} for {defect}",
                contract.task_id,
            )
