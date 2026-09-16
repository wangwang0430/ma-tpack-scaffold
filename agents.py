"""
agents.py — Pluggable agent backend for MA-TPACK Scaffold.

The orchestrator calls agents through a single interface, AgentBackend.run(...).
Two implementations are provided:

  * StubBackend   — deterministic offline responses mirroring the execution
                    trace reported in the paper. Lets the full orchestration
                    pipeline run, validate, detect conflicts, and log WITHOUT
                    network access, so the architecture's behavior is
                    reproducible and testable.

  * DeepSeekBackend — real LLM calls via the DeepSeek API. Swap this in by
                    setting DEEPSEEK_API_KEY; the orchestration logic is
                    unchanged.

Only the content-generation step differs between backends. Routing, schema
validation, conflict detection, repair routing, and logging are all performed
by the orchestrator and are identical in both modes.
"""

from __future__ import annotations
import os
import json


class AgentBackend:
    def run(self, agent_id: str, prompt_package: dict) -> dict:
        raise NotImplementedError


# ----------------------------------------------------------------------------
# Deterministic offline backend (mirrors the paper's worked example)
# ----------------------------------------------------------------------------
class StubBackend(AgentBackend):
    """Returns fixed, schema-shaped outputs for the Grade 9 reading case.

    `inject_fault` deliberately produces a schema-invalid Pedagogy output on
    the first call, demonstrating schema-failure detection and repair routing.
    """

    def __init__(self, inject_fault: bool = False):
        self.inject_fault = inject_fault
        self._pedagogy_calls = 0

    def run(self, agent_id: str, prompt_package: dict) -> dict:
        return getattr(self, f"_{agent_id}")(prompt_package)

    def _content_knowledge(self, p):
        return {
            "agent_id": "content_knowledge",
            "prompt_role": p["prompt_role"],
            "tpack_dimension": "CK",
            "fields": {
                "content_map": "Grade 9 persuasive/expository reading text; argument structure, "
                               "claim-evidence relations, cohesive devices.",
                "reading_difficulty": "Tier-2/Tier-3 vocabulary barriers; complex cohesion; "
                                      "inference gaps; background-knowledge demands.",
                "interpretation_risks": "Authorial intent, tone, and any statistical/cultural "
                                        "references require teacher verification against the "
                                        "actual passage.",
            },
        }

    def _pedagogy_design(self, p):
        self._pedagogy_calls += 1
        if self.inject_fault and self._pedagogy_calls == 1:
            return {
                "agent_id": "pedagogy_design",
                "prompt_role": p["prompt_role"],
                "tpack_dimension": "PK",
                "fields": {
                    "activity_sequence": "Anticipation guide; while-reading annotation; "
                                         "claim-evidence-reasoning discussion; exit slip.",
                    "differentiation": "Tiered glossary, partial graphic organizer, sentence starters.",
                    # 'formative_checks' intentionally omitted -> schema-invalid
                },
            }
        return {
            "agent_id": "pedagogy_design",
            "prompt_role": p["prompt_role"],
            "tpack_dimension": "PK",
            "fields": {
                "activity_sequence": "Pre-reading anticipation guide (5m); while-reading "
                                     "annotation (15m); post-reading claim-evidence-reasoning "
                                     "discussion (10m); Traffic-Light exit slip (5m).",
                "differentiation": "Three learner levels: tiered glossary, partially completed "
                                   "graphic organizer, sentence starters for developing readers.",
                "formative_checks": "Annotation quality check; CER discussion observation; "
                                    "exit-slip self-rating.",
            },
        }

    def _technology_affordance(self, p):
        return {
            "agent_id": "technology_affordance",
            "prompt_role": p["prompt_role"],
            "tpack_dimension": "TK/TPK",
            "fields": {
                "ai_use_protocol": "DeepSeek as teacher-only planning tool: difficulty analysis, "
                                   "scaffold drafting, formative-question generation, reflection.",
                "prompt_constraints": "No full lesson-plan generation; no student-facing output "
                                      "without teacher rewriting; no student personal data.",
                "anti_copying_rules": "Teacher must adapt AI-generated sentence starters to the "
                                      "actual text; document which scaffold elements were AI-drafted.",
            },
        }

    def _tpack_integration(self, p):
        return {
            "agent_id": "tpack_integration",
            "prompt_role": p["prompt_role"],
            "tpack_dimension": "integrated_TPACK",
            "fields": {
                "integrated_lesson": "CK+PK+TK synthesis with teacher-mediated DeepSeek use and "
                                     "assessment evidence.",
                "tpack_rationale": "AI confined to teacher planning functions where a model "
                                   "second-reader perspective adds value beyond single-author review.",
                "conflicts": [
                    {
                        "type": "timing",
                        "detail": "While-reading annotation (15m) + post-reading discussion (10m) "
                                  "risks exceeding the 40-minute constraint.",
                        "repair_agent": "pedagogy_design",
                    }
                ],
            },
        }

    def _ethical_verification(self, p):
        # The issue objects follow Listing 1 in the final paper exactly:
        # issue_category, severity, evidence, repair_agent, teacher_action.
        # Context-specific concerns such as an unverified interpretation and
        # weak learner adaptation are represented in evidence while keeping
        # issue_category within the paper-defined enumeration.
        return {
            "agent_id": "ethical_verification",
            "prompt_role": p["prompt_role"],
            "tpack_dimension": "ethical_risk",
            "fields": {
                "issues": [
                    {
                        "issue_category": "privacy",
                        "severity": "low",
                        "evidence": "The design request contains no student personal data and confines AI use to teacher-facing planning.",
                        "repair_agent": "ethical_verification",
                        "teacher_action": "Confirm that no student personal data are entered during enactment.",
                    },
                    {
                        "issue_category": "hallucination",
                        "severity": "medium",
                        "evidence": "AI-drafted interpretations may contain unsupported claims unless checked against the source passage.",
                        "repair_agent": "content_knowledge",
                        "teacher_action": "Verify AI-drafted interpretations against the text.",
                    },
                    {
                        "issue_category": "over_reliance",
                        "severity": "medium",
                        "evidence": "AI-generated explanations could be copied into teacher talk without independent pedagogical review.",
                        "repair_agent": "technology_affordance",
                        "teacher_action": "Do not copy AI explanations into teacher talk verbatim.",
                    },
                    {
                        "issue_category": "hallucination",
                        "severity": "high",
                        "evidence": "Unverified text interpretation remains unresolved because the controller does not have the actual textbook passage.",
                        "repair_agent": "content_knowledge",
                        "teacher_action": "Complete a Text Verification Record before enactment.",
                    },
                    {
                        "issue_category": "oversight",
                        "severity": "high",
                        "evidence": "Weak learner adaptation remains unresolved because the controller cannot verify scaffold fit without the actual learner profile.",
                        "repair_agent": "pedagogy_design",
                        "teacher_action": "Calibrate scaffolds to the actual learner profile.",
                    },
                ],
                "teacher_review_required": True,
            },
        }


# ----------------------------------------------------------------------------
# Real DeepSeek backend (used when DEEPSEEK_API_KEY is set; same interface)
# ----------------------------------------------------------------------------
class DeepSeekBackend(AgentBackend):
    """Calls the DeepSeek chat-completions API. Drop-in replacement for the stub.

    Requires: pip install openai ; DeepSeek is OpenAI-API-compatible.
    The orchestrator is unchanged — only content generation moves to the model.
    """

    def __init__(self, model: str = "deepseek-chat"):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self.model = model

    def run(self, agent_id: str, prompt_package: dict) -> dict:
        system = prompt_package["system_prompt"]
        user = prompt_package["user_prompt"]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        return json.loads(raw)
