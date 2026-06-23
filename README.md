# MA-TPACK Scaffold — Reference Implementation

Supplementary material for:

> **MA-TPACK Scaffold: Architecture and Reference Implementation
> for GenAI-Supported Lesson Planning**
> Zhangnan Wang, Xuanyi Zhao, Fang Zhao
> AIFE 2026 (3rd International Conference on Artificial Intelligence
> and Future Education), Tokyo, Japan

---

## What this is

This repository contains the reference implementation of the
MA-TPACK Scaffold orchestrator described in the paper. The
implementation demonstrates that the two prompt-orchestration
procedures (TPACK-oriented routing and ethical verification)
execute as specified, producing a program-generated TraceLog
with schema validation, conflict detection, repair re-routing,
and ethical-verification flags.

---

## Files

| File | Description |
|------|-------------|
| `schemas.py` | JSON Schema definitions for DesignState, agent outputs, VerificationReport |
| `agents.py` | Pluggable agent backend: StubBackend (offline) and DeepSeekBackend (live API) |
| `orchestrator.py` | Core controller implementing Procedure 1 (routing) and Procedure 2 (verification) |
| `run_grade9.py` | Runner for the Grade 9 English reading lesson-planning case |
| `trace_output.json` | Program-generated execution trace (output of the clean run) |

---

## Requirements

```bash
pip install jsonschema
# For the live DeepSeek backend only:
pip install openai
```

---

## Running

```bash
# Clean run (offline, deterministic)
python run_grade9.py

# Inject a schema fault to demonstrate automatic repair routing
python run_grade9.py --fault

# Live DeepSeek model (requires API key)
export DEEPSEEK_API_KEY=sk-...
python run_grade9.py --deepseek
```

---

## What the output shows

The clean run completes in **6 agent calls**:

- T0: orchestrator normalizes input → DesignState initialized
- T1–T3: CK / PK / TK agents write schema-valid outputs
- T4: TPACK Integration detects a timing conflict → repair routed to Pedagogy Design
- T5: Pedagogy Design returns revised sequence → conflict reduced
- T6: Ethical Verification produces 5 issues; 2 high-severity items
  carried as human-review flags → status: `human_review_required`

The `--fault` run adds a T2 schema failure (missing required field)
and shows automatic re-queue and repair before continuing.

---

## Claim boundary

This implementation demonstrates **execution feasibility**:
schema validation, conflict re-routing, and trace generation
in one lesson-planning case. It does not establish system-level
effectiveness, robustness, or generalizability across cases.
Deployed-system evaluation against single-prompt and
structured-template baselines is reserved for future work.
