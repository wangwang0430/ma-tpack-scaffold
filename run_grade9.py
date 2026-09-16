"""
run_grade9.py — Execute the MA-TPACK orchestrator on the Grade 9 English
reading lesson-planning case and emit a real, program-generated TraceLog.

Run:
    python run_grade9.py            # clean run
    python run_grade9.py --fault    # inject a schema fault to show repair routing

To use the real DeepSeek model instead of the deterministic stub:
    export DEEPSEEK_API_KEY=sk-...
    python run_grade9.py --deepseek
"""

import sys
import json
import os
from orchestrator import Orchestrator
from agents import StubBackend, DeepSeekBackend

DESIGN_REQUEST = {
    "subject_domain": "English",
    "topic": "reading comprehension (argument/evidence)",
    "grade_level": 9,
    "duration_minutes": 40,
    "learning_objectives": [
        "reading comprehension",
        "evidence-based interpretation",
        "critical literacy",
    ],
    "learner_profile": "mixed-ability Grade 9 class, three levels",
    "available_technologies": ["DeepSeek"],
    "ethical_constraints": [
        "no student personal data",
        "teacher-facing AI use only",
        "no direct copying of AI output",
    ],
}


def main():
    fault = "--fault" in sys.argv
    use_deepseek = "--deepseek" in sys.argv

    if use_deepseek and os.environ.get("DEEPSEEK_API_KEY"):
        backend = DeepSeekBackend()
        mode = "DeepSeek (live LLM)"
    else:
        backend = StubBackend(inject_fault=fault)
        mode = "Stub (deterministic offline)" + (
            " + injected schema fault" if fault else ""
        )

    orch = Orchestrator(backend)

    print("=== MA-TPACK Scaffold orchestrator ===")
    print(f"Backend: {mode}")
    print("Case:    Grade 9 English reading, 40 min, DeepSeek teacher-facing\n")

    artifact = orch.route(DESIGN_REQUEST)
    report = orch.verify(artifact) if artifact else None

    print("--- TraceLog (program-generated) ---")
    print(f"{'Step':<5}{'Actor':<22}{'Schema status':<22}{'Repair / reroute'}")
    for entry in orch.tracelog():
        print(
            f"{entry['step']:<5}{entry['actor']:<22}"
            f"{entry['schema_status']:<22}{entry['repair_action']}"
        )

    print(f"\nTotal agent calls: {orch.call_count}")
    print(f"Conflicts detected: {len(orch.state.conflict_set)}")
    for conflict in orch.state.conflict_set:
        print(
            f"  - [{conflict['type']}] {conflict['detail']} "
            f"-> repair: {conflict['repair_agent']}"
        )

    print("\nSchema validation per agent:")
    for agent, status in orch.state.schema_validation_status.items():
        print(f"  - {agent:<24}: {status}")

    if report:
        review_required = report["fields"]["teacher_review_required"]
        print(f"\nTeacher review required: {review_required}")
        print(f"Human-review flags ({len(orch.state.teacher_oversight_flags)}):")
        for flag in orch.state.teacher_oversight_flags:
            print(
                f"  - {flag['issue_category']}: {flag['teacher_action']} "
                f"[{flag['repair_agent']}]"
            )

    out = {
        "design_request": DESIGN_REQUEST,
        "tracelog": orch.tracelog(),
        "schema_validation_status": orch.state.schema_validation_status,
        "conflict_set": orch.state.conflict_set,
        "verification_issues": orch.state.verification_issues,
        "teacher_oversight_flags": orch.state.teacher_oversight_flags,
        "teacher_review_required": (
            report["fields"]["teacher_review_required"] if report else None
        ),
        "total_agent_calls": orch.call_count,
        "routing_agent_calls": 5 if not fault else None,
        "verification_agent_calls": 1 if report else 0,
    }
    with open("trace_output.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\n[written] trace_output.json")


if __name__ == "__main__":
    main()
