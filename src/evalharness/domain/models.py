from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    weight: float = 1.0
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evaluator type must not be empty")
        return value.strip()

    @field_validator("weight")
    @classmethod
    def _weight_is_sane(cls, value: float) -> float:
        if value < 0:
            raise ValueError("evaluator weight must not be negative")
        return value


class TestCase(BaseModel):
    # pytest collects any class named Test*; this is a domain type, not a suite.
    __test__ = False

    model_config = ConfigDict(extra="forbid")

    id: str
    evaluators: list[EvaluatorSpec]
    input: str | None = None
    expected: Any = None
    actual: Any = None
    tags: list[str] = Field(default_factory=list)
    threshold: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case id must not be empty")
        return value.strip()

    @field_validator("threshold")
    @classmethod
    def _threshold_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return value

    @field_validator("evaluators")
    @classmethod
    def _at_least_one_evaluator(cls, value: list[EvaluatorSpec]) -> list[EvaluatorSpec]:
        if not value:
            raise ValueError("case must declare at least one evaluator")
        return value

    @model_validator(mode="after")
    def _weights_not_all_zero(self) -> TestCase:
        if all(spec.weight == 0 for spec in self.evaluators):
            raise ValueError("case evaluator weights must not all be zero")
        return self

    def has_any_tag(self, tags: set[str]) -> bool:
        return bool(tags & set(self.tags))


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[TestCase]
    sources: list[Path] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def filter_by_tags(self, tags: set[str]) -> Dataset:
        if not tags:
            return self
        return Dataset(
            cases=[case for case in self.cases if case.has_any_tag(tags)],
            sources=self.sources,
        )

    def get(self, case_id: str) -> TestCase | None:
        for case in self.cases:
            if case.id == case_id:
                return case
        return None
