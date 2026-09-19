from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from evalharness.domain.models import Dataset, TestCase
from evalharness.evaluators.base import EvaluatorError
from evalharness.evaluators.registry import build_evaluator
from evalharness.loading.errors import DatasetError

SUFFIXES = {".yaml", ".yml", ".json"}


def _parse(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatasetError(f"cannot read file: {exc.strerror}", source=path) from exc
    try:
        if path.suffix == ".json":
            return json.loads(text)
        return yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"invalid JSON at line {exc.lineno}: {exc.msg}", source=path) from exc
    except yaml.YAMLError as exc:
        raise DatasetError(f"invalid YAML: {exc}", source=path) from exc


def _cases_from_document(document: Any, path: Path) -> list[dict[str, Any]]:
    if document is None:
        raise DatasetError("file is empty", source=path)
    if isinstance(document, list):
        entries = document
    elif isinstance(document, dict):
        if "cases" not in document:
            raise DatasetError("mapping must contain a 'cases' key", source=path)
        entries = document["cases"]
        if not isinstance(entries, list):
            raise DatasetError("'cases' must be a list", source=path)
    else:
        raise DatasetError("expected a list of cases or a mapping with 'cases'", source=path)

    for entry in entries:
        if not isinstance(entry, dict):
            raise DatasetError(
                f"each case must be a mapping, got {type(entry).__name__}", source=path
            )
    return entries


def discover(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix not in SUFFIXES:
            raise DatasetError(
                f"unsupported extension {path.suffix!r}; expected one of {sorted(SUFFIXES)}",
                source=path,
            )
        return [path]
    if path.is_dir():
        found = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in SUFFIXES)
        if not found:
            raise DatasetError("no .yaml, .yml or .json files found", source=path)
        return found
    raise DatasetError("path does not exist", source=path)


def load_dataset(path: Path) -> Dataset:
    sources = discover(path)
    cases: list[TestCase] = []
    seen: dict[str, Path] = {}

    for source in sources:
        for index, entry in enumerate(_cases_from_document(_parse(source), source)):
            try:
                case = TestCase.model_validate(entry)
            except ValidationError as exc:
                first = exc.errors()[0]
                location = ".".join(str(part) for part in first["loc"]) or "<case>"
                identifier = entry.get("id", f"<case {index}>")
                raise DatasetError(
                    f"case {identifier!r}: {location}: {first['msg']}", source=source
                ) from exc

            if case.id in seen:
                raise DatasetError(
                    f"duplicate case id {case.id!r} (also defined in {seen[case.id]})",
                    source=source,
                )
            seen[case.id] = source

            for spec in case.evaluators:
                try:
                    build_evaluator(spec.type, spec.config)
                except EvaluatorError as exc:
                    raise DatasetError(f"case {case.id!r}: {exc}", source=source) from exc

            cases.append(case)

    if not cases:
        raise DatasetError("no cases defined", source=path)
    return Dataset(cases=cases, sources=sources)
