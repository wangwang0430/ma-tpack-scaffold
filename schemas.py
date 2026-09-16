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
# "fields" object contains all of these keys with non-empty values where
# appropriate. For ethical verification, teacher_review_required is Boolean
# and is validated by VERIFICATION_REPORT_SCHEMA below.
REQUIRED_FIELDS = {
    "content_knowledge": ["content_map", "reading_difficulty", "interpretation_risks"],
    "pedagogy_design": ["activity_sequence", "differentiation", "formative_checks"],
    "technology_affordance": ["ai_use_protocol", "prompt_constraints", "anti_copying_rules"],
    "tpack_integration": ["integrated_lesson", "tpack_rationale", "conflicts"],
    "ethical_verification": ["issues", "teacher_review_required"],
}

# Listing 1 in the final paper: minimal JSON schema for ethical-risk
# verification output. Every issue uses a paper-defined issue_category and
# records evidence, a responsible repair agent, and the required teacher action.
ISSUE_SCHEMA = {
    "type": "object",
    "required": [
        "issue_category",
        "severity",
        "evidence",
        "repair_agent",
        "teacher_action",
    ],
    "properties": {
        "issue_category": {
            "enum": [
                "privacy",
                "bias",
                "hallucination",
                "transparency",
                "over_reliance",
                "age_appropriateness",
                "assessment_fairness",
                "oversight",
            ]
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "evidence": {"type": "string", "minLength": 1},
        "repair_agent": {
            "enum": [
                "content_knowledge",
                "pedagogy_design",
                "technology_affordance",
                "tpack_integration",
                "ethical_verification",
            ]
        },
        "teacher_action": {"type": "string"},
    },
    "additionalProperties": False,
}

VERIFICATION_REPORT_SCHEMA = {
    "type": "object",
    "required": ["issues", "teacher_review_required"],
    "properties": {
        "issues": {"type": "array", "items": ISSUE_SCHEMA},
        "teacher_review_required": {"type": "boolean"},
    },
    "additionalProperties": False,
}
