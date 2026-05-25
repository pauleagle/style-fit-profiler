import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import parse_cr001_raw_response  # noqa: E402


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


class CR001RawResponseParserTests(unittest.TestCase):
    def test_cr001_04_parses_valid_raw_response_into_source_linked_record(self):
        result = parse_cr001_raw_response(
            raw_response=_valid_raw_response(),
            source_image="reference_images/ref-001.png",
        )

        self.assertTrue(result.valid)
        self.assertIsNone(result.error)
        self.assertEqual(result.source_image, "reference_images/ref-001.png")
        self.assertEqual(result.record["source_image"], "reference_images/ref-001.png")
        self.assertIn("appeal_point_and_art_style", result.record)
        self.assertTrue(result.record["cr001_summary"].strip())

    def test_cr001_04_normalizes_lowercase_impression_colors_in_valid_record(self):
        raw_document = json.loads(_valid_raw_response())
        raw_document["appeal_point_and_art_style"]["impression_colors"] = {
            "main": "#88c8ff",
            "secondary": "#f8b0d0",
            "accent": "#fff2a8",
        }

        result = parse_cr001_raw_response(
            raw_response=json.dumps(raw_document),
            source_image="reference_images/ref-001.png",
        )

        self.assertTrue(result.valid)
        self.assertEqual(
            result.record["appeal_point_and_art_style"]["impression_colors"],
            {
                "main": "#88C8FF",
                "secondary": "#F8B0D0",
                "accent": "#FFF2A8",
            },
        )

    def test_cr001_04_rejects_malformed_json_without_throwing(self):
        result = parse_cr001_raw_response(
            raw_response="{not json",
            source_image="reference_images/ref-001.png",
        )

        self.assertFalse(result.valid)
        self.assertIsNone(result.record)
        self.assertIn("invalid CR-001 raw JSON", result.error)

    def test_cr001_04_rejects_unknown_raw_top_level_key(self):
        raw_document = json.loads(_valid_raw_response())
        raw_document["schema_version"] = "cr001.v1"

        result = parse_cr001_raw_response(
            raw_response=json.dumps(raw_document),
            source_image="reference_images/ref-001.png",
        )

        self.assertFalse(result.valid)
        self.assertIn("unknown key", result.error)
        self.assertIn("schema_version", result.error)

    def test_cr001_04_rejects_schema_mismatch_as_invalid_result(self):
        raw_document = json.loads(_valid_raw_response())
        del raw_document["appeal_point_and_art_style"]["expected_style_genes"]["genre"]

        result = parse_cr001_raw_response(
            raw_response=json.dumps(raw_document),
            source_image="reference_images/ref-001.png",
        )

        self.assertFalse(result.valid)
        self.assertIsNone(result.record)
        self.assertIn("missing locus", result.error)

    def test_cr001_04_rejects_invalid_source_image_traceability(self):
        invalid_source_images = (
            "",
            "/reference_images/ref-001.png",
            "\\reference_images\\ref-001.png",
            "C:reference_images\\ref-001.png",
            "C:\\reference_images\\ref-001.png",
        )

        for source_image in invalid_source_images:
            with self.subTest(source_image=source_image):
                result = parse_cr001_raw_response(
                    raw_response=_valid_raw_response(),
                    source_image=source_image,
                )

                self.assertFalse(result.valid)
                self.assertIsNone(result.record)
                self.assertIn("source_image", result.error)

    def test_cr001_04_does_not_accept_llm_raw_source_image_field(self):
        raw_document = json.loads(_valid_raw_response())
        raw_document["source_image"] = "reference_images/ref-001.png"

        result = parse_cr001_raw_response(
            raw_response=json.dumps(raw_document),
            source_image="reference_images/ref-001.png",
        )

        self.assertFalse(result.valid)
        self.assertIn("unknown key", result.error)
        self.assertIn("source_image", result.error)


if __name__ == "__main__":
    unittest.main()
