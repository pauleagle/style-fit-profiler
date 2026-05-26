"""Configuration models for Style Fit Profiler."""

from __future__ import annotations

from dataclasses import dataclass, field
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
        "provider_retry_policy",
    }
)
PROVIDER_RETRY_POLICY_FIELDS = frozenset(
    {
        "max_attempts",
        "delay_retry_enabled",
        "delay_retry_times",
        "retry_buffer_seconds",
        "default_initial_backoff_seconds",
        "max_single_delay_seconds",
        "max_total_delay_seconds",
        "jitter_enabled",
    }
)


class ConfigValidationError(ValueError):
    """Raised when a configuration value violates the spec."""


@dataclass(frozen=True)
class ProviderRetryPolicy:
    """Config-owned provider retry policy for batch Gemini runtime behavior."""

    max_attempts: int = 3
    delay_retry_enabled: bool = False
    delay_retry_times: int = 2
    retry_buffer_seconds: float = 2
    default_initial_backoff_seconds: float = 5
    max_single_delay_seconds: float = 60
    max_total_delay_seconds: float = 120
    jitter_enabled: bool = True

    def __post_init__(self) -> None:
        max_attempts = _validate_positive_int(
            "provider_retry_policy.max_attempts",
            self.max_attempts,
        )
        delay_retry_enabled = _validate_bool(
            "provider_retry_policy.delay_retry_enabled",
            self.delay_retry_enabled,
        )
        delay_retry_times = _validate_non_negative_int(
            "provider_retry_policy.delay_retry_times",
            self.delay_retry_times,
        )
        retry_buffer_seconds = _validate_non_negative_number(
            "provider_retry_policy.retry_buffer_seconds",
            self.retry_buffer_seconds,
        )
        default_initial_backoff_seconds = _validate_positive_number(
            "provider_retry_policy.default_initial_backoff_seconds",
            self.default_initial_backoff_seconds,
        )
        max_single_delay_seconds = _validate_positive_number(
            "provider_retry_policy.max_single_delay_seconds",
            self.max_single_delay_seconds,
        )
        max_total_delay_seconds = _validate_positive_number(
            "provider_retry_policy.max_total_delay_seconds",
            self.max_total_delay_seconds,
        )
        jitter_enabled = _validate_bool(
            "provider_retry_policy.jitter_enabled",
            self.jitter_enabled,
        )

        object.__setattr__(self, "max_attempts", max_attempts)
        object.__setattr__(self, "delay_retry_enabled", delay_retry_enabled)
        object.__setattr__(
            self,
            "delay_retry_times",
            min(delay_retry_times, max_attempts - 1),
        )
        object.__setattr__(self, "retry_buffer_seconds", retry_buffer_seconds)
        object.__setattr__(
            self,
            "default_initial_backoff_seconds",
            default_initial_backoff_seconds,
        )
        object.__setattr__(self, "max_single_delay_seconds", max_single_delay_seconds)
        object.__setattr__(self, "max_total_delay_seconds", max_total_delay_seconds)
        object.__setattr__(self, "jitter_enabled", jitter_enabled)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ProviderRetryPolicy":
        if value is None:
            return cls()

        if not isinstance(value, Mapping):
            raise ConfigValidationError(
                "reference_image_analysis_policy.provider_retry_policy must be an object"
            )

        unknown_fields = set(value) - PROVIDER_RETRY_POLICY_FIELDS
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ConfigValidationError(
                f"reference_image_analysis_policy.provider_retry_policy unknown field: {fields}"
            )

        return cls(
            max_attempts=value.get("max_attempts", 3),
            delay_retry_enabled=value.get("delay_retry_enabled", False),
            delay_retry_times=value.get("delay_retry_times", 2),
            retry_buffer_seconds=value.get("retry_buffer_seconds", 2),
            default_initial_backoff_seconds=value.get(
                "default_initial_backoff_seconds",
                5,
            ),
            max_single_delay_seconds=value.get("max_single_delay_seconds", 60),
            max_total_delay_seconds=value.get("max_total_delay_seconds", 120),
            jitter_enabled=value.get("jitter_enabled", True),
        )


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
    provider_retry_policy: ProviderRetryPolicy = field(default_factory=ProviderRetryPolicy)

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ConfigValidationError("reference_image_analysis_policy.enabled must be a boolean")

        input_dir = _validate_non_blank_string("input_dir", self.input_dir)
        output_file = _validate_non_blank_string("output_file", self.output_file)
        aspects = _validate_aspects(self.aspects)
        provider_retry_policy = _validate_provider_retry_policy(
            self.provider_retry_policy
        )

        object.__setattr__(self, "input_dir", input_dir)
        object.__setattr__(self, "output_file", output_file)
        object.__setattr__(self, "aspects", aspects)
        object.__setattr__(self, "provider_retry_policy", provider_retry_policy)

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
            provider_retry_policy=ProviderRetryPolicy.from_mapping(
                value.get("provider_retry_policy")
            ),
        )


def _validate_non_blank_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a non-empty string"
        )
    return value


def _validate_provider_retry_policy(value: Any) -> ProviderRetryPolicy:
    if isinstance(value, ProviderRetryPolicy):
        return value
    if isinstance(value, Mapping) or value is None:
        return ProviderRetryPolicy.from_mapping(value)
    raise ConfigValidationError(
        "reference_image_analysis_policy.provider_retry_policy must be an object"
    )


def _validate_bool(field_name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a boolean"
        )
    return value


def _validate_positive_int(field_name: str, value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a positive integer"
        )
    return value


def _validate_non_negative_int(field_name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a non-negative integer"
        )
    return value


def _validate_positive_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a positive number"
        )
    return value


def _validate_non_negative_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ConfigValidationError(
            f"reference_image_analysis_policy.{field_name} must be a non-negative number"
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
