from contextlib import redirect_stdout
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
    DEFAULT_BATCH_RUN_DIR,
    GeminiBatchProbeResult,
    main,
    parse_args,
)
from style_fit_profiler.gemini_image_probe import (  # noqa: E402
    DEFAULT_ANALYSIS_PROMPT,
    GeminiImageProbeError,
)


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


class GeminiBatchProbeCommandTests(unittest.TestCase):
    def test_batch_command_exposes_manual_gemini_options(self):
        args = parse_args(
            [
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
            ]
        )

        self.assertEqual(args.project_root, Path("C:/project"))
        self.assertEqual(args.input_dir, "refs")
        self.assertEqual(args.run_dir, Path("runs/manual"))
        self.assertEqual(args.batch_size, 3)
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.prompt_file, Path("prompt.txt"))
        self.assertEqual(args.timeout_seconds, 7)

    def test_batch_command_uses_safe_default_output_dir(self):
        args = parse_args([])

        self.assertEqual(args.run_dir, DEFAULT_BATCH_RUN_DIR)
        self.assertEqual(args.input_dir, "reference_images")
        self.assertEqual(args.batch_size, 2)

    def test_batch_command_requires_env_api_key_before_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GeminiImageProbeError, "GEMINI_API_KEY"):
                main([])

    def test_batch_command_writes_candidates_manifest_and_batch_report(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                calls.append(("init", api_key, model, prompt, timeout_seconds))
                self.model = model

            def analyze_image(self, image_path):
                calls.append(("analyze_image", image_path.name))
                return f"""
                {{
                  "rendering": ["clean linework {image_path.stem}"],
                  "color_light": ["soft warm light {image_path.stem}"],
                  "texture_artifacts": [],
                  "notes": "fixture response"
                }}
                """

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
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--batch-size",
                        "1",
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
            report = json.loads(
                (run_dir / "phase0" / "batch_run_report.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-test-model", DEFAULT_ANALYSIS_PROMPT, 60),
                ("analyze_image", "a.png"),
                ("analyze_image", "b.png"),
            ],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(candidates["source"], "phase0_batch_reference_image_analysis")
        self.assertEqual(report["summary"]["total_batches"], 2)
        self.assertEqual(report["summary"]["completed_batches"], 2)
        self.assertEqual(report["summary"]["failed_batches"], 0)
        self.assertEqual(
            stdout_record["style_gene_candidates_path"],
            "phase0/style_gene_candidates.json",
        )
        self.assertEqual(stdout_record["summary"]["total_batches"], 2)

    def test_batch_command_writes_partial_outputs_and_returns_failure_for_failed_batch(self):
        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                self.model = model

            def analyze_image(self, image_path):
                if image_path.name == "b.png":
                    raise GeminiImageProbeError("Gemini API HTTP 500: boom")
                return """
                {
                  "rendering": ["clean linework"],
                  "color_light": [],
                  "texture_artifacts": [],
                  "notes": "fixture response"
                }
                """

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
        self.assertEqual(len(candidates["aspects"]["rendering"]), 1)

    def test_batch_probe_result_reports_failed_batches(self):
        result = GeminiBatchProbeResult(
            reference_image_manifest_path="phase0/reference_image_manifest.json",
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
