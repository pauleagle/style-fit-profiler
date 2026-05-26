"""Manual Gemini probe entrypoints for CR-001 native artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .cr001 import (
    CR001GeminiAnalysisClient,
    CR001GeminiRawExtractor,
    CR001ValidationError,
    build_cr001_native_artifact_document,
    extract_cr001_single_image_record,
    run_cr001_batch_extraction,
    write_cr001_native_artifact_document,
)
from .gemini_image_probe import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    classify_gemini_provider_error,
    gemini_provider_error_to_json_record,
)
from .phase0 import (
    DEFAULT_PHASE0_BATCH_MAX_ATTEMPTS,
    build_reference_image_manifest_records,
    discover_reference_images,
    write_reference_image_manifest_document,
)


DEFAULT_SINGLE_RUN_DIR = Path("runs/manual-cr001-single")
DEFAULT_BATCH_RUN_DIR = Path("runs/manual-cr001-batch")
DEFAULT_BATCH_SIZE = 2
DEFAULT_BATCH_MAX_ATTEMPTS = DEFAULT_PHASE0_BATCH_MAX_ATTEMPTS


class CR001GeminiProbeError(RuntimeError):
    """Raised when a manual CR-001 Gemini probe cannot complete."""


@dataclass(frozen=True)
class CR001SingleProbeResult:
    """File outputs and validation status from a single-image CR-001 probe."""

    reference_image_manifest_path: str
    native_artifact_path: str
    source_image: str
    valid: bool
    model: str | None = None
    raw_response_path: str | None = None
    error: str | None = None
    provider_error: Mapping[str, Any] | None = None

    @property
    def has_failed_images(self) -> bool:
        return not self.valid

    def to_json_record(self) -> dict[str, Any]:
        return {
            "reference_image_manifest_path": self.reference_image_manifest_path,
            "native_artifact_path": self.native_artifact_path,
            "source_image": self.source_image,
            "valid": self.valid,
            "model": self.model,
            "raw_response_path": self.raw_response_path,
            "error": self.error,
            "provider_error": (
                dict(self.provider_error)
                if self.provider_error is not None
                else None
            ),
        }


@dataclass(frozen=True)
class CR001BatchProbeResult:
    """File outputs and status summary from a batch CR-001 probe."""

    reference_image_manifest_path: str
    native_artifact_path: str
    batch_run_report_path: str
    summary: Mapping[str, Any]

    @property
    def has_failed_batches(self) -> bool:
        return int(self.summary.get("failed_batches", 0)) > 0

    def to_json_record(self) -> dict[str, Any]:
        return {
            "reference_image_manifest_path": self.reference_image_manifest_path,
            "native_artifact_path": self.native_artifact_path,
            "batch_run_report_path": self.batch_run_report_path,
            "summary": dict(self.summary),
        }


def run_cr001_single_probe(
    *,
    project_root: Path,
    source_image: str,
    run_dir: Path,
    client: Any,
    model: str,
    raw_output: Path | None = None,
) -> CR001SingleProbeResult:
    """Run one CR-001 reference image through Gemini and write native output."""

    reference_image_manifest_records = build_reference_image_manifest_records(
        project_root=project_root,
        reference_image_paths=(source_image,),
    )
    reference_image_manifest_path = write_reference_image_manifest_document(
        run_dir=run_dir,
        reference_image_manifest_records=reference_image_manifest_records,
    )
    extractor = CR001GeminiRawExtractor(
        project_root=project_root,
        client=client,
        model=model,
    )
    try:
        extraction_result = extract_cr001_single_image_record(
            reference_image_manifest_record=reference_image_manifest_records[0],
            raw_extractor=extractor,
        )
    except Exception as error:
        provider_error = gemini_provider_error_to_json_record(
            classify_gemini_provider_error(error)
        )
        raw_response_path = None
        if raw_output is not None:
            raw_response_path = _write_raw_response_record(
                run_dir=run_dir,
                raw_output=raw_output,
                document={
                    "source_image": source_image,
                    "model": model,
                    "response_text": None,
                    "valid": False,
                    "error": str(error),
                    "provider_error": provider_error,
                },
            )
        native_artifact_path = write_cr001_native_artifact_document(
            run_dir=run_dir,
            artifact_document=build_cr001_native_artifact_document([]),
        )
        return CR001SingleProbeResult(
            reference_image_manifest_path=reference_image_manifest_path,
            native_artifact_path=native_artifact_path,
            source_image=source_image,
            valid=False,
            model=model,
            raw_response_path=raw_response_path,
            error=str(error),
            provider_error=provider_error,
        )

    raw_response_path = None
    if raw_output is not None and extraction_result.raw_response_text is not None:
        raw_response_path = _write_raw_response_record(
            run_dir=run_dir,
            raw_output=raw_output,
            document={
                "source_image": extraction_result.source_image,
                "model": extraction_result.model,
                "response_text": extraction_result.raw_response_text,
                "valid": extraction_result.valid,
                "error": extraction_result.error,
            },
        )

    artifact_document = build_cr001_native_artifact_document(
        [extraction_result.record] if extraction_result.valid else []
    )
    native_artifact_path = write_cr001_native_artifact_document(
        run_dir=run_dir,
        artifact_document=artifact_document,
    )
    return CR001SingleProbeResult(
        reference_image_manifest_path=reference_image_manifest_path,
        native_artifact_path=native_artifact_path,
        source_image=extraction_result.source_image,
        valid=extraction_result.valid,
        model=extraction_result.model,
        raw_response_path=raw_response_path,
        error=extraction_result.error,
    )


def run_cr001_batch_probe(
    *,
    project_root: Path,
    input_dir: str,
    run_dir: Path,
    batch_size: int,
    max_attempts: int,
    client: Any,
    model: str,
) -> CR001BatchProbeResult:
    """Run CR-001 extraction for a reference image directory."""

    reference_image_paths = discover_reference_images(
        project_root=project_root,
        input_dir=input_dir,
    )
    reference_image_manifest_records = build_reference_image_manifest_records(
        project_root=project_root,
        reference_image_paths=reference_image_paths,
    )
    reference_image_manifest_path = write_reference_image_manifest_document(
        run_dir=run_dir,
        reference_image_manifest_records=reference_image_manifest_records,
    )
    extractor = CR001GeminiRawExtractor(
        project_root=project_root,
        client=client,
        model=model,
    )
    extraction_result = run_cr001_batch_extraction(
        reference_image_manifest_records=reference_image_manifest_records,
        run_dir=run_dir,
        raw_extractor=extractor,
        batch_size=batch_size,
        max_attempts=max_attempts,
    )
    return CR001BatchProbeResult(
        reference_image_manifest_path=reference_image_manifest_path,
        native_artifact_path=extraction_result.native_artifact_path,
        batch_run_report_path=extraction_result.batch_run_report_path,
        summary=extraction_result.summary,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run manual CR-001 Gemini probes and write native artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  $env:PYTHONPATH = 'src'\n"
            "  $env:GEMINI_API_KEY = '<your key>'\n"
            "  python -m style_fit_profiler.cr001_gemini_probe single reference_images/ref-001.png\n"
            "  python -m style_fit_profiler.cr001_gemini_probe batch --input-dir reference_images"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_common_options(
        subparsers.add_parser(
            "single",
            help="Analyze one reference image and write CR-001 native output.",
        )
    )
    single_parser = subparsers.choices["single"]
    single_parser.add_argument(
        "image_path",
        type=Path,
        help="Reference image path. Relative paths are resolved from project root.",
    )
    single_parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_SINGLE_RUN_DIR,
        help="Output run directory. Relative paths are resolved from project root.",
    )
    single_parser.add_argument(
        "--raw-output",
        type=Path,
        help="Optional path for saving CR-001 raw response text and validation status.",
    )

    batch_parser = subparsers.add_parser(
        "batch",
        help="Analyze a reference image directory and write CR-001 native output.",
    )
    _add_common_options(batch_parser)
    batch_parser.add_argument(
        "--input-dir",
        default="reference_images",
        help="Reference image directory relative to project root.",
    )
    batch_parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_BATCH_RUN_DIR,
        help="Output run directory. Relative paths are resolved from project root.",
    )
    batch_parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of manifest records per CR-001 batch.",
    )
    batch_parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_BATCH_MAX_ATTEMPTS,
        help="Maximum attempts per CR-001 batch before it is reported as failed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise CR001GeminiProbeError("GEMINI_API_KEY is not set")

    project_root = args.project_root.resolve()
    run_dir = _resolve_run_dir(project_root=project_root, run_dir=args.run_dir)
    client = CR001GeminiAnalysisClient(
        api_key=api_key,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
    )

    if args.command == "single":
        source_image = _source_image_from_path(
            project_root=project_root,
            image_path=args.image_path,
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

    if args.command == "batch":
        result = run_cr001_batch_probe(
            project_root=project_root,
            input_dir=args.input_dir,
            run_dir=run_dir,
            batch_size=args.batch_size,
            max_attempts=args.max_attempts,
            client=client,
            model=args.model,
        )
        print(json.dumps(result.to_json_record(), ensure_ascii=False, indent=2))
        return 1 if result.has_failed_batches else 0

    raise CR001GeminiProbeError(f"unsupported CR-001 probe command: {args.command}")


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root containing reference image paths.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout for each Gemini generateContent request.",
    )


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
        raise CR001GeminiProbeError(
            "single-image CR-001 probe image_path must be under project root"
        ) from error


def _write_raw_response_record(
    *,
    run_dir: Path,
    raw_output: Path,
    document: Mapping[str, Any],
) -> str:
    output_path = raw_output
    if not output_path.is_absolute():
        output_path = run_dir / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path.relative_to(run_dir).as_posix()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CR001GeminiProbeError, CR001ValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
