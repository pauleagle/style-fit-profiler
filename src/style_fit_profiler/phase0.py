"""Phase 0 reference image analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping, Protocol, Sequence

from .config import ALLOWED_REFERENCE_IMAGE_ASPECTS, ReferenceImageAnalysisPolicy


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

STYLE_GENE_CANDIDATES_VERSION = "0.1.0"
STYLE_GENE_CANDIDATES_SOURCE = "phase0_reference_image_analysis"
STYLE_GENE_CANDIDATE_ASPECTS = ALLOWED_REFERENCE_IMAGE_ASPECTS
STYLE_GENE_CANDIDATE_FIELDS = (
    "id",
    "prompt",
    "confidence",
    "source_images",
    "notes",
)
MOCK_EXTRACTOR_PROMPTS_BY_ASPECT = {
    "rendering": "mock rendering traits",
    "color_light": "mock color and light traits",
    "texture_artifacts": "mock texture and artifact traits",
}


class Phase0Error(RuntimeError):
    """Raised when Phase 0 cannot satisfy a spec-defined precondition."""


class Phase0Status(str, Enum):
    """Execution status for the Phase 0 workflow."""

    SKIPPED = "skipped"
    REFERENCE_IMAGES_DISCOVERED = "reference_images_discovered"
    REFERENCE_IMAGE_MANIFEST_WRITTEN = "reference_image_manifest_written"


@dataclass(frozen=True)
class Phase0Result:
    """Result returned by the Phase 0 workflow runner."""

    status: Phase0Status
    reason: str
    reference_image_paths: tuple[str, ...] = ()
    reference_image_manifest_path: str | None = None


@dataclass(frozen=True)
class StyleGeneCandidate:
    """Schema record for one Phase 0 candidate style gene."""

    id: str
    prompt: str
    confidence: float
    source_images: tuple[str, ...]
    notes: str = ""

    def to_json_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "confidence": self.confidence,
            "source_images": list(self.source_images),
            "notes": self.notes,
        }


ReferenceImageManifestRecord = Mapping[str, Any]
CandidateGenesByAspect = Mapping[str, Sequence[StyleGeneCandidate]]


class Phase0Extractor(Protocol):
    """Callable contract for Phase 0 candidate gene extractors."""

    def __call__(
        self,
        reference_image_manifest_records: Sequence[ReferenceImageManifestRecord],
    ) -> CandidateGenesByAspect:
        """Return candidate style genes grouped by Phase 0 aspect."""


def extract_style_gene_candidates(
    *,
    extractor: Phase0Extractor,
    reference_image_manifest_records: Sequence[ReferenceImageManifestRecord],
) -> dict[str, tuple[StyleGeneCandidate, ...]]:
    """Call a Phase 0 extractor without granting it output-file ownership."""

    candidates_by_aspect = {
        aspect: tuple(candidates)
        for aspect, candidates in extractor(reference_image_manifest_records).items()
    }
    validate_style_gene_candidate_aspects(candidates_by_aspect)
    return candidates_by_aspect


def validate_style_gene_candidate_aspects(
    candidates_by_aspect: Mapping[str, Sequence[StyleGeneCandidate]],
) -> None:
    """Validate P0-09 aspect keys and candidate ID prefixes."""

    if not isinstance(candidates_by_aspect, Mapping):
        raise Phase0Error("Phase 0 candidate gene aspects must be an object")

    expected_aspects = set(STYLE_GENE_CANDIDATE_ASPECTS)
    actual_aspects = set(candidates_by_aspect)
    missing_aspects = sorted(expected_aspects - actual_aspects)
    unknown_aspects = sorted(actual_aspects - expected_aspects)

    if missing_aspects:
        raise Phase0Error(f"Phase 0 candidate gene missing aspect: {', '.join(missing_aspects)}")
    if unknown_aspects:
        raise Phase0Error(f"Phase 0 candidate gene unknown aspect: {', '.join(unknown_aspects)}")

    for aspect in STYLE_GENE_CANDIDATE_ASPECTS:
        candidates = candidates_by_aspect[aspect]
        if isinstance(candidates, str) or not isinstance(candidates, Sequence):
            raise Phase0Error(f"Phase 0 candidate gene aspect must contain a list: {aspect}")

        for candidate in candidates:
            if not isinstance(candidate, StyleGeneCandidate):
                raise Phase0Error("Phase 0 candidate gene aspect must contain StyleGeneCandidate records")
            if not candidate.id.startswith(f"{aspect}_"):
                raise Phase0Error(
                    f"Phase 0 candidate gene id prefix does not match aspect: {candidate.id}"
                )


def deterministic_mock_phase0_extractor(
    reference_image_manifest_records: Sequence[ReferenceImageManifestRecord],
) -> dict[str, tuple[StyleGeneCandidate, ...]]:
    """Build deterministic P0-08 candidate genes from manifest records."""

    candidates_by_aspect: dict[str, list[StyleGeneCandidate]] = {
        aspect: [] for aspect in STYLE_GENE_CANDIDATE_ASPECTS
    }

    for record in sorted(reference_image_manifest_records, key=_manifest_record_sort_key):
        source_image = _manifest_record_path(record)
        source_token = _style_gene_id_token(source_image)
        source_label = source_token.replace("_", " ")
        source_digest = hashlib.sha256(source_image.encode("utf-8")).hexdigest()[:8]

        for aspect_index, aspect in enumerate(STYLE_GENE_CANDIDATE_ASPECTS):
            candidates_by_aspect[aspect].append(
                StyleGeneCandidate(
                    id=f"{aspect}_{source_token}_{source_digest}",
                    prompt=f"{MOCK_EXTRACTOR_PROMPTS_BY_ASPECT[aspect]} from {source_label}",
                    confidence=round(0.55 + (aspect_index * 0.05), 2),
                    source_images=(source_image,),
                    notes="deterministic mock extractor",
                )
            )

    return {
        aspect: tuple(candidates)
        for aspect, candidates in candidates_by_aspect.items()
    }


def _manifest_record_sort_key(record: ReferenceImageManifestRecord) -> str:
    return _manifest_record_path(record).casefold()


def _manifest_record_path(record: ReferenceImageManifestRecord) -> str:
    path = record.get("path")
    if not isinstance(path, str) or not path.strip():
        raise Phase0Error("reference image manifest record must include a relative path")
    return path


def _style_gene_id_token(source_image: str) -> str:
    stem = PurePosixPath(source_image.replace("\\", "/")).stem
    token_characters = [
        character.lower() if character.isalnum() else "_"
        for character in stem
    ]
    token = "_".join("".join(token_characters).split("_"))
    return token or "reference_image"


def build_style_gene_candidates_document(
    *,
    candidates_by_aspect: Mapping[str, Sequence[StyleGeneCandidate]] | None = None,
) -> dict[str, Any]:
    """Build the P0-05 style_gene_candidates.json document shape."""

    candidates_by_aspect = candidates_by_aspect or {}

    return {
        "version": STYLE_GENE_CANDIDATES_VERSION,
        "source": STYLE_GENE_CANDIDATES_SOURCE,
        "aspects": {
            aspect: [
                candidate.to_json_record()
                for candidate in candidates_by_aspect.get(aspect, ())
            ]
            for aspect in STYLE_GENE_CANDIDATE_ASPECTS
        },
    }


def validate_style_gene_candidates_document(document: Mapping[str, Any]) -> None:
    """Validate a P0-06 candidate gene document."""

    if not isinstance(document, Mapping):
        raise Phase0Error("Phase 0 candidate gene schema invalid: document must be an object")

    aspects = document.get("aspects")
    if not isinstance(aspects, Mapping):
        raise Phase0Error("Phase 0 candidate gene schema invalid: aspects must be an object")

    seen_ids: set[str] = set()
    for aspect in STYLE_GENE_CANDIDATE_ASPECTS:
        if aspect not in aspects:
            raise Phase0Error(f"Phase 0 candidate gene schema invalid: missing aspect: {aspect}")

    for aspect, candidates in aspects.items():
        if isinstance(candidates, str) or not isinstance(candidates, Sequence):
            raise Phase0Error(
                f"Phase 0 candidate gene schema invalid: aspect must contain a list: {aspect}"
            )

        for candidate in candidates:
            _validate_candidate_gene_record(candidate, seen_ids)


def _validate_candidate_gene_record(candidate: Any, seen_ids: set[str]) -> None:
    if not isinstance(candidate, Mapping):
        raise Phase0Error("Phase 0 candidate gene schema invalid: candidate must be an object")

    missing_fields = [field for field in STYLE_GENE_CANDIDATE_FIELDS if field not in candidate]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise Phase0Error(f"Phase 0 candidate gene schema invalid: missing candidate field: {fields}")

    candidate_id = candidate["id"]
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise Phase0Error("Phase 0 candidate gene schema invalid: candidate id must be non-empty")
    if candidate_id in seen_ids:
        raise Phase0Error(f"Phase 0 candidate gene schema invalid: duplicate candidate gene id: {candidate_id}")
    seen_ids.add(candidate_id)

    prompt = candidate["prompt"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise Phase0Error("Phase 0 candidate gene schema invalid: prompt must be non-empty")

    confidence = candidate["confidence"]
    if type(confidence) not in {int, float} or not 0 <= confidence <= 1:
        raise Phase0Error("Phase 0 candidate gene schema invalid: confidence must be between 0 and 1")

    _validate_source_images(candidate["source_images"])

    notes = candidate["notes"]
    if not isinstance(notes, str):
        raise Phase0Error("Phase 0 candidate gene schema invalid: notes must be a string")


def _validate_source_images(source_images: Any) -> None:
    if (
        isinstance(source_images, str)
        or not isinstance(source_images, Sequence)
        or not source_images
    ):
        raise Phase0Error(
            "Phase 0 candidate gene schema invalid: source_images must contain at least one relative path"
        )

    for source_image in source_images:
        if not isinstance(source_image, str) or not source_image.strip():
            raise Phase0Error(
                "Phase 0 candidate gene schema invalid: source_images must contain relative paths"
            )
        windows_path = PureWindowsPath(source_image)
        if (
            PurePosixPath(source_image).is_absolute()
            or bool(windows_path.drive)
            or bool(windows_path.root)
        ):
            raise Phase0Error(
                "Phase 0 candidate gene schema invalid: source_images must contain relative paths"
            )


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
    reference_image_manifest_path = write_reference_image_manifest(
        project_root=project_root,
        run_dir=run_dir,
        reference_image_paths=reference_image_paths,
    )

    return Phase0Result(
        status=Phase0Status.REFERENCE_IMAGE_MANIFEST_WRITTEN,
        reason="reference image manifest written",
        reference_image_paths=reference_image_paths,
        reference_image_manifest_path=reference_image_manifest_path,
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


def write_reference_image_manifest(
    *,
    project_root: Path,
    run_dir: Path,
    reference_image_paths: tuple[str, ...],
) -> str:
    """Write the P0-04 reference image manifest and return its run-relative path."""

    manifest = {
        "version": "0.1.0",
        "source": "phase0_reference_image_analysis",
        "images": [
            _build_reference_image_manifest_record(
                project_root=project_root,
                reference_image_path=reference_image_path,
            )
            for reference_image_path in reference_image_paths
        ],
    }

    manifest_path = run_dir / "phase0" / "reference_image_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path.relative_to(run_dir).as_posix()


def _build_reference_image_manifest_record(
    *,
    project_root: Path,
    reference_image_path: str,
) -> dict[str, Any]:
    image_path = project_root / reference_image_path
    image_bytes = image_path.read_bytes()
    width, height = _read_image_size(image_bytes, image_path)

    return {
        "path": reference_image_path,
        "file_hash": f"sha256:{hashlib.sha256(image_bytes).hexdigest()}",
        "image_size": {"width": width, "height": height},
        "analysis_status": "pending",
    }


def _read_image_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    suffix = image_path.suffix.lower()

    if suffix == ".png":
        return _read_png_size(image_bytes, image_path)
    if suffix in {".jpg", ".jpeg"}:
        return _read_jpeg_size(image_bytes, image_path)
    if suffix == ".gif":
        return _read_gif_size(image_bytes, image_path)
    if suffix == ".bmp":
        return _read_bmp_size(image_bytes, image_path)
    if suffix == ".webp":
        return _read_webp_size(image_bytes, image_path)
    if suffix in {".tif", ".tiff"}:
        return _read_tiff_size(image_bytes, image_path)

    raise Phase0Error(f"unsupported reference image format: {image_path.as_posix()}")


def _read_png_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if len(image_bytes) >= 24 and image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return (
            int.from_bytes(image_bytes[16:20], "big"),
            int.from_bytes(image_bytes[20:24], "big"),
        )
    raise Phase0Error(f"cannot read PNG image size: {image_path.as_posix()}")


def _read_jpeg_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if not image_bytes.startswith(b"\xff\xd8"):
        raise Phase0Error(f"cannot read JPEG image size: {image_path.as_posix()}")

    start_of_frame_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    offset = 2

    while offset < len(image_bytes):
        while offset < len(image_bytes) and image_bytes[offset] != 0xFF:
            offset += 1
        while offset < len(image_bytes) and image_bytes[offset] == 0xFF:
            offset += 1
        if offset >= len(image_bytes):
            break

        marker = image_bytes[offset]
        offset += 1

        if marker == 0xD9 or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(image_bytes):
            break

        segment_length = int.from_bytes(image_bytes[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(image_bytes):
            break

        if marker in start_of_frame_markers and segment_length >= 7:
            return (
                int.from_bytes(image_bytes[offset + 5 : offset + 7], "big"),
                int.from_bytes(image_bytes[offset + 3 : offset + 5], "big"),
            )

        offset += segment_length

    raise Phase0Error(f"cannot read JPEG image size: {image_path.as_posix()}")


def _read_gif_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if len(image_bytes) >= 10 and image_bytes[:6] in {b"GIF87a", b"GIF89a"}:
        return (
            int.from_bytes(image_bytes[6:8], "little"),
            int.from_bytes(image_bytes[8:10], "little"),
        )
    raise Phase0Error(f"cannot read GIF image size: {image_path.as_posix()}")


def _read_bmp_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if len(image_bytes) < 26 or not image_bytes.startswith(b"BM"):
        raise Phase0Error(f"cannot read BMP image size: {image_path.as_posix()}")

    dib_header_size = int.from_bytes(image_bytes[14:18], "little")
    if dib_header_size == 12 and len(image_bytes) >= 22:
        return (
            int.from_bytes(image_bytes[18:20], "little"),
            int.from_bytes(image_bytes[20:22], "little"),
        )

    return (
        int.from_bytes(image_bytes[18:22], "little", signed=True),
        abs(int.from_bytes(image_bytes[22:26], "little", signed=True)),
    )


def _read_webp_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if len(image_bytes) < 20 or image_bytes[:4] != b"RIFF" or image_bytes[8:12] != b"WEBP":
        raise Phase0Error(f"cannot read WebP image size: {image_path.as_posix()}")

    offset = 12
    while offset + 8 <= len(image_bytes):
        chunk_type = image_bytes[offset : offset + 4]
        chunk_size = int.from_bytes(image_bytes[offset + 4 : offset + 8], "little")
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        payload = image_bytes[payload_start:payload_end]

        if payload_end > len(image_bytes):
            break
        if chunk_type == b"VP8X" and len(payload) >= 10:
            width = int.from_bytes(payload[4:7], "little") + 1
            height = int.from_bytes(payload[7:10], "little") + 1
            return (width, height)
        if chunk_type == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            bits = int.from_bytes(payload[1:5], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        if chunk_type == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(payload[6:8], "little") & 0x3FFF
            height = int.from_bytes(payload[8:10], "little") & 0x3FFF
            return (width, height)

        offset = payload_end + (chunk_size % 2)

    raise Phase0Error(f"cannot read WebP image size: {image_path.as_posix()}")


def _read_tiff_size(image_bytes: bytes, image_path: Path) -> tuple[int, int]:
    if len(image_bytes) < 8:
        raise Phase0Error(f"cannot read TIFF image size: {image_path.as_posix()}")

    if image_bytes[:4] == b"II*\x00":
        byte_order = "little"
    elif image_bytes[:4] == b"MM\x00*":
        byte_order = "big"
    else:
        raise Phase0Error(f"cannot read TIFF image size: {image_path.as_posix()}")

    ifd_offset = int.from_bytes(image_bytes[4:8], byte_order)
    if ifd_offset + 2 > len(image_bytes):
        raise Phase0Error(f"cannot read TIFF image size: {image_path.as_posix()}")

    entry_count = int.from_bytes(image_bytes[ifd_offset : ifd_offset + 2], byte_order)
    width: int | None = None
    height: int | None = None

    for entry_index in range(entry_count):
        entry_offset = ifd_offset + 2 + (entry_index * 12)
        if entry_offset + 12 > len(image_bytes):
            break

        tag = int.from_bytes(image_bytes[entry_offset : entry_offset + 2], byte_order)
        field_type = int.from_bytes(image_bytes[entry_offset + 2 : entry_offset + 4], byte_order)
        count = int.from_bytes(image_bytes[entry_offset + 4 : entry_offset + 8], byte_order)
        value_bytes = image_bytes[entry_offset + 8 : entry_offset + 12]

        if count != 1 or field_type not in {3, 4}:
            continue

        if field_type == 3:
            value = int.from_bytes(value_bytes[:2], byte_order)
        else:
            value = int.from_bytes(value_bytes, byte_order)

        if tag == 256:
            width = value
        elif tag == 257:
            height = value

    if width is not None and height is not None:
        return (width, height)

    raise Phase0Error(f"cannot read TIFF image size: {image_path.as_posix()}")
