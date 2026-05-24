"""Batch Gemini image-analysis probe for local Phase 0 experiments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .gemini_image_probe import (
    DEFAULT_BATCH_ANALYSIS_PROMPT,
    DEFAULT_MODEL,
    GEMINI_TRAIT_ASPECTS,
    GeminiImageAnalysisClient,
    GeminiImageTraitAnalysis,
    GeminiImageProbeError,
    map_gemini_traits_to_candidates,
    parse_gemini_batch_trait_response,
)
from .phase0 import (
    Phase0Batch,
    Phase0BatchResult,
    Phase0BatchStatus,
    StyleGeneCandidate,
    build_phase0_batch_candidates_document,
    build_phase0_batch_run_report,
    build_reference_image_manifest_records,
    discover_reference_images,
    plan_phase0_batches,
    run_phase0_batches,
    validate_style_gene_candidates_document,
    write_reference_image_manifest_document,
)


DEFAULT_BATCH_RUN_DIR = Path("runs/manual-gemini-batch")
DEFAULT_BATCH_SIZE = 2
REFERENCE_IMAGE_ANALYSIS_OUTPUT = Path("phase0/reference_image_analysis.json")
STYLE_GENE_CANDIDATES_OUTPUT = Path("phase0/style_gene_candidates.json")
BATCH_RUN_REPORT_OUTPUT = Path("phase0/batch_run_report.json")


@dataclass(frozen=True)
class GeminiBatchProbeResult:
    """File outputs and status summary from a manual Gemini batch probe."""

    reference_image_manifest_path: str
    reference_image_analysis_path: str
    style_gene_candidates_path: str
    batch_run_report_path: str
    summary: Mapping[str, Any]

    @property
    def has_failed_batches(self) -> bool:
        return int(self.summary.get("failed_batches", 0)) > 0

    def to_json_record(self) -> dict[str, Any]:
        return {
            "reference_image_manifest_path": self.reference_image_manifest_path,
            "reference_image_analysis_path": self.reference_image_analysis_path,
            "style_gene_candidates_path": self.style_gene_candidates_path,
            "batch_run_report_path": self.batch_run_report_path,
            "summary": dict(self.summary),
        }


def run_gemini_batch_probe(
    *,
    project_root: Path,
    input_dir: str,
    run_dir: Path,
    batch_size: int,
    client: Any,
    model: str,
) -> GeminiBatchProbeResult:
    """Run a manual EXP Gemini batch probe and write Phase 0 artifacts."""

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

    batches = plan_phase0_batches(
        reference_image_manifest_records=reference_image_manifest_records,
        batch_size=batch_size,
    )
    image_analyses_by_batch: dict[int, tuple[GeminiImageTraitAnalysis, ...]] = {}
    batch_results = run_phase0_batches(
        batches=batches,
        analyzer=lambda batch: _analyze_gemini_batch(
            batch=batch,
            project_root=project_root,
            client=client,
            model=model,
            image_analyses_by_batch=image_analyses_by_batch,
        ),
    )
    reference_image_analysis_document = _build_reference_image_analysis_document(
        batch_results=batch_results,
        image_analyses_by_batch=image_analyses_by_batch,
        model=model,
    )
    reference_image_analysis_path = _write_run_relative_json(
        run_dir=run_dir,
        relative_path=REFERENCE_IMAGE_ANALYSIS_OUTPUT,
        document=reference_image_analysis_document,
    )
    batch_results_with_outputs = _attach_output_path_to_batch_results(
        batch_results=batch_results,
        output_path=reference_image_analysis_path,
    )

    style_gene_candidates_document = build_phase0_batch_candidates_document(
        batch_results=batch_results,
    )
    validate_style_gene_candidates_document(style_gene_candidates_document)
    style_gene_candidates_path = _write_run_relative_json(
        run_dir=run_dir,
        relative_path=STYLE_GENE_CANDIDATES_OUTPUT,
        document=style_gene_candidates_document,
    )

    batch_run_report = build_phase0_batch_run_report(
        batch_results=batch_results_with_outputs
    )
    batch_run_report_path = _write_run_relative_json(
        run_dir=run_dir,
        relative_path=BATCH_RUN_REPORT_OUTPUT,
        document=batch_run_report,
    )

    return GeminiBatchProbeResult(
        reference_image_manifest_path=reference_image_manifest_path,
        reference_image_analysis_path=reference_image_analysis_path,
        style_gene_candidates_path=style_gene_candidates_path,
        batch_run_report_path=batch_run_report_path,
        summary=batch_run_report["summary"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze reference_images in batches with Gemini and write Phase 0 artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  $env:PYTHONPATH = 'src'\n"
            "  $env:GEMINI_API_KEY = '<your key>'\n"
            "  python -m style_fit_profiler.gemini_batch_probe "
            "--input-dir reference_images --batch-size 2"
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root containing the reference image input directory.",
    )
    parser.add_argument(
        "--input-dir",
        default="reference_images",
        help="Reference image directory relative to project root.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_BATCH_RUN_DIR,
        help="Output run directory. Relative paths are resolved from project root.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of manifest records per batch.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name.")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Optional UTF-8 batch prompt file. Defaults to the Phase 0 batch probe prompt.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for each Gemini generateContent request.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiImageProbeError("GEMINI_API_KEY is not set")

    project_root = args.project_root.resolve()
    run_dir = args.run_dir
    if not run_dir.is_absolute():
        run_dir = project_root / run_dir

    prompt = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file is not None
        else DEFAULT_BATCH_ANALYSIS_PROMPT
    )
    client = GeminiImageAnalysisClient(
        api_key=api_key,
        model=args.model,
        prompt=prompt,
        timeout_seconds=args.timeout_seconds,
    )
    result = run_gemini_batch_probe(
        project_root=project_root,
        input_dir=args.input_dir,
        run_dir=run_dir,
        batch_size=args.batch_size,
        client=client,
        model=args.model,
    )

    print(json.dumps(result.to_json_record(), ensure_ascii=False, indent=2))
    return 1 if result.has_failed_batches else 0


def _write_run_relative_json(
    *,
    run_dir: Path,
    relative_path: Path,
    document: Mapping[str, Any],
) -> str:
    output_path = run_dir / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path.relative_to(run_dir).as_posix()


def _analyze_gemini_batch(
    *,
    batch: Phase0Batch,
    project_root: Path,
    client: Any,
    model: str,
    image_analyses_by_batch: dict[int, tuple[GeminiImageTraitAnalysis, ...]],
) -> dict[str, tuple[StyleGeneCandidate, ...]]:
    source_images = batch.input_paths
    image_paths = tuple(project_root / source_image for source_image in source_images)
    try:
        response_text = client.analyze_images(
            image_paths=image_paths,
            source_images=source_images,
        )
        image_analyses = parse_gemini_batch_trait_response(
            response_text,
            expected_source_images=source_images,
        )
    except GeminiImageProbeError as error:
        source_list = ", ".join(source_images)
        raise GeminiImageProbeError(
            f"Gemini batch image analysis failed for batch {batch.index} "
            f"({source_list}): {error}"
        ) from error

    image_analyses_by_batch[batch.index] = image_analyses
    return _map_gemini_image_analyses_to_candidates(
        image_analyses=image_analyses,
        model=model,
    )


def _map_gemini_image_analyses_to_candidates(
    *,
    image_analyses: tuple[GeminiImageTraitAnalysis, ...],
    model: str,
) -> dict[str, tuple[StyleGeneCandidate, ...]]:
    candidates_by_aspect: dict[str, list[StyleGeneCandidate]] = {
        aspect: [] for aspect in GEMINI_TRAIT_ASPECTS
    }
    seen_candidate_ids: set[str] = set()

    for image_analysis in image_analyses:
        image_candidates_by_aspect = map_gemini_traits_to_candidates(
            traits_by_aspect=image_analysis.traits_by_aspect,
            source_image=image_analysis.source_image,
            model=model,
        )
        for aspect in GEMINI_TRAIT_ASPECTS:
            for candidate in image_candidates_by_aspect[aspect]:
                if candidate.id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(candidate.id)
                candidates_by_aspect[aspect].append(candidate)

    return {
        aspect: tuple(candidates)
        for aspect, candidates in candidates_by_aspect.items()
    }


def _build_reference_image_analysis_document(
    *,
    batch_results: tuple[Phase0BatchResult, ...],
    image_analyses_by_batch: Mapping[int, tuple[GeminiImageTraitAnalysis, ...]],
    model: str,
) -> dict[str, Any]:
    image_records: list[dict[str, Any]] = []

    for batch_result in batch_results:
        if batch_result.status == Phase0BatchStatus.COMPLETED:
            image_analyses = image_analyses_by_batch.get(batch_result.batch_index)
            if image_analyses is None:
                raise GeminiImageProbeError(
                    "Gemini batch image analysis missing completed batch records: "
                    f"{batch_result.batch_index}"
                )
            for image_analysis in image_analyses:
                image_records.append(
                    {
                        "path": image_analysis.source_image,
                        "batch_index": batch_result.batch_index,
                        "analysis_status": Phase0BatchStatus.COMPLETED.value,
                        "model": model,
                        "traits": {
                            aspect: list(image_analysis.traits_by_aspect[aspect])
                            for aspect in GEMINI_TRAIT_ASPECTS
                        },
                        "notes": image_analysis.notes,
                    }
                )
            continue

        for source_image in batch_result.input_paths:
            image_records.append(
                {
                    "path": source_image,
                    "batch_index": batch_result.batch_index,
                    "analysis_status": Phase0BatchStatus.FAILED.value,
                    "model": model,
                    "traits": {aspect: [] for aspect in GEMINI_TRAIT_ASPECTS},
                    "notes": "",
                    "error": batch_result.error,
                }
            )

    return {
        "version": "0.1.0",
        "source": "phase0_batch_reference_image_analysis",
        "images": image_records,
    }


def _attach_output_path_to_batch_results(
    *,
    batch_results: tuple[Phase0BatchResult, ...],
    output_path: str,
) -> tuple[Phase0BatchResult, ...]:
    return tuple(
        Phase0BatchResult(
            batch_index=batch_result.batch_index,
            input_paths=batch_result.input_paths,
            status=batch_result.status,
            candidates_by_aspect=batch_result.candidates_by_aspect,
            error=batch_result.error,
            output_paths=(*batch_result.output_paths, output_path),
        )
        for batch_result in batch_results
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GeminiImageProbeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
