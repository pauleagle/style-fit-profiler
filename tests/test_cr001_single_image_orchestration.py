import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001GeminiRawAnalysis,
    extract_cr001_single_image_record,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


def _valid_raw_response():
    document = json.loads(
        (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
            encoding="utf-8"
        )
    )
    record = copy.deepcopy(document["records"][0])
    return json.dumps(
        {
            "appeal_point_and_art_style": record["appeal_point_and_art_style"],
            "cr001_summary": record["cr001_summary"],
        }
    )


class CR001SingleImageExtractionOrchestrationTests(unittest.TestCase):
    def test_cr001_07a_extracts_valid_raw_into_source_linked_native_record(self):
        calls = []

        def raw_extractor(records):
            calls.append(tuple(records))
            return (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/ref-001.png",
                    response_text=_valid_raw_response(),
                    model="gemini-fake-model",
                ),
            )

        manifest_record = {"path": "reference_images/ref-001.png"}

        result = extract_cr001_single_image_record(
            reference_image_manifest_record=manifest_record,
            raw_extractor=raw_extractor,
        )

        self.assertTrue(result.valid)
        self.assertIsNone(result.error)
        self.assertEqual(result.source_image, "reference_images/ref-001.png")
        self.assertEqual(result.model, "gemini-fake-model")
        self.assertEqual(result.raw_response_text, _valid_raw_response())
        self.assertEqual(result.record["source_image"], "reference_images/ref-001.png")
        self.assertIn("appeal_point_and_art_style", result.record)
        self.assertEqual(calls, [({"path": "reference_images/ref-001.png"},)])

    def test_cr001_07a_keeps_invalid_raw_isolated_from_native_record(self):
        def raw_extractor(records):
            return (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/ref-001.png",
                    response_text="{not json",
                    model="gemini-fake-model",
                ),
            )

        result = extract_cr001_single_image_record(
            reference_image_manifest_record={"path": "reference_images/ref-001.png"},
            raw_extractor=raw_extractor,
        )

        self.assertFalse(result.valid)
        self.assertIsNone(result.record)
        self.assertEqual(result.raw_response_text, "{not json")
        self.assertIn("invalid CR-001 raw JSON", result.error)

    def test_cr001_07a_rejects_raw_source_image_mismatch(self):
        def raw_extractor(records):
            return (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/other.png",
                    response_text=_valid_raw_response(),
                    model="gemini-fake-model",
                ),
            )

        result = extract_cr001_single_image_record(
            reference_image_manifest_record={"path": "reference_images/ref-001.png"},
            raw_extractor=raw_extractor,
        )

        self.assertFalse(result.valid)
        self.assertIsNone(result.record)
        self.assertIn("source_image mismatch", result.error)

    def test_cr001_07a_rejects_extractor_cardinality_mismatch(self):
        invalid_raw_outputs = (
            (),
            (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/ref-001.png",
                    response_text=_valid_raw_response(),
                    model="gemini-fake-model",
                ),
                CR001GeminiRawAnalysis(
                    source_image="reference_images/ref-002.png",
                    response_text=_valid_raw_response(),
                    model="gemini-fake-model",
                ),
            ),
        )

        for raw_output in invalid_raw_outputs:
            with self.subTest(raw_output_count=len(raw_output)):
                result = extract_cr001_single_image_record(
                    reference_image_manifest_record={
                        "path": "reference_images/ref-001.png"
                    },
                    raw_extractor=lambda records: raw_output,
                )

                self.assertFalse(result.valid)
                self.assertIsNone(result.record)
                self.assertIn("exactly one raw analysis", result.error)


if __name__ == "__main__":
    unittest.main()
