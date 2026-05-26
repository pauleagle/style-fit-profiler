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

from style_fit_profiler.cr001_gemini_probe import (  # noqa: E402
    DEFAULT_BATCH_RUN_DIR,
    DEFAULT_SINGLE_RUN_DIR,
    CR001GeminiProbeError,
    main,
    parse_args,
)
from style_fit_profiler.gemini_image_probe import GeminiImageProbeError  # noqa: E402


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


def _valid_raw_response(*, source_image="reference_images/ref-001.png"):
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


class CR001GeminiProbeCommandTests(unittest.TestCase):
    def test_single_command_exposes_manual_cr001_options(self):
        args = parse_args(
            [
                "single",
                "reference_images/ref-001.png",
                "--project-root",
                "C:/project",
                "--run-dir",
                "runs/manual-single",
                "--model",
                "gemini-test-model",
                "--timeout-seconds",
                "7",
                "--raw-output",
                "raw/cr001.json",
            ]
        )

        self.assertEqual(args.command, "single")
        self.assertEqual(args.image_path, Path("reference_images/ref-001.png"))
        self.assertEqual(args.project_root, Path("C:/project"))
        self.assertEqual(args.run_dir, Path("runs/manual-single"))
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.timeout_seconds, 7)
        self.assertEqual(args.raw_output, Path("raw/cr001.json"))

    def test_batch_command_exposes_manual_cr001_options(self):
        args = parse_args(
            [
                "batch",
                "--project-root",
                "C:/project",
                "--input-dir",
                "refs",
                "--run-dir",
                "runs/manual-batch",
                "--batch-size",
                "3",
                "--max-attempts",
                "2",
                "--model",
                "gemini-test-model",
                "--timeout-seconds",
                "7",
            ]
        )

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.project_root, Path("C:/project"))
        self.assertEqual(args.input_dir, "refs")
        self.assertEqual(args.run_dir, Path("runs/manual-batch"))
        self.assertEqual(args.batch_size, 3)
        self.assertEqual(args.max_attempts, 2)
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.timeout_seconds, 7)

    def test_commands_use_safe_default_output_dirs(self):
        single_args = parse_args(["single", "reference_images/ref-001.png"])
        batch_args = parse_args(["batch"])

        self.assertEqual(single_args.run_dir, DEFAULT_SINGLE_RUN_DIR)
        self.assertEqual(batch_args.run_dir, DEFAULT_BATCH_RUN_DIR)
        self.assertEqual(batch_args.input_dir, "reference_images")
        self.assertEqual(batch_args.batch_size, 2)
        self.assertEqual(batch_args.max_attempts, 1)

    def test_command_requires_env_api_key_before_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(CR001GeminiProbeError, "GEMINI_API_KEY"):
                main(["batch"])

    def test_single_command_writes_manifest_native_artifact_and_raw_response(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                calls.append(("init", api_key, model, timeout_seconds))
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                calls.append(("analyze_image", image_path.name, source_image))
                return _valid_raw_response(source_image=source_image)

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "cr001-single"
            reference_dir.mkdir()
            (reference_dir / "ref-001.png").write_bytes(
                _png_header_bytes(width=2, height=3)
            )

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.cr001_gemini_probe.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "single",
                        "reference_images/ref-001.png",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--model",
                        "gemini-test-model",
                        "--raw-output",
                        "raw/cr001-response.json",
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
            raw_response = json.loads(
                (run_dir / "raw" / "cr001-response.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-test-model", 60),
                ("analyze_image", "ref-001.png", "reference_images/ref-001.png"),
            ],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/ref-001.png"],
        )
        self.assertEqual(artifact["schema_version"], "cr001.v1")
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/ref-001.png"],
        )
        self.assertTrue(stdout_record["valid"])
        self.assertEqual(
            stdout_record["native_artifact_path"],
            "phase0/cr001_reference_image_analysis.json",
        )
        self.assertEqual(stdout_record["raw_response_path"], "raw/cr001-response.json")
        self.assertTrue(raw_response["valid"])
        self.assertIn("appeal_point_and_art_style", raw_response["response_text"])

    def test_single_command_returns_failure_and_keeps_invalid_raw_out_of_native_records(self):
        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                return "{not json"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "cr001-single"
            reference_dir.mkdir()
            (reference_dir / "ref-001.png").write_bytes(
                _png_header_bytes(width=2, height=3)
            )

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.cr001_gemini_probe.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "single",
                        "reference_images/ref-001.png",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            artifact = json.loads(
                (run_dir / "phase0" / "cr001_reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 1)
        self.assertFalse(stdout_record["valid"])
        self.assertIn("invalid CR-001 raw JSON", stdout_record["error"])
        self.assertEqual(artifact["records"], [])

    def test_exp_001_fu_01d_single_classifies_provider_error_without_retry(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                calls.append(("analyze_image", image_path.name, source_image))
                raise GeminiImageProbeError(
                    'Gemini API HTTP 429: {"error":{"code":429,'
                    '"status":"RESOURCE_EXHAUSTED",'
                    '"message":"Quota exceeded. Please retry in 5s."}}'
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "cr001-single"
            reference_dir.mkdir()
            (reference_dir / "ref-001.png").write_bytes(
                _png_header_bytes(width=2, height=3)
            )

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.cr001_gemini_probe.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "single",
                        "reference_images/ref-001.png",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            artifact = json.loads(
                (run_dir / "phase0" / "cr001_reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(
            calls,
            [("analyze_image", "ref-001.png", "reference_images/ref-001.png")],
        )
        self.assertFalse(stdout_record["valid"])
        self.assertEqual(
            stdout_record["provider_error"]["type"],
            "provider_quota_exhausted",
        )
        self.assertEqual(stdout_record["provider_error"]["provider_status"], "RESOURCE_EXHAUSTED")
        self.assertEqual(stdout_record["provider_error"]["retry_after_seconds"], 5.0)
        self.assertEqual(artifact["records"], [])
        self.assertNotIn("provider_error", artifact)

    def test_batch_command_writes_manifest_native_artifact_and_batch_report_only(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                calls.append(("init", api_key, model, timeout_seconds))
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                calls.append(("analyze_image", image_path.name, source_image))
                return _valid_raw_response(source_image=source_image)

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "cr001-batch"
            reference_dir.mkdir()
            (reference_dir / "b.png").write_bytes(_png_header_bytes(width=4, height=5))
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.cr001_gemini_probe.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "batch",
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
        self.assertFalse((run_dir / "phase0" / "style_gene_candidates.json").exists())


if __name__ == "__main__":
    unittest.main()
