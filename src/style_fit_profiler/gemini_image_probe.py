"""Small Gemini image-analysis probe for local Phase 0 experiments."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
MAX_INLINE_IMAGE_BYTES = 19 * 1024 * 1024

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
    payload = build_generate_content_payload(image_path=args.image_path, prompt=prompt)
    response = call_gemini_generate_content(
        api_key=api_key,
        payload=payload,
        model=args.model,
    )

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
