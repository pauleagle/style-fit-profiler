"""Phase 0 reference image analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .config import ReferenceImageAnalysisPolicy


SUPPORTED_REFERENCE_IMAGE_EXTENSIONS = frozenset(
    {
        ".bmp",
        ".gif",
        ".jpeg",
        ".jpg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    }
)


class Phase0Error(RuntimeError):
    """Raised when Phase 0 cannot satisfy a spec-defined precondition."""


class Phase0Status(str, Enum):
    """Execution status for the Phase 0 workflow."""

    SKIPPED = "skipped"
    REFERENCE_IMAGES_DISCOVERED = "reference_images_discovered"


@dataclass(frozen=True)
class Phase0Result:
    """Result returned by the Phase 0 workflow runner."""

    status: Phase0Status
    reason: str
    reference_image_paths: tuple[str, ...] = ()


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

    reference_image_paths = discover_reference_images(
        project_root=project_root,
        input_dir=policy.input_dir,
    )

    return Phase0Result(
        status=Phase0Status.REFERENCE_IMAGES_DISCOVERED,
        reason="reference images discovered",
        reference_image_paths=reference_image_paths,
    )


def discover_reference_images(*, project_root: Path, input_dir: str) -> tuple[str, ...]:
    """Discover supported reference images for P0-03.

    P0-03 does not read image metadata or write manifests. It only validates
    that enabled Phase 0 has at least one supported input image.
    """

    reference_dir = project_root / input_dir
    if not reference_dir.is_dir():
        raise Phase0Error(f"reference image directory does not exist: {input_dir}")

    image_paths = tuple(
        sorted(
            (
                path.relative_to(project_root).as_posix()
                for path in reference_dir.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_REFERENCE_IMAGE_EXTENSIONS
            ),
            key=str.casefold,
        )
    )

    if not image_paths:
        raise Phase0Error(f"no supported reference images found in: {input_dir}")

    return image_paths
