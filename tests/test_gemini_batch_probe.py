from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.gemini_batch_probe import (  # noqa: E402
    CR001_BATCH_BACKEND,
    DEFAULT_BATCH_RUN_DIR,
    DEFAULT_BATCH_BACKEND,
    GeminiBatchProbeResult,
    LEGACY_BATCH_BACKEND,
    main,
    parse_args,
)
from style_fit_profiler.gemini_image_probe import (  # noqa: E402
    DEFAULT_BATCH_ANALYSIS_PROMPT,
    GeminiImageProbeError,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


def _png_header_bytes(*, width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def _valid_cr001_raw_response(*, source_image="reference_images/ref-001.png"):
    document = json.loads(
        (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
            encoding="utf-8"
        )
    )
    record = copy.deepcopy(document["records"][0])
    record["source_image"] = source_image
    return json.dumps(
        {
            "appeal_point_and_art_style": record["appeal_point_and_art_style"],
            "cr001_summary": record["cr001_summary"],
        }
    )


class GeminiBatchProbeCommandTests(unittest.TestCase):
    def test_batch_command_exposes_manual_gemini_options(self):
        args = parse_args(
            [
                "--backend",
                "legacy",
                "--project-root",
                "C:/project",
                "--input-dir",
                "refs",
                "--run-dir",
                "runs/manual",
                "--batch-size",
                "3",
                "--model",
                "gemini-test-model",
                "--prompt-file",
                "prompt.txt",
                "--timeout-seconds",
                "7",
                "--max-attempts",
                "3",
            ]
        )

        self.assertEqual(args.backend, LEGACY_BATCH_BACKEND)
        self.assertEqual(args.project_root, Path("C:/project"))
        self.assertEqual(args.input_dir, "refs")
        self.assertEqual(args.run_dir, Path("runs/manual"))
        self.assertEqual(args.batch_size, 3)
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.prompt_file, Path("prompt.txt"))
        self.assertEqual(args.timeout_seconds, 7)
        self.assertEqual(args.max_attempts, 3)

    def test_batch_command_uses_safe_default_output_dir(self):
        args = parse_args([])

        self.assertEqual(args.run_dir, DEFAULT_BATCH_RUN_DIR)
        self.assertEqual(args.backend, DEFAULT_BATCH_BACKEND)
        self.assertEqual(args.backend, CR001_BATCH_BACKEND)
        self.assertEqual(args.input_dir, "reference_images")
        self.assertEqual(args.batch_size, 2)
        self.assertEqual(args.max_attempts, 1)

    def test_batch_command_requires_env_api_key_before_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GeminiImageProbeError, "GEMINI_API_KEY"):
                main([])

    def test_batch_command_defaults_to_cr001_native_backend(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                calls.append(("init", api_key, model, timeout_seconds))
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                calls.append(("analyze_image", image_path.name, source_image))
                return _valid_cr001_raw_response(source_image=source_image)

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "manual-gemini-batch"
            reference_dir.mkdir()
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=4, height=5))
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_batch_probe.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "2",
                        "--model",
                        "gemini-test-model",
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            manifest = json.loads(
                (run_dir / "phase0" / "reference_image_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            artifact = json.loads(
                (run_dir / "phase0" / "cr001_reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (run_dir / "phase0" / "cr001_batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-test-model", 60),
                ("analyze_image", "a.png", "reference_images/a.png"),
                ("analyze_image", "b.png", "reference_images/b.png"),
            ],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(report["summary"]["completed_batches"], 1)
        self.assertEqual(report["summary"]["failed_batches"], 0)
        self.assertEqual(
            stdout_record["native_artifact_path"],
            "phase0/cr001_reference_image_analysis.json",
        )
        self.assertEqual(
            stdout_record["batch_run_report_path"],
            "phase0/cr001_batch_run_report.json",
        )
        self.assertNotIn("style_gene_candidates_path", stdout_record)
        self.assertFalse((run_dir / "phase0" / "style_gene_candidates.json").exists())

    def test_batch_command_rejects_prompt_file_for_cr001_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            prompt_file = project_root / "prompt.txt"
            prompt_file.write_text("legacy prompt", encoding="utf-8")
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                self.assertRaisesRegex(GeminiImageProbeError, "backend legacy"),
            ):
                main(
                    [
                        "--project-root",
                        str(project_root),
                        "--prompt-file",
                        str(prompt_file),
                    ]
                )

    def test_batch_command_writes_candidates_manifest_and_batch_report(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                calls.append(("init", api_key, model, prompt, timeout_seconds))
                self.model = model

            def analyze_images(self, *, image_paths, source_images):
                calls.append(
                    (
                        "analyze_images",
                        tuple(image_path.name for image_path in image_paths),
                        tuple(source_images),
                    )
                )
                image_records = []
                for source_image in source_images:
                    stem = Path(source_image).stem
                    image_records.append(
                        {
                            "path": source_image,
                            "rendering": [f"clean linework {stem}"],
                            "color_light": [f"soft warm light {stem}"],
                            "texture_artifacts": [],
                            "notes": f"fixture response {stem}",
                        }
                    )
                return json.dumps({"images": image_records})

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "gemini-batch"
            reference_dir.mkdir()
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=4, height=5))
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_batch_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "2",
                        "--model",
                        "gemini-test-model",
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            manifest = json.loads(
                (run_dir / "phase0" / "reference_image_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            candidates = json.loads(
                (run_dir / "phase0" / "style_gene_candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            image_analysis = json.loads(
                (run_dir / "phase0" / "reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (run_dir / "phase0" / "batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-test-model", DEFAULT_BATCH_ANALYSIS_PROMPT, 60),
                (
                    "analyze_images",
                    ("a.png", "b.png"),
                    ("reference_images/a.png", "reference_images/b.png"),
                ),
            ],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(candidates["source"], "phase0_batch_reference_image_analysis")
        self.assertEqual(
            [
                candidate["source_images"]
                for candidate in candidates["aspects"]["rendering"]
            ],
            [["reference_images/a.png"], ["reference_images/b.png"]],
        )
        self.assertEqual(
            [record["path"] for record in image_analysis["images"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(
            [record["analysis_status"] for record in image_analysis["images"]],
            ["completed", "completed"],
        )
        self.assertEqual(
            image_analysis["images"][0]["traits"]["rendering"],
            ["clean linework a"],
        )
        self.assertEqual(len(image_analysis["raw_responses"]), 1)
        self.assertEqual(
            image_analysis["raw_responses"][0]["validation_status"],
            "valid",
        )
        self.assertEqual(report["summary"]["total_batches"], 1)
        self.assertEqual(report["summary"]["completed_batches"], 1)
        self.assertEqual(report["summary"]["failed_batches"], 0)
        self.assertEqual(report["batches"][0]["attempt_count"], 1)
        self.assertEqual(report["batches"][0]["max_attempts"], 1)
        self.assertEqual(report["batches"][0]["remaining_attempts"], 0)
        self.assertEqual(
            report["batches"][0]["output_paths"],
            ["phase0/reference_image_analysis.json"],
        )
        self.assertEqual(
            stdout_record["reference_image_analysis_path"],
            "phase0/reference_image_analysis.json",
        )
        self.assertEqual(
            stdout_record["style_gene_candidates_path"],
            "phase0/style_gene_candidates.json",
        )
        self.assertEqual(stdout_record["summary"]["total_batches"], 1)

    def test_batch_command_writes_partial_outputs_and_returns_failure_for_failed_batch(self):
        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                self.model = model

            def analyze_images(self, *, image_paths, source_images):
                if image_paths[0].name == "b.png":
                    raise GeminiImageProbeError("Gemini API HTTP 500: boom")
                return json.dumps(
                    {
                        "images": [
                            {
                                "path": source_images[0],
                                "rendering": ["clean linework"],
                                "color_light": [],
                                "texture_artifacts": [],
                                "notes": "fixture response",
                            }
                        ]
                    }
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "gemini-batch"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=4, height=5))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_batch_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "1",
                    ]
                )

            candidates = json.loads(
                (run_dir / "phase0" / "style_gene_candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            image_analysis = json.loads(
                (run_dir / "phase0" / "reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (run_dir / "phase0" / "batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(report["summary"]["completed_batches"], 1)
        self.assertEqual(report["summary"]["failed_batches"], 1)
        self.assertEqual(report["summary"]["retryable_batch_indexes"], [1])
        self.assertEqual(report["batches"][1]["status"], "failed")
        self.assertIn("b.png", report["batches"][1]["error"])
        self.assertEqual(report["batches"][1]["attempt_count"], 1)
        self.assertEqual(report["batches"][1]["max_attempts"], 1)
        self.assertEqual(report["batches"][1]["remaining_attempts"], 0)
        self.assertTrue(report["batches"][1]["retry_exhausted"])
        self.assertEqual(
            [record["analysis_status"] for record in image_analysis["images"]],
            ["completed", "failed"],
        )
        self.assertEqual(image_analysis["images"][1]["path"], "reference_images/b.png")
        self.assertIn("HTTP 500", image_analysis["images"][1]["error"])
        self.assertEqual(len(image_analysis["raw_responses"]), 1)
        self.assertEqual(
            image_analysis["raw_responses"][0]["validation_status"],
            "valid",
        )
        self.assertEqual(len(candidates["aspects"]["rendering"]), 1)

    def test_batch_command_retries_failed_batch_with_configured_attempt_budget(self):
        calls_by_image = {}

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                self.model = model

            def analyze_images(self, *, image_paths, source_images):
                first_name = image_paths[0].name
                calls_by_image[first_name] = calls_by_image.get(first_name, 0) + 1
                if first_name == "b.png" and calls_by_image[first_name] == 1:
                    return "not json yet"
                return json.dumps(
                    {
                        "images": [
                            {
                                "path": source_images[0],
                                "rendering": [f"clean linework {Path(source_images[0]).stem}"],
                                "color_light": [],
                                "texture_artifacts": [],
                                "notes": "fixture response",
                            }
                        ]
                    }
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "gemini-batch"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=4, height=5))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_batch_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "1",
                        "--max-attempts",
                        "2",
                    ]
                )

            image_analysis = json.loads(
                (run_dir / "phase0" / "reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (run_dir / "phase0" / "batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertEqual(calls_by_image, {"a.png": 1, "b.png": 2})
        self.assertEqual(report["summary"]["completed_batches"], 2)
        self.assertEqual(report["summary"]["failed_batches"], 0)
        self.assertEqual(report["batches"][1]["attempt_count"], 2)
        self.assertEqual(report["batches"][1]["max_attempts"], 2)
        self.assertEqual(report["batches"][1]["remaining_attempts"], 0)
        self.assertEqual(
            [record["validation_status"] for record in image_analysis["raw_responses"]],
            ["valid", "invalid_retryable", "valid"],
        )
        self.assertEqual(
            [record["attempt_index"] for record in image_analysis["raw_responses"]],
            [1, 1, 2],
        )
        self.assertIn(
            "invalid Gemini batch trait JSON",
            image_analysis["raw_responses"][1]["error"],
        )

    def test_batch_command_marks_final_invalid_raw_response_non_retryable(self):
        calls_by_image = {}

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                pass

            def analyze_images(self, *, image_paths, source_images):
                first_name = image_paths[0].name
                calls_by_image[first_name] = calls_by_image.get(first_name, 0) + 1
                return "still not json"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "gemini-batch"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_batch_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "1",
                        "--max-attempts",
                        "2",
                    ]
                )

            image_analysis = json.loads(
                (run_dir / "phase0" / "reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (run_dir / "phase0" / "batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls_by_image, {"a.png": 2})
        self.assertEqual(report["summary"]["failed_batches"], 1)
        self.assertEqual(report["batches"][0]["attempt_count"], 2)
        self.assertEqual(report["batches"][0]["remaining_attempts"], 0)
        self.assertTrue(report["batches"][0]["retry_exhausted"])
        self.assertEqual(
            [record["validation_status"] for record in image_analysis["raw_responses"]],
            ["invalid_retryable", "invalid_non_retryable"],
        )
        self.assertEqual(
            [record["attempt_index"] for record in image_analysis["raw_responses"]],
            [1, 2],
        )

    def test_batch_probe_result_reports_failed_batches(self):
        result = GeminiBatchProbeResult(
            reference_image_manifest_path="phase0/reference_image_manifest.json",
            reference_image_analysis_path="phase0/reference_image_analysis.json",
            style_gene_candidates_path="phase0/style_gene_candidates.json",
            batch_run_report_path="phase0/batch_run_report.json",
            summary={"failed_batches": 1},
        )

        self.assertTrue(result.has_failed_batches)
        self.assertEqual(
            result.to_json_record()["batch_run_report_path"],
            "phase0/batch_run_report.json",
        )


if __name__ == "__main__":
    unittest.main()
