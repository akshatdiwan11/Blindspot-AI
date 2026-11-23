"""Evaluation configuration schema (validated with Pydantic)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TextEvalConfig(BaseModel):
    match: Literal["normalized_exact", "exact", "token_f1", "similarity"] = "normalized_exact"
    threshold: float = Field(0.8, ge=0.0, le=1.0, description="Score needed to count as correct for token_f1 / similarity matching.")
    lowercase: bool = True
    strip_punctuation: bool = True
    remove_articles: bool = True
    compute_similarity: bool = True


class ClassificationEvalConfig(BaseModel):
    case_sensitive: bool = False
    positive_label: str | None = None


class JsonEvalConfig(BaseModel):
    criterion: Literal["exact", "field_accuracy"] = "exact"
    field_threshold: float = Field(1.0, ge=0.0, le=1.0)
    ignore_extra_fields: bool = False
    case_sensitive_values: bool = False
    list_order_insensitive: bool = True
    json_schema: dict[str, Any] | None = Field(default=None, description="Optional JSON Schema the actual output should satisfy.")


class DiscoveryConfig(BaseModel):
    min_group_size: int = Field(20, ge=5, le=100000)
    alpha: float = Field(0.05, gt=0, lt=0.5, description="False discovery rate for Benjamini-Hochberg correction.")
    max_tree_depth: int = Field(3, ge=1, le=5)
    numeric_bins: int = Field(4, ge=2, le=10)
    derive_text_features: bool = True
    max_groups: int = Field(25, ge=1, le=200)


class ClusteringConfig(BaseModel):
    enabled: bool = True
    max_clusters: int = Field(8, ge=2, le=30)
    use_embeddings: bool = False


class EvaluationConfig(BaseModel):
    task_type: Literal["classification", "text", "json"]
    label: str = Field("", max_length=120)
    text: TextEvalConfig = TextEvalConfig()
    classification: ClassificationEvalConfig = ClassificationEvalConfig()
    json_eval: JsonEvalConfig = Field(default_factory=JsonEvalConfig, alias="json")
    discovery: DiscoveryConfig = DiscoveryConfig()
    clustering: ClusteringConfig = ClusteringConfig()

    model_config = {"populate_by_name": True}

    def to_storage(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
