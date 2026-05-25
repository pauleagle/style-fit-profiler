"""CR-001 appeal point and art style extraction contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


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
