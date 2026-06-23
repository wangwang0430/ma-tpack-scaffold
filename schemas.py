"""
schemas.py — Formal JSON Schema definitions for MA-TPACK Scaffold objects.

These schemas operationalize the "schema-constrained outputs" claim in the paper:
every agent output is validated against a required schema before it is written
to the shared DesignState. A failed validation triggers a schema-repair request.
"""

# Each agent must return an object whose "fields" cover its required_fields.
AGENT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["agent_id", "prompt_role", "tpack_dimension", "fields"],
    "properties": {
        "agent_id": {"type": "string"},
        "prompt_role": {"type": "string"},
        "tpack_dimension": {"type": "string"},
        "fields": {"type": "object"},
    },
    "additionalProperties": True,
}

# Required field keys per agent. The orchestrator checks that an agent's
# "fields" object contains all of these keys with non-empty values.
REQUIRED_FIELDS = {
    "content_knowledge": ["content_map", "reading_difficulty", "interpretation_risks"],
    "pedagogy_design": ["activity_sequence", "differentiation", "formative_checks"],
    "technology_affordance": ["ai_use_protocol", "prompt_constraints", "anti_copying_rules"],
    "tpack_integration": ["integrated_lesson", "tpack_rationale", "conflicts"],
    "ethical_verification": ["issues", "verification_status"],
}

# A single verification issue must carry severity and a responsible repair agent.
ISSUE_SCHEMA = {
    "type": "object",
    "required": ["category", "severity", "repair_agent", "teacher_action"],
    "properties": {
        "category": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "repair_agent": {"type": "string"},
        "teacher_action": {"type": "string"},
    },
}

VERIFICATION_REPORT_SCHEMA = {
    "type": "object",
    "required": ["issues", "verification_status"],
    "properties": {
        "issues": {"type": "array", "items": ISSUE_SCHEMA},
        "verification_status": {
            "type": "string",
            "enum": [
                "approved",
                "approved_with_teacher_oversight_notes",
                "human_review_required",
            ],
        },
    },
}
