import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import style_fit_profiler  # noqa: E402
from style_fit_profiler import Phase0Error, ReferenceImageAnalysisPolicy  # noqa: E402
from style_fit_profiler.notebook import (  # noqa: E402
    NotebookCell,
    build_colab_analysis_cells,
    build_colab_phase0_notebook,
    build_colab_preview_and_export_cells,
    build_colab_runtime_bootstrap_cells,
    build_colab_runtime_bootstrap_notebook,
    build_colab_upload_and_staging_cells,
    build_notebook_candidate_preview_rows,
    build_notebook_phase0_export_manifest,
    load_notebook_candidate_preview_rows,
    load_notebook_reference_image_analysis_policy,
    run_notebook_phase0_analysis,
    stage_notebook_reference_images,
    write_notebook_phase0_export_zip,
)


class ColabRuntimeBootstrapTests(unittest.TestCase):
    def test_exp_003a_builds_runtime_setup_and_dependency_cells(self):
        cells = build_colab_runtime_bootstrap_cells(
            project_root="/content/style-fit-profiler",
            run_id="colab-smoke",
        )

        self.assertEqual(
            [cell.name for cell in cells],
            [
                "runtime-setup",
                "dependency-check",
            ],
        )
        self.assertTrue(all(cell.cell_type == "code" for cell in cells))
        self.assertIn("/content/style-fit-profiler", cells[0].source)
        self.assertIn("sys.path.insert", cells[0].source)
        self.assertIn("reference_images", cells[0].source)
        self.assertIn("runs", cells[0].source)
        self.assertIn("style_fit_profiler", cells[1].source)

    def test_exp_003a_notebook_document_is_ipynb_serializable(self):
        notebook = build_colab_runtime_bootstrap_notebook(
            project_root="/content/style-fit-profiler"
        )

        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["metadata"]["colab"]["name"], "style-fit-profiler-phase0.ipynb")
        self.assertEqual(len(notebook["cells"]), 2)
        json.dumps(notebook)

    def test_exp_003a_bootstrap_cells_do_not_embed_secret_values(self):
        notebook_text = json.dumps(
            build_colab_runtime_bootstrap_notebook(),
            ensure_ascii=False,
        )

        self.assertNotIn("GEMINI_API_KEY =", notebook_text)
        self.assertNotIn("<your key>", notebook_text)

    def test_exp_003a_notebook_cell_serializes_to_colab_code_cell(self):
        cell = NotebookCell(
            name="runtime-setup",
            source="print('ready')",
        )

        self.assertEqual(
            cell.to_ipynb_cell(),
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"id": "runtime-setup"},
                "outputs": [],
                "source": "print('ready')",
            },
        )


class NotebookUploadAndStagingTests(unittest.TestCase):
    def test_exp_003b_stages_uploaded_reference_images_and_writes_manifest(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "colab-phase0"
            result = stage_notebook_reference_images(
                project_root=project_root,
                uploaded_files={
                    "nested/ref-b.JPG": _jpeg_header_bytes(width=4, height=5),
                    "ref-a.png": _png_header_bytes(width=2, height=3),
                },
                run_dir=run_dir,
            )

            manifest_path = run_dir / "phase0" / "reference_image_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(
            result.reference_image_paths,
            ("reference_images/ref-a.png", "reference_images/ref-b.JPG"),
        )
        self.assertEqual(
            result.reference_image_manifest_path,
            "phase0/reference_image_manifest.json",
        )
        self.assertEqual(
            [record["path"] for record in result.reference_image_manifest_records],
            ["reference_images/ref-a.png", "reference_images/ref-b.JPG"],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/ref-a.png", "reference_images/ref-b.JPG"],
        )

    def test_exp_003b_rejects_unsupported_uploads_and_name_collisions(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            with self.assertRaisesRegex(ValueError, "unsupported"):
                stage_notebook_reference_images(
                    project_root=project_root,
                    uploaded_files={"notes.txt": b"not an image"},
                )

            with self.assertRaisesRegex(FileExistsError, "duplicate"):
                stage_notebook_reference_images(
                    project_root=project_root,
                    uploaded_files={
                        "a/ref.png": _png_header_bytes(width=1, height=1),
                        "b/ref.png": _png_header_bytes(width=1, height=1),
                    },
                )

    def test_exp_003b_builds_upload_cell_without_embedding_secrets(self):
        cells = build_colab_upload_and_staging_cells(input_dir="reference_images")

        self.assertEqual([cell.name for cell in cells], ["reference-upload"])
        self.assertIn("files.upload", cells[0].source)
        self.assertIn("stage_notebook_reference_images", cells[0].source)
        self.assertNotIn("GEMINI_API_KEY", cells[0].source)


class NotebookAnalysisRunnerTests(unittest.TestCase):
    def test_exp_003c_loads_policy_from_full_config_or_json_file(self):
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "style_profiler_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "reference_image_analysis_policy": {
                            "enabled": True,
                            "input_dir": "refs",
                            "output_file": "candidates.json",
                        }
                    }
                ),
                encoding="utf-8",
            )

            policy = load_notebook_reference_image_analysis_policy(config_path)

        self.assertEqual(policy, ReferenceImageAnalysisPolicy(
            enabled=True,
            input_dir="refs",
            output_file="candidates.json",
        ))
        self.assertFalse(load_notebook_reference_image_analysis_policy({}).enabled)
        self.assertTrue(
            load_notebook_reference_image_analysis_policy({"enabled": True}).enabled
        )

    def test_exp_003c_runs_single_phase0_flow_from_notebook(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "colab-phase0"
            reference_dir = project_root / "reference_images"
            reference_dir.mkdir()
            (reference_dir / "ref-a.png").write_bytes(_png_header_bytes(width=2, height=3))

            result = run_notebook_phase0_analysis(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
            )

            candidate_path = run_dir / result.style_gene_candidates_path
            candidate_path_exists = candidate_path.is_file()

        self.assertEqual(result.status, "phase0_output_written")
        self.assertEqual(
            result.reference_image_manifest_path,
            "phase0/reference_image_manifest.json",
        )
        self.assertEqual(
            result.style_gene_candidates_path,
            "phase0/style_gene_candidates.json",
        )
        self.assertTrue(candidate_path_exists)

    def test_exp_003c_runs_batch_phase0_flow_with_mock_analyzer(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "colab-phase0"
            reference_dir = project_root / "reference_images"
            reference_dir.mkdir()
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=2, height=3))
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            result = run_notebook_phase0_analysis(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
                use_batch=True,
                batch_size=1,
            )
            candidate_document = json.loads(
                (run_dir / result.style_gene_candidates_path).read_text(
                    encoding="utf-8"
                )
            )
            batch_report = json.loads(
                (run_dir / result.batch_report_path).read_text(encoding="utf-8")
            )

        self.assertEqual(result.status, "phase0_batch_output_written")
        self.assertEqual(candidate_document["source"], "phase0_batch_reference_image_analysis")
        self.assertEqual(result.batch_summary["total_batches"], 2)
        self.assertEqual(batch_report["summary"]["completed_batches"], 2)

    def test_exp_003c_builds_analysis_cell_for_config_loading_and_batch_runner(self):
        cells = build_colab_analysis_cells(use_batch=True, batch_size=3)

        self.assertEqual([cell.name for cell in cells], ["phase0-analysis"])
        self.assertIn("load_notebook_reference_image_analysis_policy", cells[0].source)
        self.assertIn("run_notebook_phase0_analysis", cells[0].source)
        self.assertIn("batch_size=3", cells[0].source)


class NotebookPreviewAndExportTests(unittest.TestCase):
    def test_exp_003d_builds_candidate_preview_rows_without_mutating_document(self):
        document = {
            "version": "0.1.0",
            "source": "phase0_reference_image_analysis",
            "aspects": {
                "rendering": [
                    {
                        "id": "rendering_soft_edges",
                        "prompt": "soft edges",
                        "confidence": 0.6,
                        "source_images": ["reference_images/ref-a.png"],
                        "notes": "",
                    }
                ],
                "color_light": [],
                "texture_artifacts": [],
            },
        }

        rows = build_notebook_candidate_preview_rows(document)

        self.assertEqual(
            rows,
            (
                {
                    "aspect": "rendering",
                    "id": "rendering_soft_edges",
                    "prompt": "soft edges",
                    "confidence": 0.6,
                    "source_images": ["reference_images/ref-a.png"],
                },
            ),
        )
        self.assertEqual(document["aspects"]["rendering"][0]["prompt"], "soft edges")

    def test_exp_003d_rejects_invalid_candidate_preview_document(self):
        invalid_document = {
            "version": "0.1.0",
            "source": "phase0_reference_image_analysis",
            "aspects": {
                "rendering": [],
            },
        }

        with self.assertRaisesRegex(Phase0Error, "missing aspect"):
            build_notebook_candidate_preview_rows(invalid_document)

    def test_exp_003d_loads_preview_rows_and_exports_phase0_zip(self):
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "colab-phase0"
            phase0_dir = run_dir / "phase0"
            phase0_dir.mkdir(parents=True)
            candidates_path = phase0_dir / "style_gene_candidates.json"
            candidates_path.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "source": "phase0_reference_image_analysis",
                        "aspects": {
                            "rendering": [],
                            "color_light": [],
                            "texture_artifacts": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (phase0_dir / "reference_image_manifest.json").write_text(
                "{}",
                encoding="utf-8",
            )

            rows = load_notebook_candidate_preview_rows(candidates_path)
            export_manifest = build_notebook_phase0_export_manifest(run_dir=run_dir)
            export_zip_path = write_notebook_phase0_export_zip(run_dir=run_dir)
            with zipfile.ZipFile(export_zip_path) as archive:
                zip_names = sorted(archive.namelist())

        self.assertEqual(rows, ())
        self.assertEqual(
            export_manifest["artifact_paths"],
            [
                "phase0/reference_image_manifest.json",
                "phase0/style_gene_candidates.json",
            ],
        )
        self.assertEqual(
            zip_names,
            [
                "phase0/reference_image_manifest.json",
                "phase0/style_gene_candidates.json",
                "phase0_export_manifest.json",
            ],
        )

    def test_exp_003d_builds_preview_and_export_cells(self):
        cells = build_colab_preview_and_export_cells()

        self.assertEqual(
            [cell.name for cell in cells],
            ["candidate-preview", "output-export"],
        )
        self.assertIn("load_notebook_candidate_preview_rows", cells[0].source)
        self.assertIn("files.download", cells[1].source)
        self.assertIn("write_notebook_phase0_export_zip", cells[1].source)


class NotebookSmokeTests(unittest.TestCase):
    def test_exp_003e_package_exports_notebook_helpers(self):
        expected_exports = (
            "NotebookPhase0AnalysisResult",
            "NotebookReferenceImageStagingResult",
            "build_colab_phase0_notebook",
            "stage_notebook_reference_images",
            "write_notebook_phase0_export_zip",
        )

        for export_name in expected_exports:
            with self.subTest(export_name=export_name):
                self.assertTrue(hasattr(style_fit_profiler, export_name))
                self.assertIn(export_name, style_fit_profiler.__all__)

    def test_exp_003e_builds_full_colab_phase0_notebook_document(self):
        notebook = build_colab_phase0_notebook(
            project_root="/content/style-fit-profiler",
            run_id="colab-smoke",
            batch_size=1,
        )

        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(
            [
                cell["metadata"]["id"]
                for cell in notebook["cells"]
            ],
            [
                "runtime-setup",
                "dependency-check",
                "reference-upload",
                "phase0-analysis",
                "candidate-preview",
                "output-export",
            ],
        )
        json.dumps(notebook)

    def test_exp_003e_smoke_flow_preserves_phase0_contract_with_mock_backend(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "colab-phase0"
            stage_result = stage_notebook_reference_images(
                project_root=project_root,
                uploaded_files={
                    "ref-a.png": _png_header_bytes(width=2, height=3),
                    "ref-b.png": _png_header_bytes(width=4, height=5),
                },
                run_dir=run_dir,
            )
            analysis_result = run_notebook_phase0_analysis(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
                use_batch=True,
                batch_size=1,
            )
            preview_rows = load_notebook_candidate_preview_rows(
                run_dir / analysis_result.style_gene_candidates_path
            )
            export_zip_path = write_notebook_phase0_export_zip(run_dir=run_dir)
            export_zip_exists = export_zip_path.is_file()

        self.assertEqual(
            stage_result.reference_image_paths,
            ("reference_images/ref-a.png", "reference_images/ref-b.png"),
        )
        self.assertEqual(analysis_result.batch_summary["failed_batches"], 0)
        self.assertEqual(len(preview_rows), 6)
        self.assertTrue(export_zip_exists)


def _png_header_bytes(*, width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\r"
        b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )


def _jpeg_header_bytes(*, width: int, height: int) -> bytes:
    return (
        b"\xff\xd8"
        b"\xff\xc0"
        b"\x00\x11"
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )


if __name__ == "__main__":
    unittest.main()
