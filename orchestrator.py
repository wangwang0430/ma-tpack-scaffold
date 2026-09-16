"""
orchestrator.py — MA-TPACK Scaffold orchestrator.

Implements the two procedures specified in the paper:

  Procedure 1: TPACK-Oriented Prompt Routing  (routing phase)
  Procedure 2: Ethical Verification and Revision  (verification phase)

The orchestrator owns all coordination logic — DesignState management, TPACK
profiling, agent-queue routing, schema validation, conflict detection, repair
routing, and TraceLog emission. Agents only generate content (via AgentBackend).
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from jsonschema import validate as js_validate, ValidationError

from schemas import (
    AGENT_OUTPUT_SCHEMA,
    REQUIRED_FIELDS,
    VERIFICATION_REPORT_SCHEMA,
)
from agents import AgentBackend


# ----------------------------------------------------------------------------
# Shared DesignState — the blackboard coordination substrate
# ----------------------------------------------------------------------------
@dataclass
class DesignState:
    normalized_input: dict = field(default_factory=dict)
    tpack_profile: list = field(default_factory=list)
    agent_outputs: dict = field(default_factory=dict)
    conflict_set: list = field(default_factory=list)
    verification_issues: list = field(default_factory=list)
    teacher_oversight_flags: list = field(default_factory=list)
    revision_history: list = field(default_factory=list)
    schema_validation_status: dict = field(default_factory=dict)


@dataclass
class TraceEntry:
    step: str
    actor: str
    action: str
    schema_status: str
    detail: str = ""
    repair_action: str = ""


class Orchestrator:
    def __init__(self, backend: AgentBackend, max_agent_calls: int = 12,
                 max_revision_rounds: int = 3):
        self.backend = backend
        self.max_agent_calls = max_agent_calls
        self.max_revision_rounds = max_revision_rounds
        self.state = DesignState()
        self.trace: list[TraceEntry] = []
        self.call_count = 0

    # ---- schema validation -------------------------------------------------
    def _validate_agent_output(self, agent_id: str, output: dict) -> tuple[bool, str]:
        try:
            js_validate(instance=output, schema=AGENT_OUTPUT_SCHEMA)
        except ValidationError as e:
            return False, f"structural schema error: {e.message}"

        fields = output.get("fields", {})
        missing = []
        for key in REQUIRED_FIELDS.get(agent_id, []):
            if key not in fields:
                missing.append(key)
                continue
            value = fields[key]
            # Boolean False is a valid value for teacher_review_required.
            if value is None or value == "" or value == [] or value == {}:
                missing.append(key)
        if missing:
            return False, f"missing required fields: {missing}"
        return True, "valid"

    # ---- prompt contract (typed PromptPackage) -----------------------------
    def _build_prompt_package(self, agent_id: str) -> dict:
        roles = {
            "content_knowledge": "reading_difficulty_analysis",
            "pedagogy_design": "differentiated_reading_scaffold_generation",
            "technology_affordance": "ai_use_protocol_specification",
            "tpack_integration": "integrated_lesson_artifact",
            "ethical_verification": "ethical_risk_check",
        }
        system_prompt = (
            f"You are the {agent_id} agent in MA-TPACK Scaffold. "
            "Return JSON with keys: agent_id, prompt_role, tpack_dimension, fields."
        )
        if agent_id == "ethical_verification":
            system_prompt += (
                " In fields, return issues and teacher_review_required. Each issue must "
                "contain issue_category, severity, evidence, repair_agent, and teacher_action. "
                "Allowed issue_category values are privacy, bias, hallucination, transparency, "
                "over_reliance, age_appropriateness, assessment_fairness, and oversight."
            )
        return {
            "agent_id": agent_id,
            "prompt_role": roles[agent_id],
            "required_schema": REQUIRED_FIELDS.get(agent_id, []),
            "system_prompt": system_prompt,
            "user_prompt": json.dumps(self.state.normalized_input, ensure_ascii=False),
        }

    # ---- conflict detection ------------------------------------------------
    def _detect_conflicts(self) -> list:
        conflicts = []
        ti = self.state.agent_outputs.get("tpack_integration")
        if ti:
            for conflict in ti["fields"].get("conflicts", []):
                conflicts.append(conflict)
        return conflicts

    # ======================================================================
    # Procedure 1: TPACK-Oriented Prompt Routing
    # ======================================================================
    def route(self, design_request: dict) -> Optional[dict]:
        self.state.normalized_input = dict(design_request)
        self.trace.append(
            TraceEntry(
                "T0",
                "orchestrator",
                "normalize_input",
                "valid",
                json.dumps(design_request, ensure_ascii=False),
            )
        )

        self.state.tpack_profile = [
            "CK", "PK", "TK", "TCK", "TPK", "integrated_TPACK", "ethical_risk"
        ]

        queue = [
            "content_knowledge",
            "pedagogy_design",
            "technology_affordance",
            "tpack_integration",
        ]

        step_n = 1
        while queue and self.call_count < self.max_agent_calls:
            agent_id = queue.pop(0)
            pkg = self._build_prompt_package(agent_id)
            output = self.backend.run(agent_id, pkg)
            self.call_count += 1

            ok, msg = self._validate_agent_output(agent_id, output)
            self.state.schema_validation_status[agent_id] = msg

            if not ok:
                self.trace.append(
                    TraceEntry(
                        f"T{step_n}",
                        agent_id,
                        "agent_call",
                        "INVALID",
                        msg,
                        repair_action=f"schema-repair: re-queue {agent_id}",
                    )
                )
                queue.insert(0, agent_id)
                step_n += 1
                continue

            self.state.agent_outputs[agent_id] = output

            conflicts = self._detect_conflicts()
            new_conflicts = [c for c in conflicts if c not in self.state.conflict_set]
            if new_conflicts:
                self.state.conflict_set.extend(new_conflicts)
                for conflict in new_conflicts:
                    repair_agent = conflict.get("repair_agent")
                    if repair_agent and repair_agent not in queue:
                        queue.append(repair_agent)
                    self.trace.append(
                        TraceEntry(
                            f"T{step_n}",
                            agent_id,
                            "agent_call",
                            "valid_with_conflict",
                            conflict["detail"],
                            repair_action=f"conflict reroute -> {repair_agent}",
                        )
                    )
            else:
                self.trace.append(
                    TraceEntry(
                        f"T{step_n}",
                        agent_id,
                        "agent_call",
                        "valid",
                        f"{agent_id} output accepted",
                    )
                )
            step_n += 1

        core = [
            "content_knowledge",
            "pedagogy_design",
            "technology_affordance",
            "tpack_integration",
        ]
        if all(agent in self.state.agent_outputs for agent in core):
            return {agent: self.state.agent_outputs[agent]["fields"] for agent in core}
        return None

    # ======================================================================
    # Procedure 2: Ethical Verification and Revision
    # ======================================================================
    def verify(self, artifact: dict) -> dict:
        # The worked example performs one verification call after the five-call
        # routing phase. Context-dependent high-severity issues that cannot be
        # repaired without the actual text/learner profile are surfaced for
        # teacher review, matching the final paper's claim boundary.
        pkg = self._build_prompt_package("ethical_verification")
        report = self.backend.run("ethical_verification", pkg)
        self.call_count += 1

        try:
            js_validate(instance=report["fields"], schema=VERIFICATION_REPORT_SCHEMA)
            schema_status = "valid"
            self.state.schema_validation_status["ethical_verification"] = "valid"
        except ValidationError as e:
            schema_status = f"INVALID: {e.message}"
            self.state.schema_validation_status["ethical_verification"] = schema_status

        issues = report["fields"].get("issues", [])
        self.state.verification_issues = issues
        highs = [i for i in issues if i.get("severity") in ("high", "critical")]

        # The final report-level Boolean is derived from unresolved high/critical
        # issues. This is the exact field defined by Listing 1 in the paper.
        teacher_review_required = bool(highs)
        report["fields"]["teacher_review_required"] = teacher_review_required

        if teacher_review_required:
            self.state.teacher_oversight_flags = [
                {
                    "issue_category": issue["issue_category"],
                    "evidence": issue["evidence"],
                    "repair_agent": issue["repair_agent"],
                    "teacher_action": issue["teacher_action"],
                }
                for issue in highs
            ]
            self.state.revision_history.append(
                {"round": 1, "unresolved_high_issues": highs}
            )
        else:
            self.state.teacher_oversight_flags = []

        step_n = len(self.trace)
        self.trace.append(
            TraceEntry(
                f"T{step_n}",
                "ethical_verification",
                "verification",
                schema_status,
                f"{len(issues)} issues; {len(highs)} high/critical; "
                f"teacher_review_required={teacher_review_required}",
            )
        )

        return report

    # ---- export ------------------------------------------------------------
    def tracelog(self) -> list[dict]:
        return [asdict(entry) for entry in self.trace]
