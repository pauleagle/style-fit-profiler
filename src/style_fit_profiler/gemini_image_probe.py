"""Small Gemini image-analysis probe for local Phase 0 experiments."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import ProviderRetryPolicy
from .phase0 import StyleGeneCandidate


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_IMAGE_RUN_DIR = Path("runs/manual-gemini-single")
DEFAULT_IMAGE_BACKEND = "cr001"
LEGACY_IMAGE_BACKEND = "legacy"
CR001_IMAGE_BACKEND = "cr001"
GEMINI_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
MAX_INLINE_IMAGE_BYTES = 19 * 1024 * 1024
GEMINI_EXPERIMENTAL_CONFIDENCE = 0.5
GEMINI_TRAIT_ASPECTS = (
    "rendering",
    "color_light",
    "texture_artifacts",
)
GEMINI_TRAIT_RESPONSE_KEYS = frozenset((*GEMINI_TRAIT_ASPECTS, "notes"))
GEMINI_PROVIDER_RETRY_AFTER_PATTERN = re.compile(
    r"\bretry\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s\b",
    re.IGNORECASE,
)
GEMINI_PROVIDER_STATUS_ERROR_TYPES = {
    "RESOURCE_EXHAUSTED": "provider_quota_exhausted",
    "UNAVAILABLE": "provider_unavailable",
    "INTERNAL": "provider_internal_error",
    "DEADLINE_EXCEEDED": "provider_timeout",
    "INVALID_ARGUMENT": "invalid_request",
    "UNAUTHENTICATED": "auth_error",
    "PERMISSION_DENIED": "permission_error",
}
GEMINI_PROVIDER_HTTP_STATUS_ERROR_TYPES = {
    429: "provider_quota_exhausted",
    500: "provider_internal_error",
    503: "provider_unavailable",
    504: "provider_timeout",
}
GEMINI_RETRYABLE_PROVIDER_STATUSES = frozenset(
    {
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "INTERNAL",
        "DEADLINE_EXCEEDED",
    }
)
GEMINI_RETRYABLE_PROVIDER_ERROR_TYPES = frozenset(
    {
        "provider_quota_exhausted",
        "provider_unavailable",
        "provider_internal_error",
        "provider_timeout",
    }
)
GEMINI_PROVIDER_HTTP_ERROR_PATTERN = re.compile(
    r"\bGemini API HTTP\s+([0-9]{3})\b",
    re.IGNORECASE,
)

DEFAULT_ANALYSIS_PROMPT = """Analyze this local reference image for a style-fit profiler.

Return only JSON with this exact top-level shape:
{
  "rendering": ["short reusable prompt gene", "..."],
  "color_light": ["short reusable prompt gene", "..."],
  "texture_artifacts": ["short reusable prompt gene", "..."],
  "notes": "brief visual summary"
}

Rules:
- Focus on reusable visual style traits, not object identity.
- Keep each gene short enough to reuse in an image generation prompt.
- Do not invent artist names, copyrighted character names, or private identity claims.
- If a category has no clear traits, return an empty list for that category.
"""

DEFAULT_BATCH_ANALYSIS_PROMPT = """Analyze each local reference image for a style-fit profiler.

Return only JSON with this exact top-level shape:
{
  "images": [
    {
      "path": "reference_images/example.png",
      "rendering": ["short reusable prompt gene", "..."],
      "color_light": ["short reusable prompt gene", "..."],
      "texture_artifacts": ["short reusable prompt gene", "..."],
      "notes": "brief visual summary"
    }
  ]
}

Rules:
- Return exactly one image record for each input path label.
- Use the exact input path label in each image record.
- Analyze each image independently; do not merge traits across images.
- Focus on reusable visual style traits, not object identity.
- Keep each gene short enough to reuse in an image generation prompt.
- Do not invent artist names, copyrighted character names, or private identity claims.
- If a category has no clear traits, return an empty list for that category.
"""


class GeminiImageProbeError(RuntimeError):
    """Raised when the Gemini image probe cannot complete."""


@dataclass(frozen=True)
class GeminiProviderError:
    """Normalized Gemini provider error metadata for retry decisions."""

    type: str
    provider_status: str | None = None
    retryable: bool = False
    message: str = ""
    retry_after_seconds: float | None = None
    provider_http_status: int | None = None


def gemini_provider_error_to_json_record(
    provider_error: GeminiProviderError,
) -> dict[str, Any]:
    return {
        "type": provider_error.type,
        "provider_status": provider_error.provider_status,
        "retryable": provider_error.retryable,
        "message": provider_error.message,
        "retry_after_seconds": provider_error.retry_after_seconds,
        "provider_http_status": provider_error.provider_http_status,
    }


@dataclass(frozen=True)
class ProviderRetryDecision:
    """Retry and optional wait decision for provider runtime errors."""

    should_retry: bool
    remaining_attempts: int
    wait_seconds: float | None = None
    delay_retry_allowed: bool = False
    total_delay_after_wait_seconds: float = 0


@dataclass(frozen=True)
class GeminiImageTraitAnalysis:
    """Normalized Gemini trait analysis for one source image."""

    source_image: str
    traits_by_aspect: Mapping[str, tuple[str, ...]]
    notes: str = ""

    def to_json_record(self) -> dict[str, Any]:
        return {
            "path": self.source_image,
            "traits": {
                aspect: list(self.traits_by_aspect[aspect])
                for aspect in GEMINI_TRAIT_ASPECTS
            },
            "notes": self.notes,
        }


def extract_gemini_retry_after_seconds(message: str) -> float | None:
    if not isinstance(message, str) or not message:
        return None

    match = GEMINI_PROVIDER_RETRY_AFTER_PATTERN.search(message)
    if match is None:
        return None
    return float(match.group(1))


def classify_gemini_provider_error(error: object) -> GeminiProviderError:
    payload = _gemini_provider_error_payload(error)
    error_record = (
        payload.get("error")
        if isinstance(payload.get("error"), Mapping)
        else payload
    )
    status = _normalize_gemini_provider_status(error_record.get("status"))
    http_status = _normalize_gemini_provider_http_status(error_record.get("code"))
    message = error_record.get("message", "")
    if not isinstance(message, str):
        message = str(message)

    error_type = GEMINI_PROVIDER_STATUS_ERROR_TYPES.get(
        status or "",
        GEMINI_PROVIDER_HTTP_STATUS_ERROR_TYPES.get(
            http_status,
            "unknown_provider_error",
        ),
    )
    return GeminiProviderError(
        type=error_type,
        provider_status=status,
        retryable=(
            status in GEMINI_RETRYABLE_PROVIDER_STATUSES
            or error_type in GEMINI_RETRYABLE_PROVIDER_ERROR_TYPES
        ),
        message=message,
        retry_after_seconds=extract_gemini_retry_after_seconds(message),
        provider_http_status=http_status,
    )


def resolve_provider_retry_decision(
    *,
    provider_error: GeminiProviderError,
    policy: ProviderRetryPolicy,
    attempt_index: int,
    total_delay_seconds: float = 0,
    delay_retry_count: int = 0,
) -> ProviderRetryDecision:
    attempt_index = _normalize_positive_int("attempt_index", attempt_index)
    total_delay_seconds = _normalize_non_negative_number(
        "total_delay_seconds",
        total_delay_seconds,
    )
    delay_retry_count = _normalize_non_negative_int(
        "delay_retry_count",
        delay_retry_count,
    )

    remaining_attempts = max(policy.max_attempts - attempt_index, 0)
    if not provider_error.retryable or remaining_attempts < 1:
        return ProviderRetryDecision(
            should_retry=False,
            remaining_attempts=remaining_attempts,
            total_delay_after_wait_seconds=total_delay_seconds,
        )

    wait_seconds = _resolve_provider_retry_wait_seconds(
        provider_error=provider_error,
        policy=policy,
        total_delay_seconds=total_delay_seconds,
        delay_retry_count=delay_retry_count,
    )
    return ProviderRetryDecision(
        should_retry=True,
        remaining_attempts=remaining_attempts,
        wait_seconds=wait_seconds,
        delay_retry_allowed=wait_seconds is not None,
        total_delay_after_wait_seconds=(
            total_delay_seconds
            if wait_seconds is None
            else total_delay_seconds + wait_seconds
        ),
    )


def sleep_for_provider_retry_delay(
    decision: ProviderRetryDecision,
    *,
    sleeper: Callable[[float], object],
) -> None:
    if decision.wait_seconds is not None and decision.wait_seconds > 0:
        sleeper(decision.wait_seconds)


def _resolve_provider_retry_wait_seconds(
    *,
    provider_error: GeminiProviderError,
    policy: ProviderRetryPolicy,
    total_delay_seconds: float,
    delay_retry_count: int,
) -> float | None:
    if not policy.delay_retry_enabled:
        return None
    if delay_retry_count >= policy.delay_retry_times:
        return None

    remaining_total_delay_seconds = max(
        policy.max_total_delay_seconds - total_delay_seconds,
        0,
    )
    if remaining_total_delay_seconds <= 0:
        return None

    retry_after_seconds = (
        provider_error.retry_after_seconds
        if provider_error.retry_after_seconds is not None
        else policy.default_initial_backoff_seconds
    )
    return min(
        retry_after_seconds + policy.retry_buffer_seconds,
        policy.max_single_delay_seconds,
        remaining_total_delay_seconds,
    )


def _gemini_provider_error_payload(error: object) -> Mapping[str, Any]:
    if isinstance(error, Mapping):
        return error

    text = str(error)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        try:
            payload = json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping):
            return payload

    http_match = GEMINI_PROVIDER_HTTP_ERROR_PATTERN.search(text)
    if http_match is not None:
        return {"code": int(http_match.group(1)), "message": text}

    return {"message": text}


def _normalize_gemini_provider_status(status: Any) -> str | None:
    if not isinstance(status, str):
        return None
    normalized_status = status.strip().upper()
    return normalized_status or None


def _normalize_gemini_provider_http_status(code: Any) -> int | None:
    if isinstance(code, bool):
        return None
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.strip().isdigit():
        return int(code.strip())
    return None


def _normalize_positive_int(field_name: str, value: Any) -> int:
    if type(value) is not int or value < 1:
        raise GeminiImageProbeError(f"{field_name} must be a positive integer")
    return value


def _normalize_non_negative_int(field_name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise GeminiImageProbeError(f"{field_name} must be a non-negative integer")
    return value


def _normalize_non_negative_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise GeminiImageProbeError(f"{field_name} must be a non-negative number")
    return value


def parse_gemini_trait_response(response_text: str) -> dict[str, tuple[str, ...]]:
    """Parse EXP-001A Gemini JSON text into normalized aspect traits."""

    try:
        response = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise GeminiImageProbeError(f"invalid Gemini trait JSON: {error.msg}") from error

    if not isinstance(response, Mapping):
        raise GeminiImageProbeError("Gemini trait response must be a JSON object")

    unknown_keys = sorted(set(response) - GEMINI_TRAIT_RESPONSE_KEYS)
    if unknown_keys:
        raise GeminiImageProbeError(f"Gemini trait response unknown key: {', '.join(unknown_keys)}")

    if "notes" in response and not isinstance(response["notes"], str):
        raise GeminiImageProbeError("Gemini trait response notes must be a string")

    traits_by_aspect: dict[str, tuple[str, ...]] = {}
    for aspect in GEMINI_TRAIT_ASPECTS:
        if aspect not in response:
            raise GeminiImageProbeError(f"Gemini trait response missing aspect: {aspect}")

        aspect_traits = response[aspect]
        if isinstance(aspect_traits, str) or not isinstance(aspect_traits, list):
            raise GeminiImageProbeError(f"Gemini trait response aspect must be a list: {aspect}")

        traits_by_aspect[aspect] = tuple(
            _normalize_gemini_trait(trait=trait, aspect=aspect)
            for trait in aspect_traits
        )

    return traits_by_aspect


def parse_gemini_batch_trait_response(
    response_text: str,
    *,
    expected_source_images: Sequence[str],
) -> tuple[GeminiImageTraitAnalysis, ...]:
    """Parse EXP batch Gemini JSON text into one analysis per source image."""

    expected_sources = tuple(
        _normalize_source_image_path(source_image)
        for source_image in expected_source_images
    )
    if not expected_sources:
        raise GeminiImageProbeError("Gemini batch response expected sources cannot be empty")

    try:
        response = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise GeminiImageProbeError(f"invalid Gemini batch trait JSON: {error.msg}") from error

    if not isinstance(response, Mapping):
        raise GeminiImageProbeError("Gemini batch trait response must be a JSON object")

    unknown_keys = sorted(set(response) - {"images"})
    if unknown_keys:
        raise GeminiImageProbeError(
            f"Gemini batch trait response unknown key: {', '.join(unknown_keys)}"
        )

    images = response.get("images")
    if isinstance(images, str) or not isinstance(images, list):
        raise GeminiImageProbeError("Gemini batch trait response images must be a list")

    expected_source_set = set(expected_sources)
    seen_sources: set[str] = set()
    analyses: list[GeminiImageTraitAnalysis] = []

    for image_record in images:
        analysis = _parse_gemini_batch_image_record(
            image_record=image_record,
            expected_source_set=expected_source_set,
        )
        if analysis.source_image in seen_sources:
            raise GeminiImageProbeError(
                f"Gemini batch trait response duplicate image: {analysis.source_image}"
            )
        seen_sources.add(analysis.source_image)
        analyses.append(analysis)

    missing_sources = [
        source_image
        for source_image in expected_sources
        if source_image not in seen_sources
    ]
    if missing_sources:
        raise GeminiImageProbeError(
            f"Gemini batch trait response missing image: {', '.join(missing_sources)}"
        )

    return tuple(analyses)


def _parse_gemini_batch_image_record(
    *,
    image_record: Any,
    expected_source_set: set[str],
) -> GeminiImageTraitAnalysis:
    if not isinstance(image_record, Mapping):
        raise GeminiImageProbeError("Gemini batch trait image record must be an object")

    allowed_keys = {"path", *GEMINI_TRAIT_RESPONSE_KEYS}
    unknown_keys = sorted(set(image_record) - allowed_keys)
    if unknown_keys:
        raise GeminiImageProbeError(
            f"Gemini batch trait image record unknown key: {', '.join(unknown_keys)}"
        )

    source_image = _normalize_source_image_path(image_record.get("path"))
    if source_image not in expected_source_set:
        raise GeminiImageProbeError(
            f"Gemini batch trait response unexpected image: {source_image}"
        )

    notes = image_record.get("notes", "")
    if not isinstance(notes, str):
        raise GeminiImageProbeError("Gemini batch trait response notes must be a string")

    traits_by_aspect: dict[str, tuple[str, ...]] = {}
    for aspect in GEMINI_TRAIT_ASPECTS:
        if aspect not in image_record:
            raise GeminiImageProbeError(
                f"Gemini batch trait response missing aspect: {aspect}"
            )

        aspect_traits = image_record[aspect]
        if isinstance(aspect_traits, str) or not isinstance(aspect_traits, list):
            raise GeminiImageProbeError(
                f"Gemini batch trait response aspect must be a list: {aspect}"
            )
        traits_by_aspect[aspect] = tuple(
            _normalize_gemini_trait(trait=trait, aspect=aspect)
            for trait in aspect_traits
        )

    return GeminiImageTraitAnalysis(
        source_image=source_image,
        traits_by_aspect=traits_by_aspect,
        notes=notes,
    )


def map_gemini_traits_to_candidates(
    *,
    traits_by_aspect: Mapping[str, Sequence[str]],
    source_image: str,
    model: str = DEFAULT_MODEL,
    confidence: float = GEMINI_EXPERIMENTAL_CONFIDENCE,
) -> dict[str, tuple[StyleGeneCandidate, ...]]:
    """Map EXP-001B Gemini traits into schema-valid Phase 0 candidates."""

    if not isinstance(traits_by_aspect, Mapping):
        raise GeminiImageProbeError("Gemini trait response must be a mapping")

    unknown_aspects = sorted(set(traits_by_aspect) - set(GEMINI_TRAIT_ASPECTS))
    if unknown_aspects:
        raise GeminiImageProbeError(f"Gemini trait response unknown aspect: {', '.join(unknown_aspects)}")

    missing_aspects = sorted(set(GEMINI_TRAIT_ASPECTS) - set(traits_by_aspect))
    if missing_aspects:
        raise GeminiImageProbeError(f"Gemini trait response missing aspect: {', '.join(missing_aspects)}")

    normalized_source_image = _normalize_source_image_path(source_image)
    notes = f"gemini experimental extractor; model={model or 'unknown'}"
    candidates_by_aspect: dict[str, tuple[StyleGeneCandidate, ...]] = {}

    for aspect in GEMINI_TRAIT_ASPECTS:
        aspect_traits = traits_by_aspect[aspect]
        if isinstance(aspect_traits, str) or not isinstance(aspect_traits, Sequence):
            raise GeminiImageProbeError(f"Gemini trait response aspect must be a list: {aspect}")

        aspect_candidates: list[StyleGeneCandidate] = []
        seen_candidate_ids: set[str] = set()
        for trait in aspect_traits:
            normalized_trait = _normalize_gemini_trait(trait=trait, aspect=aspect)
            candidate_id = _gemini_candidate_id(
                aspect=aspect,
                trait=normalized_trait,
                source_image=normalized_source_image,
            )
            if candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate_id)
            aspect_candidates.append(
                StyleGeneCandidate(
                    id=candidate_id,
                    prompt=normalized_trait,
                    confidence=confidence,
                    source_images=(normalized_source_image,),
                    notes=notes,
                )
            )

        candidates_by_aspect[aspect] = tuple(aspect_candidates)

    return candidates_by_aspect


def _normalize_gemini_trait(*, trait: Any, aspect: str) -> str:
    if not isinstance(trait, str):
        raise GeminiImageProbeError(f"Gemini trait must be a string: {aspect}")

    normalized_trait = trait.strip()
    if not normalized_trait:
        raise GeminiImageProbeError(f"Gemini trait must be non-empty: {aspect}")

    return normalized_trait


def _normalize_source_image_path(source_image: str) -> str:
    if not isinstance(source_image, str) or not source_image.strip():
        raise GeminiImageProbeError("Gemini source image must be a relative path")

    normalized_source_image = source_image.strip().replace("\\", "/")
    windows_path = PureWindowsPath(normalized_source_image)
    if (
        PurePosixPath(normalized_source_image).is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
    ):
        raise GeminiImageProbeError("Gemini source image must be a relative path")

    return normalized_source_image


def _gemini_candidate_id(*, aspect: str, trait: str, source_image: str) -> str:
    trait_token = _gemini_trait_id_token(trait)
    digest = hashlib.sha256(
        f"{aspect}\0{trait}\0{source_image}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{aspect}_{trait_token}_{digest}"


def _gemini_trait_id_token(trait: str) -> str:
    token_characters = [
        character.lower() if character.isalnum() else "_"
        for character in trait
    ]
    token = "_".join("".join(token_characters).split("_"))
    return token or "gemini_trait"


def guess_image_mime_type(image_path: Path) -> str:
    """Return an image MIME type suitable for Gemini inline image data."""

    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None or not mime_type.startswith("image/"):
        raise GeminiImageProbeError(f"unsupported or unknown image MIME type: {image_path}")
    return mime_type


def read_inline_image_part(image_path: Path) -> dict[str, Any]:
    """Build a Gemini inline_data image part from a local image."""

    if not image_path.is_file():
        raise GeminiImageProbeError(f"image file does not exist: {image_path}")

    image_bytes = image_path.read_bytes()
    if len(image_bytes) > MAX_INLINE_IMAGE_BYTES:
        raise GeminiImageProbeError(
            "image is too large for inline Gemini request; use a file-upload flow instead"
        )

    return {
        "inline_data": {
            "mime_type": guess_image_mime_type(image_path),
            "data": base64.b64encode(image_bytes).decode("ascii"),
        }
    }


def build_generate_content_payload(
    *,
    image_path: Path,
    prompt: str = DEFAULT_ANALYSIS_PROMPT,
) -> dict[str, Any]:
    """Build the Gemini generateContent request payload for one local image."""

    return {
        "contents": [
            {
                "parts": [
                    read_inline_image_part(image_path),
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }


def build_batch_generate_content_payload(
    *,
    image_paths: Sequence[Path],
    source_images: Sequence[str],
    prompt: str = DEFAULT_BATCH_ANALYSIS_PROMPT,
) -> dict[str, Any]:
    """Build a Gemini generateContent request payload for multiple local images."""

    image_paths = tuple(image_paths)
    source_images = tuple(
        _normalize_source_image_path(source_image)
        for source_image in source_images
    )
    if not image_paths:
        raise GeminiImageProbeError("Gemini batch request requires at least one image")
    if len(image_paths) != len(source_images):
        raise GeminiImageProbeError("Gemini batch request image paths and labels differ")

    image_list = "\n".join(
        f"{index}. {source_image}"
        for index, source_image in enumerate(source_images, start=1)
    )
    parts: list[dict[str, Any]] = [
        {"text": f"{prompt}\n\nInput path labels:\n{image_list}"}
    ]
    for source_image, image_path in zip(source_images, image_paths):
        parts.append({"text": f"Image path: {source_image}"})
        parts.append(read_inline_image_part(image_path))

    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }


def call_gemini_generate_content(
    *,
    api_key: str,
    payload: Mapping[str, Any],
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Call Gemini generateContent through REST and return the raw response."""

    url = GEMINI_GENERATE_CONTENT_URL.format(model=model)
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise GeminiImageProbeError(f"Gemini API HTTP {error.code}: {body}") from error
    except URLError as error:
        raise GeminiImageProbeError(f"Gemini API request failed: {error.reason}") from error


def extract_response_text(response: Mapping[str, Any]) -> str:
    """Extract the first text part from a Gemini generateContent response."""

    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GeminiImageProbeError("Gemini response did not include candidates")

    content = candidates[0].get("content")
    if not isinstance(content, Mapping):
        raise GeminiImageProbeError("Gemini response candidate did not include content")

    parts = content.get("parts")
    if not isinstance(parts, list):
        raise GeminiImageProbeError("Gemini response content did not include parts")

    for part in parts:
        if isinstance(part, Mapping) and isinstance(part.get("text"), str):
            return part["text"]

    raise GeminiImageProbeError("Gemini response did not include text")


@dataclass(frozen=True)
class GeminiImageAnalysisClient:
    """EXP-001C injectable wrapper for Gemini image analysis calls."""

    api_key: str
    model: str = DEFAULT_MODEL
    prompt: str = DEFAULT_ANALYSIS_PROMPT
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    payload_builder: Callable[..., Mapping[str, Any]] = build_generate_content_payload
    batch_payload_builder: Callable[..., Mapping[str, Any]] = build_batch_generate_content_payload
    generate_content: Callable[..., Mapping[str, Any]] = call_gemini_generate_content

    def build_payload(self, image_path: Path) -> Mapping[str, Any]:
        return self.payload_builder(image_path=image_path, prompt=self.prompt)

    def build_batch_payload(
        self,
        *,
        image_paths: Sequence[Path],
        source_images: Sequence[str],
    ) -> Mapping[str, Any]:
        return self.batch_payload_builder(
            image_paths=image_paths,
            source_images=source_images,
            prompt=self.prompt,
        )

    def generate_content_response(self, image_path: Path) -> Mapping[str, Any]:
        return self.generate_content(
            api_key=self.api_key,
            payload=self.build_payload(image_path),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )

    def generate_batch_content_response(
        self,
        *,
        image_paths: Sequence[Path],
        source_images: Sequence[str],
    ) -> Mapping[str, Any]:
        return self.generate_content(
            api_key=self.api_key,
            payload=self.build_batch_payload(
                image_paths=image_paths,
                source_images=source_images,
            ),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )

    def analyze_image(self, image_path: Path) -> str:
        return extract_response_text(self.generate_content_response(image_path))

    def analyze_images(
        self,
        *,
        image_paths: Sequence[Path],
        source_images: Sequence[str],
    ) -> str:
        return extract_response_text(
            self.generate_batch_content_response(
                image_paths=image_paths,
                source_images=source_images,
            )
        )


@dataclass(frozen=True)
class GeminiPhase0Extractor:
    """EXP-001D opt-in Phase 0 extractor backed by Gemini image analysis."""

    project_root: Path
    client: Any
    model: str | None = None

    def __call__(
        self,
        reference_image_manifest_records: Sequence[Mapping[str, Any]],
    ) -> dict[str, tuple[StyleGeneCandidate, ...]]:
        candidates_by_aspect: dict[str, list[StyleGeneCandidate]] = {
            aspect: [] for aspect in GEMINI_TRAIT_ASPECTS
        }
        seen_candidate_ids: set[str] = set()

        for record in reference_image_manifest_records:
            source_image = _manifest_record_source_image(record)
            try:
                response_text = self.client.analyze_image(self.project_root / source_image)
            except GeminiImageProbeError as error:
                raise GeminiImageProbeError(
                    f"Gemini image analysis failed for {source_image}: {error}"
                ) from error

            record_candidates_by_aspect = map_gemini_traits_to_candidates(
                traits_by_aspect=parse_gemini_trait_response(response_text),
                source_image=source_image,
                model=self.model or getattr(self.client, "model", DEFAULT_MODEL),
            )
            for aspect in GEMINI_TRAIT_ASPECTS:
                for candidate in record_candidates_by_aspect[aspect]:
                    if candidate.id in seen_candidate_ids:
                        continue
                    seen_candidate_ids.add(candidate.id)
                    candidates_by_aspect[aspect].append(candidate)

        return {
            aspect: tuple(candidates)
            for aspect, candidates in candidates_by_aspect.items()
        }


def _manifest_record_source_image(record: Mapping[str, Any]) -> str:
    if not isinstance(record, Mapping):
        raise GeminiImageProbeError("Gemini extractor manifest record must be an object")

    path = record.get("path")
    return _normalize_source_image_path(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one local image with Gemini and write CR-001 native or "
            "legacy Phase 0 artifacts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  $env:PYTHONPATH = 'src'\n"
            "  $env:GEMINI_API_KEY = '<your key>'\n"
            "  python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png\n"
            "  python -m style_fit_profiler.gemini_image_probe "
            "--backend legacy reference_images/ref-001.png"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=(CR001_IMAGE_BACKEND, LEGACY_IMAGE_BACKEND),
        default=DEFAULT_IMAGE_BACKEND,
        help=(
            "Single-image analysis backend. Defaults to CR-001 native artifacts; "
            "use legacy for EXP Phase 0 trait JSON."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root containing the reference image path.",
    )
    parser.add_argument("image_path", type=Path, help="Path to a local image file.")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_IMAGE_RUN_DIR,
        help="Output run directory for CR-001 native artifacts.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name.")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help=(
            "Legacy backend only. Optional UTF-8 prompt file for EXP Phase 0 "
            "trait JSON. Defaults to the legacy Phase 0 probe prompt."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout for the Gemini generateContent request.",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        help=(
            "Optional path for saving the legacy raw Gemini response or CR-001 "
            "raw validation record."
        ),
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help=(
            "Legacy backend only. Print the raw Gemini generateContent "
            "response JSON."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiImageProbeError("GEMINI_API_KEY is not set")

    if args.backend == CR001_IMAGE_BACKEND:
        if args.prompt_file is not None:
            raise GeminiImageProbeError(
                "--prompt-file is only supported with --backend legacy"
            )
        if args.raw:
            raise GeminiImageProbeError("--raw is only supported with --backend legacy")
        from .cr001 import CR001GeminiAnalysisClient
        from .cr001_gemini_probe import run_cr001_single_probe

        project_root = args.project_root.resolve()
        run_dir = _resolve_run_dir(project_root=project_root, run_dir=args.run_dir)
        source_image = _source_image_from_path(
            project_root=project_root,
            image_path=args.image_path,
        )
        client = CR001GeminiAnalysisClient(
            api_key=api_key,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )
        result = run_cr001_single_probe(
            project_root=project_root,
            source_image=source_image,
            run_dir=run_dir,
            client=client,
            model=args.model,
            raw_output=args.raw_output,
        )
        print(json.dumps(result.to_json_record(), ensure_ascii=False, indent=2))
        return 1 if result.has_failed_images else 0

    prompt = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file is not None
        else DEFAULT_ANALYSIS_PROMPT
    )
    client = GeminiImageAnalysisClient(
        api_key=api_key,
        model=args.model,
        prompt=prompt,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        response = client.generate_content_response(args.image_path)
    except GeminiImageProbeError as error:
        diagnostic = _build_single_provider_error_diagnostic(error)
        if args.raw_output is not None:
            args.raw_output.parent.mkdir(parents=True, exist_ok=True)
            args.raw_output.write_text(
                json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        return 1

    if args.raw_output is not None:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(
            json.dumps(response, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.raw:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(extract_response_text(response))

    return 0


def _build_single_provider_error_diagnostic(error: GeminiImageProbeError) -> dict[str, Any]:
    provider_error = classify_gemini_provider_error(error)
    return {
        "valid": False,
        "error": str(error),
        "provider_error": gemini_provider_error_to_json_record(provider_error),
    }


def _resolve_run_dir(*, project_root: Path, run_dir: Path) -> Path:
    if run_dir.is_absolute():
        return run_dir
    return project_root / run_dir


def _source_image_from_path(*, project_root: Path, image_path: Path) -> str:
    resolved_image_path = image_path
    if not resolved_image_path.is_absolute():
        resolved_image_path = project_root / resolved_image_path
    try:
        return resolved_image_path.resolve().relative_to(project_root).as_posix()
    except ValueError as error:
        raise GeminiImageProbeError(
            "single-image Gemini probe image_path must be under project root"
        ) from error


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GeminiImageProbeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
