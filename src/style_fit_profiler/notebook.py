"""Notebook helper builders for experimental Phase 0 Colab flows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Literal
import zipfile

from .config import ReferenceImageAnalysisPolicy
from .phase0 import (
    CandidateGenesByAspect,
    Phase0Batch,
    Phase0BatchAnalyzer,
    Phase0Result,
    Phase0Status,
    SUPPORTED_REFERENCE_IMAGE_EXTENSIONS,
    build_phase0_batch_candidates_document,
    build_phase0_batch_run_report,
    build_reference_image_manifest_records,
    deterministic_mock_phase0_extractor,
    discover_reference_images,
    plan_phase0_batches,
    run_phase0,
    run_phase0_batches,
    validate_style_gene_candidates_document,
    write_reference_image_manifest_document,
)


DEFAULT_COLAB_PROJECT_ROOT = "/content/style-fit-profiler"
DEFAULT_COLAB_RUN_ID = "colab-phase0"
DEFAULT_COLAB_NOTEBOOK_NAME = "style-fit-profiler-phase0.ipynb"
DEFAULT_COLAB_EXPORT_ZIP_NAME = "phase0-artifacts.zip"


@dataclass(frozen=True)
class NotebookCell:
    """Small dependency-free representation of a generated notebook cell."""

    name: str
    source: str
    cell_type: Literal["code", "markdown"] = "code"

    def to_ipynb_cell(self) -> dict[str, Any]:
        if self.cell_type == "code":
            return {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"id": self.name},
                "outputs": [],
                "source": self.source,
            }

        return {
            "cell_type": "markdown",
            "metadata": {"id": self.name},
            "source": self.source,
        }


@dataclass(frozen=True)
class NotebookReferenceImageStagingResult:
    """Result returned after notebook upload bytes are staged as Phase 0 inputs."""

    input_dir: str
    reference_image_paths: tuple[str, ...]
    reference_image_manifest_records: tuple[dict[str, Any], ...]
    reference_image_manifest_path: str | None = None

    def to_json_record(self) -> dict[str, Any]:
        return {
            "input_dir": self.input_dir,
            "reference_image_paths": list(self.reference_image_paths),
            "reference_image_manifest_records": list(
                self.reference_image_manifest_records
            ),
            "reference_image_manifest_path": self.reference_image_manifest_path,
        }


@dataclass(frozen=True)
class NotebookPhase0AnalysisResult:
    """Notebook-friendly summary for a Phase 0 analysis run."""

    status: str
    reason: str
    reference_image_paths: tuple[str, ...] = ()
    reference_image_manifest_path: str | None = None
    style_gene_candidates_path: str | None = None
    batch_report_path: str | None = None
    batch_summary: Mapping[str, Any] | None = None

    @classmethod
    def from_phase0_result(
        cls,
        phase0_result: Phase0Result,
    ) -> "NotebookPhase0AnalysisResult":
        return cls(
            status=phase0_result.status.value,
            reason=phase0_result.reason,
            reference_image_paths=phase0_result.reference_image_paths,
            reference_image_manifest_path=phase0_result.reference_image_manifest_path,
            style_gene_candidates_path=phase0_result.style_gene_candidates_path,
        )

    def to_json_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "reference_image_paths": list(self.reference_image_paths),
            "reference_image_manifest_path": self.reference_image_manifest_path,
            "style_gene_candidates_path": self.style_gene_candidates_path,
            "batch_report_path": self.batch_report_path,
            "batch_summary": dict(self.batch_summary or {}),
        }


def load_notebook_reference_image_analysis_policy(
    config: Mapping[str, Any] | str | Path | None,
) -> ReferenceImageAnalysisPolicy:
    """Load the Phase 0 policy from a full config object or notebook path."""

    if config is None:
        return ReferenceImageAnalysisPolicy()

    if isinstance(config, (str, Path)):
        config_path = Path(config)
        config = json.loads(config_path.read_text(encoding="utf-8"))

    if not isinstance(config, Mapping):
        raise TypeError("notebook config must be a mapping or JSON file path")

    if "reference_image_analysis_policy" in config:
        policy_config = config["reference_image_analysis_policy"]
    elif any(field in config for field in ("enabled", "input_dir", "output_file", "aspects")):
        policy_config = config
    else:
        policy_config = None

    return ReferenceImageAnalysisPolicy.from_mapping(policy_config)


def stage_notebook_reference_images(
    *,
    project_root: Path,
    uploaded_files: Mapping[str, bytes | bytearray | memoryview],
    input_dir: str = "reference_images",
    run_dir: Path | None = None,
    overwrite: bool = False,
) -> NotebookReferenceImageStagingResult:
    """Stage Colab upload bytes and optionally write a Phase 0 manifest."""

    if isinstance(uploaded_files, (bytes, bytearray, memoryview)) or not isinstance(
        uploaded_files,
        Mapping,
    ):
        raise TypeError("uploaded_files must be a mapping of file names to bytes")

    reference_dir = project_root / input_dir
    staged_files = _plan_notebook_uploaded_files(
        uploaded_files=uploaded_files,
        reference_dir=reference_dir,
        overwrite=overwrite,
    )

    reference_dir.mkdir(parents=True, exist_ok=True)
    for target_path, uploaded_bytes in staged_files:
        target_path.write_bytes(bytes(uploaded_bytes))

    reference_image_paths = discover_reference_images(
        project_root=project_root,
        input_dir=input_dir,
    )
    reference_image_manifest_records = build_reference_image_manifest_records(
        project_root=project_root,
        reference_image_paths=reference_image_paths,
    )
    reference_image_manifest_path = None
    if run_dir is not None:
        reference_image_manifest_path = write_reference_image_manifest_document(
            run_dir=run_dir,
            reference_image_manifest_records=reference_image_manifest_records,
        )

    return NotebookReferenceImageStagingResult(
        input_dir=input_dir,
        reference_image_paths=reference_image_paths,
        reference_image_manifest_records=reference_image_manifest_records,
        reference_image_manifest_path=reference_image_manifest_path,
    )


def run_notebook_phase0_analysis(
    *,
    policy: ReferenceImageAnalysisPolicy,
    project_root: Path,
    run_dir: Path,
    extractor: Any | None = None,
    use_batch: bool = False,
    batch_size: int = 2,
    batch_analyzer: Phase0BatchAnalyzer | None = None,
) -> NotebookPhase0AnalysisResult:
    """Run Phase 0 from a notebook, optionally through the EXP-002 batch flow."""

    if not use_batch:
        return NotebookPhase0AnalysisResult.from_phase0_result(
            run_phase0(
                policy=policy,
                project_root=project_root,
                run_dir=run_dir,
                extractor=extractor,
            )
        )

    if not policy.enabled:
        return NotebookPhase0AnalysisResult(
            status=Phase0Status.SKIPPED.value,
            reason="reference image analysis disabled",
        )

    reference_image_paths = discover_reference_images(
        project_root=project_root,
        input_dir=policy.input_dir,
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
    analyzer = batch_analyzer or _notebook_mock_batch_analyzer
    batch_results = run_phase0_batches(
        batches=batches,
        analyzer=analyzer,
    )
    candidates_document = build_phase0_batch_candidates_document(
        batch_results=batch_results,
    )
    style_gene_candidates_path = _write_run_relative_json(
        run_dir=run_dir,
        relative_path=Path("phase0") / policy.output_file,
        document=candidates_document,
    )
    batch_report = build_phase0_batch_run_report(batch_results=batch_results)
    batch_report_path = _write_run_relative_json(
        run_dir=run_dir,
        relative_path=Path("phase0") / "batch_run_report.json",
        document=batch_report,
    )

    return NotebookPhase0AnalysisResult(
        status="phase0_batch_output_written",
        reason="phase0 batch output written",
        reference_image_paths=reference_image_paths,
        reference_image_manifest_path=reference_image_manifest_path,
        style_gene_candidates_path=style_gene_candidates_path,
        batch_report_path=batch_report_path,
        batch_summary=batch_report["summary"],
    )


def build_notebook_candidate_preview_rows(
    style_gene_candidates_document: Mapping[str, Any],
    *,
    max_rows_per_aspect: int = 5,
) -> tuple[dict[str, Any], ...]:
    """Build display rows for notebook previews without changing outputs."""

    if type(max_rows_per_aspect) is not int or max_rows_per_aspect < 1:
        raise ValueError("max_rows_per_aspect must be a positive integer")

    validate_style_gene_candidates_document(style_gene_candidates_document)
    aspects = style_gene_candidates_document["aspects"]
    rows: list[dict[str, Any]] = []
    for aspect, candidates in aspects.items():
        for candidate in candidates[:max_rows_per_aspect]:
            rows.append(
                {
                    "aspect": aspect,
                    "id": candidate["id"],
                    "prompt": candidate["prompt"],
                    "confidence": candidate["confidence"],
                    "source_images": list(candidate["source_images"]),
                }
            )

    return tuple(rows)


def load_notebook_candidate_preview_rows(
    style_gene_candidates_path: Path,
    *,
    max_rows_per_aspect: int = 5,
) -> tuple[dict[str, Any], ...]:
    """Load a Phase 0 candidate document and build notebook preview rows."""

    document = json.loads(style_gene_candidates_path.read_text(encoding="utf-8"))
    return build_notebook_candidate_preview_rows(
        document,
        max_rows_per_aspect=max_rows_per_aspect,
    )


def build_notebook_phase0_export_manifest(*, run_dir: Path) -> dict[str, Any]:
    """List notebook Phase 0 artifacts that are ready for local export."""

    phase0_dir = run_dir / "phase0"
    artifact_paths = tuple(
        sorted(
            (
                path.relative_to(run_dir).as_posix()
                for path in phase0_dir.rglob("*")
                if path.is_file()
            ),
            key=str.casefold,
        )
    ) if phase0_dir.is_dir() else ()

    return {
        "version": "0.1.0",
        "source": "phase0_notebook_export",
        "run_dir": run_dir.as_posix(),
        "artifact_paths": list(artifact_paths),
    }


def write_notebook_phase0_export_zip(
    *,
    run_dir: Path,
    output_zip_path: Path | None = None,
) -> Path:
    """Create a zip containing notebook Phase 0 artifacts."""

    export_manifest = build_notebook_phase0_export_manifest(run_dir=run_dir)
    artifact_paths = export_manifest["artifact_paths"]
    if not artifact_paths:
        raise FileNotFoundError("no Phase 0 notebook artifacts found to export")

    zip_path = output_zip_path or (run_dir / DEFAULT_COLAB_EXPORT_ZIP_NAME)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for artifact_path in artifact_paths:
            archive.write(run_dir / artifact_path, arcname=artifact_path)
        archive.writestr(
            "phase0_export_manifest.json",
            json.dumps(export_manifest, ensure_ascii=False, indent=2) + "\n",
        )

    return zip_path


def build_colab_runtime_bootstrap_cells(
    *,
    project_root: str = DEFAULT_COLAB_PROJECT_ROOT,
    run_id: str = DEFAULT_COLAB_RUN_ID,
) -> tuple[NotebookCell, ...]:
    """Build EXP-003A Colab runtime setup and dependency initialization cells."""

    project_root_literal = json.dumps(project_root)
    run_id_literal = json.dumps(run_id)
    runtime_setup_source = f"""from pathlib import Path
import os
import sys

PROJECT_ROOT = Path({project_root_literal})
SRC_DIR = PROJECT_ROOT / "src"
REFERENCE_IMAGE_DIR = PROJECT_ROOT / "reference_images"
RUN_DIR = PROJECT_ROOT / "runs" / {run_id_literal}

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REFERENCE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)

print(f"Project root: {{PROJECT_ROOT}}")
print(f"Reference image dir: {{REFERENCE_IMAGE_DIR}}")
print(f"Run dir: {{RUN_DIR}}")
"""
    dependency_check_source = """import importlib.util

required_modules = ("style_fit_profiler",)
missing_modules = [
    module_name
    for module_name in required_modules
    if importlib.util.find_spec(module_name) is None
]

if missing_modules:
    raise RuntimeError(
        "Missing notebook dependencies: " + ", ".join(missing_modules)
    )

print("Notebook runtime dependencies are ready.")
"""

    return (
        NotebookCell(name="runtime-setup", source=runtime_setup_source),
        NotebookCell(name="dependency-check", source=dependency_check_source),
    )


def build_colab_upload_and_staging_cells(
    *,
    input_dir: str = "reference_images",
) -> tuple[NotebookCell, ...]:
    """Build EXP-003B upload and staging cells for Colab."""

    input_dir_literal = json.dumps(input_dir)
    upload_source = f"""from google.colab import files
from style_fit_profiler.notebook import stage_notebook_reference_images

uploaded_files = files.upload()
staging_result = stage_notebook_reference_images(
    project_root=PROJECT_ROOT,
    uploaded_files=uploaded_files,
    input_dir={input_dir_literal},
    run_dir=RUN_DIR,
    overwrite=True,
)
staging_result.to_json_record()
"""

    return (
        NotebookCell(name="reference-upload", source=upload_source),
    )


def build_colab_analysis_cells(
    *,
    use_batch: bool = True,
    batch_size: int = 2,
) -> tuple[NotebookCell, ...]:
    """Build EXP-003C notebook analysis runner cells."""

    use_batch_literal = "True" if use_batch else "False"
    analysis_source = f"""from style_fit_profiler import ReferenceImageAnalysisPolicy
from style_fit_profiler.notebook import (
    load_notebook_reference_image_analysis_policy,
    run_notebook_phase0_analysis,
)

CONFIG_PATH = PROJECT_ROOT / "style_profiler_config.json"
if CONFIG_PATH.exists():
    phase0_policy = load_notebook_reference_image_analysis_policy(CONFIG_PATH)
else:
    phase0_policy = ReferenceImageAnalysisPolicy(enabled=True)

analysis_result = run_notebook_phase0_analysis(
    policy=phase0_policy,
    project_root=PROJECT_ROOT,
    run_dir=RUN_DIR,
    use_batch={use_batch_literal},
    batch_size={batch_size},
)
analysis_result.to_json_record()
"""

    return (
        NotebookCell(name="phase0-analysis", source=analysis_source),
    )


def build_colab_preview_and_export_cells() -> tuple[NotebookCell, ...]:
    """Build EXP-003D preview and export cells for Colab."""

    preview_source = """from style_fit_profiler.notebook import load_notebook_candidate_preview_rows

candidate_path = RUN_DIR / analysis_result.style_gene_candidates_path
preview_rows = load_notebook_candidate_preview_rows(candidate_path)
preview_rows
"""
    export_source = """from google.colab import files
from style_fit_profiler.notebook import write_notebook_phase0_export_zip

export_zip_path = write_notebook_phase0_export_zip(run_dir=RUN_DIR)
files.download(str(export_zip_path))
"""

    return (
        NotebookCell(name="candidate-preview", source=preview_source),
        NotebookCell(name="output-export", source=export_source),
    )


def build_colab_runtime_bootstrap_notebook(
    *,
    project_root: str = DEFAULT_COLAB_PROJECT_ROOT,
    run_id: str = DEFAULT_COLAB_RUN_ID,
    notebook_name: str = DEFAULT_COLAB_NOTEBOOK_NAME,
) -> dict[str, Any]:
    """Build a minimal EXP-003A ipynb document for the runtime bootstrap cells."""

    return {
        "cells": [
            cell.to_ipynb_cell()
            for cell in build_colab_runtime_bootstrap_cells(
                project_root=project_root,
                run_id=run_id,
            )
        ],
        "metadata": {
            "colab": {"name": notebook_name},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_colab_phase0_notebook(
    *,
    project_root: str = DEFAULT_COLAB_PROJECT_ROOT,
    run_id: str = DEFAULT_COLAB_RUN_ID,
    notebook_name: str = DEFAULT_COLAB_NOTEBOOK_NAME,
    input_dir: str = "reference_images",
    use_batch: bool = True,
    batch_size: int = 2,
) -> dict[str, Any]:
    """Build an EXP-003E smoke-testable Colab Phase 0 notebook document."""

    cells = (
        *build_colab_runtime_bootstrap_cells(
            project_root=project_root,
            run_id=run_id,
        ),
        *build_colab_upload_and_staging_cells(input_dir=input_dir),
        *build_colab_analysis_cells(use_batch=use_batch, batch_size=batch_size),
        *build_colab_preview_and_export_cells(),
    )

    return {
        "cells": [cell.to_ipynb_cell() for cell in cells],
        "metadata": {
            "colab": {"name": notebook_name},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _plan_notebook_uploaded_files(
    *,
    uploaded_files: Mapping[str, bytes | bytearray | memoryview],
    reference_dir: Path,
    overwrite: bool,
) -> tuple[tuple[Path, bytes | bytearray | memoryview], ...]:
    staged_files: list[tuple[Path, bytes | bytearray | memoryview]] = []
    seen_target_names: set[str] = set()
    for uploaded_name, uploaded_bytes in uploaded_files.items():
        staged_name = _notebook_upload_basename(uploaded_name)
        if staged_name.casefold() in seen_target_names:
            raise FileExistsError(f"duplicate staged upload file name: {staged_name}")
        seen_target_names.add(staged_name.casefold())

        if Path(staged_name).suffix.lower() not in SUPPORTED_REFERENCE_IMAGE_EXTENSIONS:
            raise ValueError(f"unsupported reference image upload extension: {staged_name}")
        if not isinstance(uploaded_bytes, (bytes, bytearray, memoryview)):
            raise TypeError(f"uploaded file bytes are invalid: {uploaded_name}")

        target_path = reference_dir / staged_name
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"staged reference image already exists: {staged_name}")
        staged_files.append((target_path, uploaded_bytes))

    return tuple(staged_files)


def _notebook_upload_basename(uploaded_name: str) -> str:
    if not isinstance(uploaded_name, str):
        raise TypeError("uploaded file name must be a string")

    staged_name = PurePosixPath(uploaded_name.replace("\\", "/")).name
    if not staged_name or staged_name in {".", ".."}:
        raise ValueError("uploaded file name must include a file name")
    return staged_name


def _notebook_mock_batch_analyzer(batch: Phase0Batch) -> CandidateGenesByAspect:
    return deterministic_mock_phase0_extractor(batch.records)


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
