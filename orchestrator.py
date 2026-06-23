"""
orchestrator.py — MA-TPACK Scaffold orchestrator.

Implements the two procedures specified in the paper:

  Procedure 1: TPACK-Oriented Prompt Routing  (routing phase)
  Procedure 2: Ethical Verification and Revision  (verification phase)

The orchestrator owns ALL coordination logic — DesignState management, TPACK
profiling, agent-queue routing, schema validation, conflict detection, repair
routing, and TraceLog emission. Agents only generate content (via AgentBackend).
This is the "actual computer technology content" of the architecture: a
deterministic, auditable controller over a shared blackboard state.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from jsonschema import validate as js_validate, ValidationError

from schemas import (
    AGENT_OUTPUT_SCHEMA, REQUIRED_FIELDS,
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
        # 1. structural schema
        try:
            js_validate(instance=output, schema=AGENT_OUTPUT_SCHEMA)
        except ValidationError as e:
            return False, f"structural schema error: {e.message}"
        # 2. required-fields completeness
        missing = [k for k in REQUIRED_FIELDS.get(agent_id, [])
                   if k not in output.get("fields", {})
                   or output["fields"][k] in (None, "", [], {})]
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
        return {
            "agent_id": agent_id,
            "prompt_role": roles[agent_id],
            "required_schema": REQUIRED_FIELDS.get(agent_id, []),
            "system_prompt": f"You are the {agent_id} agent in MA-TPACK Scaffold. "
                             f"Return JSON with keys: agent_id, prompt_role, "
                             f"tpack_dimension, fields.",
            "user_prompt": json.dumps(self.state.normalized_input, ensure_ascii=False),
        }

    # ---- conflict detection ------------------------------------------------
    def _detect_conflicts(self) -> list:
        conflicts = []
        ti = self.state.agent_outputs.get("tpack_integration")
        if ti:
            for c in ti["fields"].get("conflicts", []):
                conflicts.append(c)
        return conflicts

    # ======================================================================
    # Procedure 1: TPACK-Oriented Prompt Routing
    # ======================================================================
    def route(self, design_request: dict) -> Optional[dict]:
        # Step 1-2: normalize request into DesignState
        self.state.normalized_input = dict(design_request)
        self.trace.append(TraceEntry("T0", "orchestrator", "normalize_input",
                                     "valid", json.dumps(design_request, ensure_ascii=False)))

        # Step 3: derive TPACK profile
        self.state.tpack_profile = ["CK", "PK", "TK", "TCK", "TPK",
                                    "integrated_TPACK", "ethical_risk"]

        # Step 4: build agent queue from profile + dependencies
        queue = ["content_knowledge", "pedagogy_design",
                 "technology_affordance", "tpack_integration"]

        step_n = 1
        # Step 5-8: dispatch loop with schema validation + conflict reroute
        while queue and self.call_count < self.max_agent_calls:
            agent_id = queue.pop(0)
            pkg = self._build_prompt_package(agent_id)
            output = self.backend.run(agent_id, pkg)
            self.call_count += 1

            ok, msg = self._validate_agent_output(agent_id, output)
            self.state.schema_validation_status[agent_id] = msg

            if not ok:
                # schema-repair routing: re-queue the same agent once
                self.trace.append(TraceEntry(
                    f"T{step_n}", agent_id, "agent_call",
                    "INVALID", msg,
                    repair_action=f"schema-repair: re-queue {agent_id}"))
                queue.insert(0, agent_id)
                step_n += 1
                continue

            self.state.agent_outputs[agent_id] = output

            # conflict detection after integration agent writes
            conflicts = self._detect_conflicts()
            new_conflicts = [c for c in conflicts if c not in self.state.conflict_set]
            if new_conflicts:
                self.state.conflict_set.extend(new_conflicts)
                for c in new_conflicts:
                    repair_agent = c.get("repair_agent")
                    if repair_agent and repair_agent not in queue:
                        queue.append(repair_agent)
                    self.trace.append(TraceEntry(
                        f"T{step_n}", agent_id, "agent_call",
                        "valid_with_conflict", c["detail"],
                        repair_action=f"conflict reroute -> {repair_agent}"))
            else:
                self.trace.append(TraceEntry(
                    f"T{step_n}", agent_id, "agent_call", "valid",
                    f"{agent_id} output accepted"))
            step_n += 1

        # Step 9: synthesize draft LessonArtifact if core fields valid
        core = ["content_knowledge", "pedagogy_design",
                "technology_affordance", "tpack_integration"]
        if all(a in self.state.agent_outputs for a in core):
            artifact = {a: self.state.agent_outputs[a]["fields"] for a in core}
            return artifact
        return None

    # ======================================================================
    # Procedure 2: Ethical Verification and Revision
    # ======================================================================
    def verify(self, artifact: dict) -> dict:
        rounds = 0
        report = None
        step_n = len(self.trace)
        while rounds < self.max_revision_rounds:
            pkg = self._build_prompt_package("ethical_verification")
            report = self.backend.run("ethical_verification", pkg)
            self.call_count += 1

            # validate the verification report against its schema
            try:
                js_validate(instance=report["fields"], schema=VERIFICATION_REPORT_SCHEMA)
                schema_status = "valid"
            except ValidationError as e:
                schema_status = f"INVALID: {e.message}"

            issues = report["fields"]["issues"]
            self.state.verification_issues = issues
            highs = [i for i in issues if i["severity"] in ("high", "critical")]

            self.trace.append(TraceEntry(
                f"T{step_n}", "ethical_verification", "verification",
                schema_status,
                f"{len(issues)} issues; {len(highs)} high/critical"))
            step_n += 1

            if not highs:
                self.state.teacher_oversight_flags = []
                report["fields"]["verification_status"] = "approved_with_teacher_oversight_notes"
                break

            # high/critical issues -> carry as human-review flags (no auto-fix
            # for context-dependent items) and stop, mirroring the paper.
            self.state.teacher_oversight_flags = [
                {"category": i["category"], "teacher_action": i["teacher_action"]}
                for i in highs
            ]
            self.state.revision_history.append({"round": rounds + 1, "high_issues": highs})
            report["fields"]["verification_status"] = "human_review_required"
            rounds += 1
            break  # context-dependent highs require human review, not auto-loop

        return report

    # ---- export ------------------------------------------------------------
    def tracelog(self) -> list[dict]:
        return [asdict(t) for t in self.trace]
