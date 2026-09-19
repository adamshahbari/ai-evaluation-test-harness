from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes.

    CI needs to distinguish "the outputs regressed" (EVALUATION_FAILED) from
    "the suite itself is broken" (INVALID_DATASET); a single non-zero code would
    make a malformed file look like a genuine regression.
    """

    SUCCESS = 0
    EVALUATION_FAILED = 1
    USAGE_ERROR = 2
    INVALID_DATASET = 3
    INTERNAL_ERROR = 4
