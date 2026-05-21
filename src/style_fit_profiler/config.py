"""Configuration models for Style Fit Profiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ALLOWED_REFERENCE_IMAGE_ASPECTS = (
    "rendering",
    "color_light",
    "texture_artifacts",
)

REFERENCE_IMAGE_ANALYSIS_POLICY_FIELDS = frozenset(
    {
        "enabled",
        "input_dir",
        "output_file",
        "aspects",
    }
)


class ConfigValidationError(ValueError):
    """Raised when a configuration value violates the spec."""


@dataclass(frozen=True)
class ReferenceImageAnalysisPolicy:
    """Phase 0 reference image analysis policy.

    This implements P0-01 only: field support and aspect validation. Filesystem
    checks for enabled policies belong to later Phase 0 atomic items.
    """

    enabled: bool = False
    input_dir: str = "reference_images"
    output_file: str = "style_gene_candidates.json"
    aspects: tuple[str, ...] = ALLOWED_REFERENCE_IMAGE_ASPECTS

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ConfigValidationError("reference_image_analysis_policy.enabled must be a boolean")

        input_dir = _validate_non_blank_string("input_dir", self.input_dir)
        output_file = _validate_non_blank_string("output_file", self.output_file)
        aspects = _validate_aspects(self.aspects)

        object.__setattr__(self, "input_dir", input_dir)
        object.__setattr__(self, "output_file", output_file)
        object.__setattr__(self, "aspects", aspects)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | None,
    ) -> "ReferenceImageAnalysisPolicy":
        if value is None:
            return cls()

        if not isinstance(value, Mapping):
            raise ConfigValidationError("reference_image_analysis_policy must be an object")

        unknown_fields = set(value) - REFERENCE_IMAGE_ANALYSIS_POLICY_FIELDS
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ConfigValidationError(f"reference_image_analysis_policy unknown field: {fields}")

        return cls(
            enabled=value.get("enabled", False),
            input_dir=value.get("input_dir", "reference_images"),
            output_file=value.get("output_file", "style_gene_candidates.json"),
            aspects=value.get("aspects", ALLOWED_REFERENCE_IMAGE_ASPECTS),
        )


def _validate_non_blank_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a non-empty string"
        )
    return value


def _validate_aspects(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, tuple | list):
        raise ConfigValidationError("reference_image_analysis_policy.aspects must be a list")

    seen: set[str] = set()
    aspects: list[str] = []

    for aspect in value:
        if aspect in seen:
            raise ConfigValidationError(f"duplicate aspect: {aspect}")
        if aspect not in ALLOWED_REFERENCE_IMAGE_ASPECTS:
            raise ConfigValidationError(f"unsupported aspect: {aspect}")

        seen.add(aspect)
        aspects.append(aspect)

    if not aspects:
        raise ConfigValidationError(
            "reference_image_analysis_policy.aspects must contain at least one aspect"
        )

    return tuple(aspects)
