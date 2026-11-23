"""Strict schemas for the LLM's investigation report.

The LLM may only *interpret* evidence it was given. Every reference must be an evidence ID
(EVIDENCE_###) or a failure-group key (GROUP_#) from the package; the validator rejects or
flags anything else. Hypotheses are always hypotheses: there is no field for "proven cause".
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

INSUFFICIENT_EVIDENCE = "Insufficient evidence to identify a reliable root-cause hypothesis."

Level = Literal["critical", "high", "medium", "low"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(Strict):
    evidence_id: str = Field(..., description="An EVIDENCE_### id from the package")
    explanation: str = Field(..., max_length=600, description="What this evidence item shows, in your words, without new numbers")


class DetectedPattern(Strict):
    description: str = Field(..., max_length=800)
    failure_groups: list[str] = Field(..., max_length=5, description="GROUP_# keys from the package")
    evidence_ids: list[str] = Field(..., max_length=12)


class Hypothesis(Strict):
    title: str = Field(..., max_length=200)
    explanation: str = Field(..., max_length=1200)
    confidence: Literal["low", "medium", "high"] = Field(..., description="Plausibility given the evidence; never certainty")
    related_groups: list[str] = Field(..., max_length=5)
    supporting_evidence: list[EvidenceRef] = Field(..., max_length=10)
    counter_evidence: list[EvidenceRef] = Field(..., max_length=10)
    how_to_test: str = Field(..., max_length=600)


class Assessment(Strict):
    severity: Level
    priority: Literal["high", "medium", "low"]
    rationale: str = Field(..., max_length=800)


class RecommendedExperiment(Strict):
    title: str = Field(..., max_length=200)
    target_group: str = Field(..., description="GROUP_# key the experiment targets")
    hypothesis: str = Field(..., max_length=600)
    proposed_change: str = Field(..., max_length=800)
    test_procedure: str = Field(..., max_length=1000)
    measurement: str = Field(..., max_length=400, description="Which metric to compare before and after")
    success_criterion: str = Field(..., max_length=500)
    expected_outcome: str = Field(..., max_length=500)
    risks: list[str] = Field(..., max_length=6)
    evidence_ids: list[str] = Field(..., max_length=10)


class InvestigationReport(Strict):
    sufficient_evidence: bool
    summary: str = Field(..., max_length=1500)
    main_pattern: DetectedPattern | None
    hypotheses: list[Hypothesis] = Field(..., max_length=5)
    assessment: Assessment | None
    experiments: list[RecommendedExperiment] = Field(..., max_length=4)
    limitations: list[str] = Field(..., max_length=8)


def openai_strict_schema() -> dict:
    """JSON schema in the subset OpenAI's strict structured outputs accept."""
    schema = InvestigationReport.model_json_schema()
    drop = {"maxLength", "minLength", "maxItems", "minItems", "default", "title", "pattern"}

    def fix(node):
        if isinstance(node, dict):
            for k in list(node):
                if k in drop and not isinstance(node[k], dict):
                    node.pop(k)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)
        return node

    return fix(schema)
