"""CR-001 appeal point and art style extraction contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any, Callable

from .gemini_image_probe import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    call_gemini_generate_content,
    extract_response_text,
    read_inline_image_part,
)
from .phase0 import plan_phase0_batches


CR001_EXPECTED_STYLE_LOCI = (
    "genre",
    "line_art",
    "brush_shading",
    "saturation",
    "lighting",
    "texture",
)
CR001_CHARACTER_APPEAL_LOCI = (
    "facial_features",
    "body_type",
    "clothing_genre",
    "clothing_fit",
)
CR001_CANONICAL_LOCI = CR001_EXPECTED_STYLE_LOCI + CR001_CHARACTER_APPEAL_LOCI
CR001_IMPRESSION_COLOR_CHANNELS = ("main", "secondary", "accent")
CR001_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
CR001_NATIVE_ARTIFACT_SCHEMA_VERSION = "cr001.v1"
CR001_NATIVE_ARTIFACT_SOURCE = "cr001_reference_image_analysis"
CR001_NATIVE_ARTIFACT_PATH = "phase0/cr001_reference_image_analysis.json"
CR001_BATCH_RUN_REPORT_PATH = "phase0/cr001_batch_run_report.json"
CR001_BATCH_RUN_REPORT_SOURCE = "cr001_batch_reference_image_analysis"

CR001_ALLELE_REGISTRY = {
    "genre": (
        "cel-shading",
        "anime-heavy-paint",
        "semi-realistic-anime",
        "flat-illustration",
        "2D-pop-art",
        "vintage-manga",
        "watercolor-anime",
        "oil-painterly",
    ),
    "line_art": (
        "clean-line-art",
        "sketchy-lines",
        "dynamic-linework",
        "thick-contours",
        "lineless",
        "colored-line-art",
        "soft-pencil-sketch",
    ),
    "brush_shading": (
        "smooth-airbrush",
        "hard-edge-shadow",
        "textured-brush",
        "impasto-stroke",
        "soft-gradient",
        "cross-hatching",
        "halftone-dot",
    ),
    "saturation": (
        "vibrant-high-saturation",
        "pastel-tones",
        "muted-low-saturation",
        "morandi-palette",
        "monochrome",
        "neon-fluorescent",
    ),
    "lighting": (
        "bright-ambient",
        "high-contrast-chiaroscuro",
        "rim-lighting",
        "soft-volumetric-light",
        "cinematic-backlight",
        "overcast-diffused",
    ),
    "texture": (
        "clean-digital-canvas",
        "grainy-paper",
        "canvas-texture",
        "watercolor-bleed",
        "vintage-film-grain",
        "noise-artifacts",
    ),
    "facial_features": (
        "large-expressive-eyes",
        "tsundere-eyes",
        "soft-blush-cheeks",
        "sharp-jawline",
        "prominent-eyelashes",
        "detailed-hair-highlights",
        "warm-smile",
        "neutral-stare",
    ),
    "body_type": (
        "slender-build",
        "athletic-toned",
        "hourglass-silhouette",
        "petite-proportion",
        "stylized-chibi",
        "realistic-anatomy",
        "elongated-limbs",
    ),
    "clothing_genre": (
        "japanese-school-uniform",
        "classic-sailor-fuku",
        "techwear-futuristic",
        "gothic-lolita",
        "modern-casualwear",
        "fantasy-armor",
        "traditional-kimono",
        "cyberpunk-gear",
    ),
    "clothing_fit": (
        "oversized-fit",
        "tailored-slim-fit",
        "pleated-silhouette",
        "high-waist-cut",
        "asymmetric-layering",
        "puff-sleeves",
        "structural-drapery",
    ),
}


class CR001ValidationError(ValueError):
    """Raised when an in-memory CR-001 record violates the v1 contract."""


@dataclass(frozen=True)
class CR001RawParseResult:
    """Result of the CR-001 raw response valid-raw gate."""

    valid: bool
    source_image: str
    record: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class CR001GeminiRawAnalysis:
    """Raw CR-001 response text for one source image before validation."""

    source_image: str
    response_text: str
    model: str


@dataclass(frozen=True)
class CR001SingleImageExtractionResult:
    """Single-image CR-001 extraction result after the valid-raw gate."""

    valid: bool
    source_image: str
    raw_response_text: str | None = None
    model: str | None = None
    record: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class CR001BatchExtractionResult:
    """File outputs and status summary for CR-001 batch extraction."""

    native_artifact_path: str
    batch_run_report_path: str
    summary: Mapping[str, Any]

    @property
    def has_failed_batches(self) -> bool:
        return int(self.summary.get("failed_batches", 0)) > 0


@dataclass(frozen=True)
class CR001GeminiAnalysisClient:
    """Injectable CR-001 Gemini image-analysis client."""

    api_key: str
    model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    payload_builder: Callable[..., Mapping[str, Any]] | None = None
    generate_content: Callable[..., Mapping[str, Any]] = call_gemini_generate_content

    def __post_init__(self) -> None:
        if self.payload_builder is None:
            object.__setattr__(
                self,
                "payload_builder",
                build_cr001_generate_content_payload,
            )

    def build_payload(self, *, image_path: Path, source_image: str) -> Mapping[str, Any]:
        return self.payload_builder(
            image_path=image_path,
            source_image=source_image,
        )

    def generate_content_response(
        self,
        *,
        image_path: Path,
        source_image: str,
    ) -> Mapping[str, Any]:
        return self.generate_content(
            api_key=self.api_key,
            payload=self.build_payload(
                image_path=image_path,
                source_image=source_image,
            ),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )

    def analyze_image(self, *, image_path: Path, source_image: str) -> str:
        return extract_response_text(
            self.generate_content_response(
                image_path=image_path,
                source_image=source_image,
            )
        )


@dataclass(frozen=True)
class CR001GeminiRawExtractor:
    """Opt-in raw CR-001 extractor backed by an injectable vision client."""

    project_root: Path
    client: Any
    model: str | None = None

    def __call__(
        self,
        reference_image_manifest_records: Sequence[Mapping[str, Any]],
    ) -> tuple[CR001GeminiRawAnalysis, ...]:
        raw_analyses: list[CR001GeminiRawAnalysis] = []
        for record in reference_image_manifest_records:
            source_image = _manifest_record_source_image(record)
            try:
                response_text = self.client.analyze_image(
                    image_path=self.project_root / source_image,
                    source_image=source_image,
                )
            except Exception as error:
                raise RuntimeError(
                    f"CR-001 Gemini raw extraction failed for {source_image}: {error}"
                ) from error
            raw_analyses.append(
                CR001GeminiRawAnalysis(
                    source_image=source_image,
                    response_text=response_text,
                    model=self.model or getattr(self.client, "model", DEFAULT_MODEL),
                )
            )
        return tuple(raw_analyses)


def build_cr001_generate_content_payload(
    *,
    image_path: Path,
    source_image: str,
) -> dict[str, Any]:
    """Build a Gemini generateContent payload for one CR-001 reference image."""

    source_image_error = _source_image_error(source_image)
    if source_image_error is not None:
        raise CR001ValidationError(source_image_error)

    return {
        "contents": [
            {
                "parts": [
                    read_inline_image_part(image_path),
                    {"text": build_cr001_gemini_prompt(source_image_label=source_image)},
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }


def extract_cr001_single_image_record(
    *,
    reference_image_manifest_record: Mapping[str, Any],
    raw_extractor: Callable[..., Sequence[CR001GeminiRawAnalysis]],
) -> CR001SingleImageExtractionResult:
    """Run one CR-001 manifest record through raw extraction and validation."""

    source_image = _manifest_record_source_image(reference_image_manifest_record)
    raw_analyses = tuple(raw_extractor((reference_image_manifest_record,)))
    if len(raw_analyses) != 1:
        return CR001SingleImageExtractionResult(
            valid=False,
            source_image=source_image,
            error="CR-001 single-image extraction expected exactly one raw analysis",
        )

    raw_analysis = raw_analyses[0]
    if raw_analysis.source_image != source_image:
        return CR001SingleImageExtractionResult(
            valid=False,
            source_image=source_image,
            raw_response_text=raw_analysis.response_text,
            model=raw_analysis.model,
            error=(
                "CR-001 single-image extraction source_image mismatch: "
                f"{raw_analysis.source_image}"
            ),
        )

    parse_result = parse_cr001_raw_response(
        raw_response=raw_analysis.response_text,
        source_image=source_image,
    )
    if not parse_result.valid:
        return CR001SingleImageExtractionResult(
            valid=False,
            source_image=source_image,
            raw_response_text=raw_analysis.response_text,
            model=raw_analysis.model,
            error=parse_result.error,
        )

    return CR001SingleImageExtractionResult(
        valid=True,
        source_image=source_image,
        raw_response_text=raw_analysis.response_text,
        model=raw_analysis.model,
        record=parse_result.record,
    )


def run_cr001_batch_extraction(
    *,
    reference_image_manifest_records: Sequence[Mapping[str, Any]],
    run_dir: Path,
    raw_extractor: Callable[..., Sequence[CR001GeminiRawAnalysis]],
    batch_size: int,
    max_attempts: int,
) -> CR001BatchExtractionResult:
    """Run CR-001 extraction in batches and write native artifact plus report."""

    if type(max_attempts) is not int or max_attempts < 1:
        raise CR001ValidationError("CR-001 batch max_attempts must be a positive integer")

    batches = plan_phase0_batches(
        reference_image_manifest_records=reference_image_manifest_records,
        batch_size=batch_size,
    )
    valid_records_by_source: dict[str, dict[str, Any]] = {}
    batch_report_records: list[dict[str, Any]] = []
    image_report_by_source: dict[str, dict[str, Any]] = {}

    for batch in batches:
        remaining_records = list(batch.records)
        failed_errors_by_source: dict[str, str] = {}
        attempt_count = 0

        for attempt_index in range(1, max_attempts + 1):
            if not remaining_records:
                break
            attempt_count = attempt_index
            attempt_results = _run_cr001_batch_attempt(
                records=remaining_records,
                raw_extractor=raw_extractor,
            )
            remaining_records = []
            failed_errors_by_source = {}

            for result in attempt_results:
                image_report_by_source[result.source_image] = _cr001_image_report_record(
                    result=result,
                    batch_index=batch.index,
                    attempt_index=attempt_index,
                )
                if result.valid:
                    valid_records_by_source[result.source_image] = result.record
                    continue
                failed_errors_by_source[result.source_image] = result.error or "unknown error"
                if result.source_image in batch.input_paths:
                    remaining_records.append(
                        _find_manifest_record_by_source(
                            batch.records,
                            result.source_image,
                        )
                    )

        failed_image_paths = [
            source_image
            for source_image in batch.input_paths
            if source_image not in valid_records_by_source
        ]
        status = "failed" if failed_image_paths else "completed"
        batch_has_valid_output = any(
            source_image in valid_records_by_source
            for source_image in batch.input_paths
        )
        batch_report_records.append(
            {
                "batch_index": batch.index,
                "input_paths": list(batch.input_paths),
                "status": status,
                "error": _format_cr001_batch_error(
                    failed_image_paths=failed_image_paths,
                    failed_errors_by_source=failed_errors_by_source,
                ),
                "output_paths": [CR001_NATIVE_ARTIFACT_PATH] if batch_has_valid_output else [],
                "retryable": status == "failed",
                "attempt_count": attempt_count,
                "max_attempts": max_attempts,
                "remaining_attempts": max_attempts - attempt_count,
                "retry_exhausted": status == "failed" and attempt_count >= max_attempts,
                "next_retry_scope": "failed_images" if status == "failed" else None,
                "failed_image_paths": failed_image_paths,
            }
        )

    artifact = build_cr001_native_artifact_document(
        [
            valid_records_by_source[source_image]
            for source_image in sorted(valid_records_by_source)
        ]
    )
    native_artifact_path = write_cr001_native_artifact_document(
        run_dir=run_dir,
        artifact_document=artifact,
    )
    batch_run_report = _build_cr001_batch_run_report(
        batch_records=batch_report_records,
        image_records=[
            image_report_by_source[source_image]
            for source_image in sorted(image_report_by_source)
        ],
    )
    batch_run_report_path = _write_cr001_run_relative_json(
        run_dir=run_dir,
        relative_path=CR001_BATCH_RUN_REPORT_PATH,
        document=batch_run_report,
    )
    return CR001BatchExtractionResult(
        native_artifact_path=native_artifact_path,
        batch_run_report_path=batch_run_report_path,
        summary=batch_run_report["summary"],
    )


def build_cr001_gemini_prompt(source_image_label: str | None = None) -> str:
    """Build the CR-001 v1 restricted-allele Gemini prompt contract."""

    registry_lines = _format_cr001_prompt_registry()
    source_context = ""
    if source_image_label is not None:
        source_context = f"\nSource image label for human review: {source_image_label}\n"

    example_expected_style_genes = _format_cr001_prompt_locus_examples(
        CR001_EXPECTED_STYLE_LOCI
    )
    example_character_appeal_genes = _format_cr001_prompt_locus_examples(
        CR001_CHARACTER_APPEAL_LOCI
    )

    return f"""You are a Visual Style & Appeal Point Encoder for CR-001 v1.
The caller will attach exactly one reference image. Analyze only that image.
{source_context}
Return JSON only. Do not wrap it in markdown.
Do not include source_image.
Do not include schema_version.
Do not include comments, confidence, fitness_score, or any extra keys.

Top-level JSON keys:
- "appeal_point_and_art_style"
- "cr001_summary"

Required payload groups:
- "expected_style_genes": loci {", ".join(CR001_EXPECTED_STYLE_LOCI)}
- "character_appeal_genes": loci {", ".join(CR001_CHARACTER_APPEAL_LOCI)}

For every required locus, return exactly this shape:
{{ "selected": ["one-to-four-allowed-alleles"], "intensity": [0.0-to-1.0] }}

Rules:
- Do not invent allele names, synonyms, aliases, or free-form labels.
- Select 1 to 4 alleles per locus from the allowed registry only.
- Keep intensity length equal to selected length.
- Use numeric intensity values between 0.0 and 1.0.
- "impression_colors" is optional. If present, it is a palette auxiliary object,
  not a selected/intensity allele locus.
- Optional "impression_colors" must contain only "main", "secondary", and
  "accent" as uppercase #RRGGBB strings.
- Keep "cr001_summary" short and do not use it instead of structured genes.

Allowed allele registry:
{registry_lines}

Output shape:
{{
  "appeal_point_and_art_style": {{
    "expected_style_genes": {{
{example_expected_style_genes}
    }},
    "character_appeal_genes": {{
{example_character_appeal_genes}
    }},
    "impression_colors": {{
      "main": "#88C8FF",
      "secondary": "#F8B0D0",
      "accent": "#FFF2A8"
    }}
  }},
  "cr001_summary": "short combined style and appeal summary"
}}"""


def parse_cr001_raw_response(*, raw_response: str, source_image: str) -> CR001RawParseResult:
    """Parse raw CR-001 JSON text into a validated source-linked record."""

    source_image_error = _source_image_error(source_image)
    if source_image_error is not None:
        return CR001RawParseResult(
            valid=False,
            source_image=source_image,
            error=source_image_error,
        )

    try:
        raw_document = json.loads(raw_response)
    except json.JSONDecodeError as error:
        return CR001RawParseResult(
            valid=False,
            source_image=source_image,
            error=f"invalid CR-001 raw JSON: {error.msg}",
        )

    if not isinstance(raw_document, Mapping):
        return CR001RawParseResult(
            valid=False,
            source_image=source_image,
            error="CR-001 raw response must be an object",
        )

    allowed_raw_keys = {"appeal_point_and_art_style", "cr001_summary"}
    unknown_raw_keys = sorted(set(raw_document) - allowed_raw_keys)
    if unknown_raw_keys:
        return CR001RawParseResult(
            valid=False,
            source_image=source_image,
            error=f"CR-001 raw response has unknown key: {', '.join(unknown_raw_keys)}",
        )

    record = {
        "source_image": source_image,
        "appeal_point_and_art_style": raw_document.get("appeal_point_and_art_style"),
        "cr001_summary": raw_document.get("cr001_summary"),
    }

    try:
        validate_cr001_record(record)
    except CR001ValidationError as error:
        return CR001RawParseResult(
            valid=False,
            source_image=source_image,
            error=str(error),
        )

    _normalize_record_palette(record)
    return CR001RawParseResult(valid=True, source_image=source_image, record=record)


def build_cr001_native_artifact_document(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the CR-001 native artifact container without filesystem side effects."""

    if isinstance(records, str) or not isinstance(records, Sequence):
        raise CR001ValidationError("CR-001 native artifact records must be a list")

    artifact_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise CR001ValidationError("CR-001 native artifact record must be an object")
        source_image = record.get("source_image")
        source_image_error = _source_image_error(source_image)
        if source_image_error is not None:
            raise CR001ValidationError(source_image_error)

        validate_cr001_record(record)
        artifact_record = copy.deepcopy(dict(record))
        _normalize_record_palette(artifact_record)
        artifact_records.append(artifact_record)

    return {
        "schema_version": CR001_NATIVE_ARTIFACT_SCHEMA_VERSION,
        "source": CR001_NATIVE_ARTIFACT_SOURCE,
        "records": artifact_records,
    }


def write_cr001_native_artifact_document(
    *,
    run_dir: Path,
    artifact_document: Mapping[str, Any],
) -> str:
    """Write the CR-001 native artifact and return the run-relative path."""

    validate_cr001_native_artifact_document(artifact_document)

    artifact_path = run_dir / CR001_NATIVE_ARTIFACT_PATH
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifact_path.relative_to(run_dir).as_posix()


def validate_cr001_native_artifact_document(artifact_document: Mapping[str, Any]) -> None:
    """Validate the CR-001 native artifact container contract."""

    if not isinstance(artifact_document, Mapping):
        raise CR001ValidationError("CR-001 native artifact must be an object")
    if tuple(artifact_document) != ("schema_version", "source", "records"):
        raise CR001ValidationError(
            "CR-001 native artifact must contain schema_version, source, and records"
        )
    if artifact_document["schema_version"] != CR001_NATIVE_ARTIFACT_SCHEMA_VERSION:
        raise CR001ValidationError("CR-001 native artifact schema_version is invalid")
    if artifact_document["source"] != CR001_NATIVE_ARTIFACT_SOURCE:
        raise CR001ValidationError("CR-001 native artifact source is invalid")

    records = artifact_document["records"]
    if isinstance(records, str) or not isinstance(records, Sequence):
        raise CR001ValidationError("CR-001 native artifact records must be a list")
    for record in records:
        if not isinstance(record, Mapping):
            raise CR001ValidationError("CR-001 native artifact record must be an object")
        source_image_error = _source_image_error(record.get("source_image"))
        if source_image_error is not None:
            raise CR001ValidationError(source_image_error)
        validate_cr001_record(record)


def validate_cr001_record(record: Mapping[str, Any]) -> None:
    """Validate the CR-001 v1 in-memory record shape and canonical gene payload."""

    if not isinstance(record, Mapping):
        raise CR001ValidationError("CR-001 record must be an object")

    payload = record.get("appeal_point_and_art_style")
    if not isinstance(payload, Mapping):
        raise CR001ValidationError(
            "CR-001 record must include appeal_point_and_art_style object"
        )

    summary = record.get("cr001_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise CR001ValidationError("CR-001 record must include non-empty cr001_summary")

    validate_cr001_gene_payload(payload)


def validate_cr001_gene_payload(payload: Mapping[str, Any]) -> None:
    """Validate CR-001 v1 canonical style and appeal gene groups."""

    if not isinstance(payload, Mapping):
        raise CR001ValidationError("CR-001 gene payload must be an object")

    allowed_payload_keys = {
        "expected_style_genes",
        "character_appeal_genes",
        "impression_colors",
    }
    unknown_payload_keys = sorted(set(payload) - allowed_payload_keys)
    if unknown_payload_keys:
        raise CR001ValidationError(
            f"CR-001 gene payload has unknown key: {', '.join(unknown_payload_keys)}"
        )

    _validate_loci_group(
        group_name="expected_style_genes",
        group_payload=payload.get("expected_style_genes"),
        expected_loci=CR001_EXPECTED_STYLE_LOCI,
    )
    _validate_loci_group(
        group_name="character_appeal_genes",
        group_payload=payload.get("character_appeal_genes"),
        expected_loci=CR001_CHARACTER_APPEAL_LOCI,
    )
    if "impression_colors" in payload:
        normalize_cr001_impression_colors(payload["impression_colors"])


def normalize_cr001_impression_colors(impression_colors: Mapping[str, Any]) -> dict[str, str]:
    """Validate and normalize optional CR-001 impression colors."""

    if not isinstance(impression_colors, Mapping):
        raise CR001ValidationError("CR-001 impression_colors must be an object")

    expected_channels = set(CR001_IMPRESSION_COLOR_CHANNELS)
    actual_channels = set(impression_colors)
    missing_channels = sorted(expected_channels - actual_channels)
    unknown_channels = sorted(actual_channels - expected_channels)
    if missing_channels:
        raise CR001ValidationError(
            f"CR-001 impression_colors missing channel: {', '.join(missing_channels)}"
        )
    if unknown_channels:
        raise CR001ValidationError(
            f"CR-001 impression_colors has unknown channel: {', '.join(unknown_channels)}"
        )

    normalized_colors: dict[str, str] = {}
    for channel in CR001_IMPRESSION_COLOR_CHANNELS:
        color = impression_colors[channel]
        if not isinstance(color, str):
            raise CR001ValidationError(
                f"CR-001 impression_colors channel must be a string: {channel}"
            )
        if CR001_HEX_COLOR_PATTERN.fullmatch(color) is None:
            raise CR001ValidationError(
                f"CR-001 impression_colors channel must be #RRGGBB hex: {channel}"
            )
        normalized_colors[channel] = color.upper()

    return normalized_colors


def _validate_loci_group(
    *,
    group_name: str,
    group_payload: Any,
    expected_loci: tuple[str, ...],
) -> None:
    if not isinstance(group_payload, Mapping):
        raise CR001ValidationError(f"CR-001 {group_name} must be an object")

    actual_loci = set(group_payload)
    expected_loci_set = set(expected_loci)
    missing_loci = sorted(expected_loci_set - actual_loci)
    unknown_loci = sorted(actual_loci - expected_loci_set)
    if missing_loci:
        raise CR001ValidationError(
            f"CR-001 {group_name} missing locus: {', '.join(missing_loci)}"
        )
    if unknown_loci:
        raise CR001ValidationError(
            f"CR-001 {group_name} has unknown locus: {', '.join(unknown_loci)}"
        )

    for locus in expected_loci:
        _validate_locus_payload(locus=locus, locus_payload=group_payload[locus])


def _validate_locus_payload(*, locus: str, locus_payload: Any) -> None:
    if not isinstance(locus_payload, Mapping):
        raise CR001ValidationError(f"CR-001 locus must be an object: {locus}")
    if tuple(locus_payload) != ("selected", "intensity"):
        raise CR001ValidationError(
            f"CR-001 locus must contain selected and intensity only: {locus}"
        )

    selected = locus_payload["selected"]
    intensity = locus_payload["intensity"]
    if (
        isinstance(selected, str)
        or not isinstance(selected, Sequence)
        or not 1 <= len(selected) <= 4
    ):
        raise CR001ValidationError(
            f"CR-001 selected must contain 1 to 4 alleles: {locus}"
        )
    if isinstance(intensity, str) or not isinstance(intensity, Sequence):
        raise CR001ValidationError(f"CR-001 intensity must be a list: {locus}")
    if len(selected) != len(intensity):
        raise CR001ValidationError(
            f"CR-001 selected and intensity length mismatch: {locus}"
        )

    allowed_alleles = set(CR001_ALLELE_REGISTRY[locus])
    for allele in selected:
        if not isinstance(allele, str) or allele not in allowed_alleles:
            raise CR001ValidationError(
                f"CR-001 selected allele is not in registry: {locus}"
            )

    for value in intensity:
        if type(value) not in {int, float} or not 0 <= value <= 1:
            raise CR001ValidationError(
                f"CR-001 intensity must be a number between 0 and 1: {locus}"
            )


def _normalize_record_palette(record: dict[str, Any]) -> None:
    payload = record["appeal_point_and_art_style"]
    if "impression_colors" not in payload:
        return
    payload["impression_colors"] = normalize_cr001_impression_colors(
        payload["impression_colors"]
    )


def _source_image_error(source_image: str) -> str | None:
    if not isinstance(source_image, str) or not source_image.strip():
        return "CR-001 source_image must be a non-empty relative path"

    windows_path = PureWindowsPath(source_image)
    if (
        PurePosixPath(source_image).is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
    ):
        return "CR-001 source_image must be a non-empty relative path"

    return None


def _manifest_record_source_image(record: Mapping[str, Any]) -> str:
    if not isinstance(record, Mapping):
        raise CR001ValidationError("CR-001 manifest record must be an object")

    source_image = record.get("path")
    source_image_error = _source_image_error(source_image)
    if source_image_error is not None:
        raise CR001ValidationError(source_image_error)
    return source_image


def _run_cr001_batch_attempt(
    *,
    records: Sequence[Mapping[str, Any]],
    raw_extractor: Callable[..., Sequence[CR001GeminiRawAnalysis]],
) -> tuple[CR001SingleImageExtractionResult, ...]:
    source_images = tuple(_manifest_record_source_image(record) for record in records)
    raw_analyses = tuple(raw_extractor(tuple(records)))
    raw_by_source: dict[str, CR001GeminiRawAnalysis] = {}
    results: list[CR001SingleImageExtractionResult] = []

    for raw_analysis in raw_analyses:
        if raw_analysis.source_image not in source_images:
            results.append(
                CR001SingleImageExtractionResult(
                    valid=False,
                    source_image=raw_analysis.source_image,
                    raw_response_text=raw_analysis.response_text,
                    model=raw_analysis.model,
                    error=(
                        "CR-001 batch extraction unexpected source_image: "
                        f"{raw_analysis.source_image}"
                    ),
                )
            )
            continue
        if raw_analysis.source_image in raw_by_source:
            results.append(
                CR001SingleImageExtractionResult(
                    valid=False,
                    source_image=raw_analysis.source_image,
                    raw_response_text=raw_analysis.response_text,
                    model=raw_analysis.model,
                    error=(
                        "CR-001 batch extraction duplicate source_image: "
                        f"{raw_analysis.source_image}"
                    ),
                )
            )
            continue
        raw_by_source[raw_analysis.source_image] = raw_analysis

    for source_image in source_images:
        raw_analysis = raw_by_source.get(source_image)
        if raw_analysis is None:
            results.append(
                CR001SingleImageExtractionResult(
                    valid=False,
                    source_image=source_image,
                    error="CR-001 batch extraction missing raw analysis",
                )
            )
            continue

        parse_result = parse_cr001_raw_response(
            raw_response=raw_analysis.response_text,
            source_image=source_image,
        )
        if not parse_result.valid:
            results.append(
                CR001SingleImageExtractionResult(
                    valid=False,
                    source_image=source_image,
                    raw_response_text=raw_analysis.response_text,
                    model=raw_analysis.model,
                    error=parse_result.error,
                )
            )
            continue

        results.append(
            CR001SingleImageExtractionResult(
                valid=True,
                source_image=source_image,
                raw_response_text=raw_analysis.response_text,
                model=raw_analysis.model,
                record=parse_result.record,
            )
        )

    return tuple(results)


def _find_manifest_record_by_source(
    records: Sequence[Mapping[str, Any]],
    source_image: str,
) -> Mapping[str, Any]:
    for record in records:
        if _manifest_record_source_image(record) == source_image:
            return record
    raise CR001ValidationError(f"CR-001 batch source image is not in batch: {source_image}")


def _cr001_image_report_record(
    *,
    result: CR001SingleImageExtractionResult,
    batch_index: int,
    attempt_index: int,
) -> dict[str, Any]:
    return {
        "path": result.source_image,
        "batch_index": batch_index,
        "attempt_index": attempt_index,
        "analysis_status": "completed" if result.valid else "failed",
        "model": result.model,
        "error": result.error,
    }


def _format_cr001_batch_error(
    *,
    failed_image_paths: Sequence[str],
    failed_errors_by_source: Mapping[str, str],
) -> str | None:
    if not failed_image_paths:
        return None
    failed_scopes = [
        f"{source_image}: {failed_errors_by_source.get(source_image, 'unknown error')}"
        for source_image in failed_image_paths
    ]
    return "; ".join(failed_scopes)


def _build_cr001_batch_run_report(
    *,
    batch_records: Sequence[Mapping[str, Any]],
    image_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    retryable_batch_indexes = [
        batch_record["batch_index"]
        for batch_record in batch_records
        if batch_record["retryable"]
    ]
    return {
        "schema_version": CR001_NATIVE_ARTIFACT_SCHEMA_VERSION,
        "source": CR001_BATCH_RUN_REPORT_SOURCE,
        "summary": {
            "total_batches": len(batch_records),
            "completed_batches": sum(
                1 for batch_record in batch_records if batch_record["status"] == "completed"
            ),
            "failed_batches": len(retryable_batch_indexes),
            "retryable_batch_indexes": retryable_batch_indexes,
        },
        "batches": [dict(batch_record) for batch_record in batch_records],
        "images": [dict(image_record) for image_record in image_records],
    }


def _write_cr001_run_relative_json(
    *,
    run_dir: Path,
    relative_path: str,
    document: Mapping[str, Any],
) -> str:
    output_path = run_dir / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path.relative_to(run_dir).as_posix()


def _format_cr001_prompt_registry() -> str:
    lines: list[str] = []
    for locus, alleles in CR001_ALLELE_REGISTRY.items():
        quoted_alleles = ", ".join(f'"{allele}"' for allele in alleles)
        lines.append(f'- "{locus}": [{quoted_alleles}]')
    return "\n".join(lines)


def _format_cr001_prompt_locus_examples(loci: tuple[str, ...]) -> str:
    lines: list[str] = []
    for index, locus in enumerate(loci):
        first_allele = CR001_ALLELE_REGISTRY[locus][0]
        suffix = "," if index < len(loci) - 1 else ""
        lines.append(
            f'      "{locus}": {{ "selected": ["{first_allele}"], '
            f'"intensity": [0.8] }}{suffix}'
        )
    return "\n".join(lines)
