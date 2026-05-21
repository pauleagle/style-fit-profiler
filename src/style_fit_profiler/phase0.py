"""Phase 0 reference image analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .config import ReferenceImageAnalysisPolicy


class Phase0Status(str, Enum):
    """Execution status for the Phase 0 workflow."""

    SKIPPED = "skipped"


@dataclass(frozen=True)
class Phase0Result:
    """Result returned by the Phase 0 workflow runner."""

    status: Phase0Status
    reason: str


Phase0Extractor = Callable[..., Any]


def run_phase0(
    *,
    policy: ReferenceImageAnalysisPolicy,
    project_root: Path,
    run_dir: Path,
    extractor: Phase0Extractor | None = None,
) -> Phase0Result:
    """Run Phase 0 according to the provided policy.

    P0-02 only defines the disabled path. Image discovery and extractor
    invocation are intentionally deferred to later atomic items.
    """

    if not policy.enabled:
        return Phase0Result(
            status=Phase0Status.SKIPPED,
            reason="reference image analysis disabled",
        )

    raise NotImplementedError("enabled Phase 0 execution starts at P0-03")
