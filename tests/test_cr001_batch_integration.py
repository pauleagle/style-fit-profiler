import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001_BATCH_RUN_REPORT_PATH,
    CR001_NATIVE_ARTIFACT_PATH,
    CR001GeminiRawAnalysis,
    run_cr001_batch_extraction,
)
from style_fit_profiler.gemini_image_probe import GeminiImageProbeError  # noqa: E402


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


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


class CR001BatchIntegrationTests(unittest.TestCase):
    def test_cr001_07b_writes_native_artifact_and_batch_report_for_valid_records(self):
        calls = []

        def raw_extractor(records):
            calls.append(tuple(record["path"] for record in records))
            return tuple(
                CR001GeminiRawAnalysis(
                    source_image=record["path"],
                    response_text=_valid_raw_response(source_image=record["path"]),
                    model="gemini-fake-model",
                )
                for record in records
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "run-001"
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=(
                    {"path": "reference_images/b.png"},
                    {"path": "reference_images/a.png"},
                ),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=2,
                max_attempts=1,
            )
            artifact = json.loads(
                (run_dir / result.native_artifact_path).read_text(encoding="utf-8")
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertEqual(result.native_artifact_path, CR001_NATIVE_ARTIFACT_PATH)
        self.assertEqual(result.batch_run_report_path, CR001_BATCH_RUN_REPORT_PATH)
        self.assertFalse(result.has_failed_batches)
        self.assertEqual(calls, [("reference_images/a.png", "reference_images/b.png")])
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(report["summary"]["completed_batches"], 1)
        self.assertEqual(report["summary"]["failed_batches"], 0)
        self.assertEqual(report["batches"][0]["status"], "completed")
        self.assertEqual(
            report["batches"][0]["output_paths"],
            [CR001_NATIVE_ARTIFACT_PATH],
        )

    def test_cr001_07b_preserves_valid_records_when_batch_has_final_failure(self):
        def raw_extractor(records):
            analyses = []
            for record in records:
                if record["path"] == "reference_images/b.png":
                    analyses.append(
                        CR001GeminiRawAnalysis(
                            source_image=record["path"],
                            response_text="{not json",
                            model="gemini-fake-model",
                        )
                    )
                    continue
                analyses.append(
                    CR001GeminiRawAnalysis(
                        source_image=record["path"],
                        response_text=_valid_raw_response(source_image=record["path"]),
                        model="gemini-fake-model",
                    )
                )
            return tuple(analyses)

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=(
                    {"path": "reference_images/a.png"},
                    {"path": "reference_images/b.png"},
                ),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=2,
                max_attempts=1,
            )
            artifact = json.loads(
                (run_dir / result.native_artifact_path).read_text(encoding="utf-8")
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertTrue(result.has_failed_batches)
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/a.png"],
        )
        self.assertEqual(report["summary"]["failed_batches"], 1)
        self.assertEqual(report["summary"]["retryable_batch_indexes"], [0])
        self.assertEqual(report["batches"][0]["status"], "failed")
        self.assertEqual(report["batches"][0]["failed_image_paths"], ["reference_images/b.png"])
        self.assertEqual(report["batches"][0]["attempt_count"], 1)
        self.assertEqual(report["batches"][0]["max_attempts"], 1)
        self.assertEqual(report["batches"][0]["remaining_attempts"], 0)
        self.assertTrue(report["batches"][0]["retry_exhausted"])
        self.assertEqual(report["images"][0]["analysis_status"], "completed")
        self.assertEqual(report["images"][1]["analysis_status"], "failed")
        self.assertIn("invalid CR-001 raw JSON", report["images"][1]["error"])

    def test_cr001_07b_retries_only_failed_image_scope(self):
        calls = []

        def raw_extractor(records):
            calls.append(tuple(record["path"] for record in records))
            analyses = []
            for record in records:
                if record["path"] == "reference_images/b.png" and len(calls) == 1:
                    analyses.append(
                        CR001GeminiRawAnalysis(
                            source_image=record["path"],
                            response_text="{not json",
                            model="gemini-fake-model",
                        )
                    )
                    continue
                analyses.append(
                    CR001GeminiRawAnalysis(
                        source_image=record["path"],
                        response_text=_valid_raw_response(source_image=record["path"]),
                        model="gemini-fake-model",
                    )
                )
            return tuple(analyses)

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=(
                    {"path": "reference_images/a.png"},
                    {"path": "reference_images/b.png"},
                ),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=2,
                max_attempts=2,
            )
            artifact = json.loads(
                (run_dir / result.native_artifact_path).read_text(encoding="utf-8")
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertFalse(result.has_failed_batches)
        self.assertEqual(calls, [("reference_images/a.png", "reference_images/b.png"), ("reference_images/b.png",)])
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(report["batches"][0]["status"], "completed")
        self.assertEqual(report["batches"][0]["attempt_count"], 2)
        self.assertEqual(report["batches"][0]["remaining_attempts"], 0)
        self.assertEqual(
            [record["analysis_status"] for record in report["images"]],
            ["completed", "completed"],
        )

    def test_cr001_07b_does_not_overwrite_style_gene_pool(self):
        def raw_extractor(records):
            return tuple(
                CR001GeminiRawAnalysis(
                    source_image=record["path"],
                    response_text=_valid_raw_response(source_image=record["path"]),
                    model="gemini-fake-model",
                )
                for record in records
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            gene_pool_path = run_dir / "style_gene_pool.json"
            original_gene_pool = '{"version":"0.1.0","genes":{"rendering":[]}}\n'
            gene_pool_path.write_text(original_gene_pool, encoding="utf-8")

            run_cr001_batch_extraction(
                reference_image_manifest_records=({"path": "reference_images/a.png"},),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=1,
                max_attempts=1,
            )

            gene_pool_after = gene_pool_path.read_text(encoding="utf-8")

        self.assertEqual(gene_pool_after, original_gene_pool)

    def test_cr001_07b_unexpected_raw_source_does_not_enter_retry_scope(self):
        def raw_extractor(records):
            return (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/unexpected.png",
                    response_text=_valid_raw_response(
                        source_image="reference_images/unexpected.png"
                    ),
                    model="gemini-fake-model",
                ),
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=({"path": "reference_images/a.png"},),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=1,
                max_attempts=1,
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertTrue(result.has_failed_batches)
        self.assertEqual(report["batches"][0]["failed_image_paths"], ["reference_images/a.png"])
        self.assertIn("missing raw analysis", report["batches"][0]["error"])
        images_by_path = {record["path"]: record for record in report["images"]}
        self.assertIn("reference_images/unexpected.png", images_by_path)
        self.assertIn(
            "unexpected source_image",
            images_by_path["reference_images/unexpected.png"]["error"],
        )

    def test_exp_001_fu_01f_retries_retryable_provider_error_for_failed_image_scope(self):
        calls = []

        def raw_extractor(records):
            calls.append(tuple(record["path"] for record in records))
            analyses = []
            for record in records:
                if record["path"] == "reference_images/b.png" and len(calls) == 1:
                    raise GeminiImageProbeError(
                        'Gemini API HTTP 429: {"error":{"code":429,'
                        '"status":"RESOURCE_EXHAUSTED",'
                        '"message":"Quota exceeded. Please retry in 5s."}}'
                    )
                analyses.append(
                    CR001GeminiRawAnalysis(
                        source_image=record["path"],
                        response_text=_valid_raw_response(source_image=record["path"]),
                        model="gemini-fake-model",
                    )
                )
            return tuple(analyses)

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=(
                    {"path": "reference_images/a.png"},
                    {"path": "reference_images/b.png"},
                ),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=2,
                max_attempts=2,
            )
            artifact = json.loads(
                (run_dir / result.native_artifact_path).read_text(encoding="utf-8")
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertFalse(result.has_failed_batches)
        self.assertEqual(
            calls,
            [
                ("reference_images/a.png", "reference_images/b.png"),
                ("reference_images/a.png", "reference_images/b.png"),
            ],
        )
        self.assertEqual(report["summary"]["retried_batches"], 1)
        self.assertEqual(report["batches"][0]["attempt_count"], 2)
        self.assertIsNone(report["batches"][0]["provider_error"])
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertNotIn("provider_error", artifact)

    def test_exp_001_fu_01f_records_exhausted_provider_error_without_native_pollution(self):
        def raw_extractor(records):
            raise GeminiImageProbeError(
                'Gemini API HTTP 429: {"error":{"code":429,'
                '"status":"RESOURCE_EXHAUSTED",'
                '"message":"Quota exceeded. Please retry in 5s."}}'
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=({"path": "reference_images/a.png"},),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=1,
                max_attempts=2,
            )
            artifact = json.loads(
                (run_dir / result.native_artifact_path).read_text(encoding="utf-8")
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertTrue(result.has_failed_batches)
        self.assertEqual(artifact["records"], [])
        self.assertNotIn("provider_error", artifact)
        self.assertEqual(report["batches"][0]["attempt_count"], 2)
        self.assertTrue(report["batches"][0]["retryable"])
        self.assertEqual(
            report["batches"][0]["provider_error"]["type"],
            "provider_quota_exhausted",
        )
        self.assertEqual(report["batches"][0]["failed_image_paths"], ["reference_images/a.png"])

    def test_exp_001_fu_01f_does_not_retry_non_retryable_provider_error(self):
        calls = []

        def raw_extractor(records):
            calls.append(tuple(record["path"] for record in records))
            raise GeminiImageProbeError(
                'Gemini API HTTP 400: {"error":{"code":400,'
                '"status":"INVALID_ARGUMENT",'
                '"message":"Bad request."}}'
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = run_cr001_batch_extraction(
                reference_image_manifest_records=({"path": "reference_images/a.png"},),
                run_dir=run_dir,
                raw_extractor=raw_extractor,
                batch_size=1,
                max_attempts=3,
            )
            report = json.loads(
                (run_dir / result.batch_run_report_path).read_text(encoding="utf-8")
            )

        self.assertTrue(result.has_failed_batches)
        self.assertEqual(calls, [("reference_images/a.png",)])
        self.assertEqual(report["summary"]["retryable_batch_indexes"], [])
        self.assertFalse(report["batches"][0]["retryable"])
        self.assertEqual(report["batches"][0]["attempt_count"], 1)
        self.assertEqual(report["batches"][0]["provider_error"]["type"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
