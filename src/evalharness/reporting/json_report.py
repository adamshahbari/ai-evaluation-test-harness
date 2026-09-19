from __future__ import annotations

import json

from evalharness.domain.results import RunSummary

SCHEMA_VERSION = "1.0"


def render(summary: RunSummary) -> str:
    payload = {"schema_version": SCHEMA_VERSION, **summary.to_payload()}
    return json.dumps(payload, indent=2, sort_keys=False)
