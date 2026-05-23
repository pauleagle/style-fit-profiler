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
import sys
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .phase0 import StyleGeneCandidate


DEFAULT_MODEL = "gemini-2.5-flash"
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


class GeminiImageProbeError(RuntimeError):
    """Raised when the Gemini image probe cannot complete."""


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


def call_gemini_generate_content(
    *,
    api_key: str,
    payload: Mapping[str, Any],
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 60,
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
    timeout_seconds: int = 60
    payload_builder: Callable[..., Mapping[str, Any]] = build_generate_content_payload
    generate_content: Callable[..., Mapping[str, Any]] = call_gemini_generate_content

    def build_payload(self, image_path: Path) -> Mapping[str, Any]:
        return self.payload_builder(image_path=image_path, prompt=self.prompt)

    def generate_content_response(self, image_path: Path) -> Mapping[str, Any]:
        return self.generate_content(
            api_key=self.api_key,
            payload=self.build_payload(image_path),
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )

    def analyze_image(self, image_path: Path) -> str:
        return extract_response_text(self.generate_content_response(image_path))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze one local image with Gemini and print Phase 0 style traits."
    )
    parser.add_argument("image_path", type=Path, help="Path to a local image file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name.")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Optional UTF-8 prompt file. Defaults to the Phase 0 probe prompt.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw Gemini generateContent response JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiImageProbeError("GEMINI_API_KEY is not set")

    prompt = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file is not None
        else DEFAULT_ANALYSIS_PROMPT
    )
    client = GeminiImageAnalysisClient(
        api_key=api_key,
        model=args.model,
        prompt=prompt,
    )
    response = client.generate_content_response(args.image_path)

    if args.raw:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(extract_response_text(response))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GeminiImageProbeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
