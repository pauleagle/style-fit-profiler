import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001ValidationError,
    validate_cr001_record,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


def _valid_record():
    document = json.loads(
        (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return copy.deepcopy(document["records"][0])


class CR001RecordValidatorTests(unittest.TestCase):
    def test_cr001_02_accepts_valid_fixture_record(self):
        validate_cr001_record(_valid_record())

    def test_cr001_02_rejects_missing_required_gene_group(self):
        record = _valid_record()
        del record["appeal_point_and_art_style"]["expected_style_genes"]

        with self.assertRaisesRegex(CR001ValidationError, "expected_style_genes"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_missing_required_locus(self):
        record = _valid_record()
        del record["appeal_point_and_art_style"]["expected_style_genes"]["genre"]

        with self.assertRaisesRegex(CR001ValidationError, "missing locus"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_unknown_locus(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["expected_style_genes"]["composition"] = {
            "selected": ["center-focused"],
            "intensity": [0.8],
        }

        with self.assertRaisesRegex(CR001ValidationError, "unknown locus"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_unknown_payload_key_except_impression_colors(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["freeform_notes"] = "not allowed"

        with self.assertRaisesRegex(CR001ValidationError, "unknown key"):
            validate_cr001_record(record)

    def test_cr001_02_allows_valid_impression_colors(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["impression_colors"] = {
            "main": "#88C8FF",
            "secondary": "#F8B0D0",
            "accent": "#FFF2A8",
        }

        validate_cr001_record(record)

    def test_cr001_02_rejects_non_list_selected_or_intensity(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["expected_style_genes"]["genre"][
            "selected"
        ] = "cel-shading"

        with self.assertRaisesRegex(CR001ValidationError, "selected"):
            validate_cr001_record(record)

        record = _valid_record()
        record["appeal_point_and_art_style"]["expected_style_genes"]["genre"][
            "intensity"
        ] = "0.9"

        with self.assertRaisesRegex(CR001ValidationError, "intensity"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_empty_or_too_many_selected_alleles(self):
        invalid_selected_values = (
            [],
            [
                "cel-shading",
                "anime-heavy-paint",
                "semi-realistic-anime",
                "flat-illustration",
                "2D-pop-art",
            ],
        )

        for selected in invalid_selected_values:
            with self.subTest(selected=selected):
                record = _valid_record()
                record["appeal_point_and_art_style"]["expected_style_genes"]["genre"] = {
                    "selected": selected,
                    "intensity": [0.9 for _ in selected],
                }

                with self.assertRaisesRegex(CR001ValidationError, "1 to 4"):
                    validate_cr001_record(record)

    def test_cr001_02_rejects_selected_intensity_length_mismatch(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["expected_style_genes"]["genre"] = {
            "selected": ["cel-shading", "anime-heavy-paint"],
            "intensity": [0.9],
        }

        with self.assertRaisesRegex(CR001ValidationError, "length mismatch"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_custom_allele(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["expected_style_genes"]["genre"] = {
            "selected": ["custom-soft-style"],
            "intensity": [0.9],
        }

        with self.assertRaisesRegex(CR001ValidationError, "not in registry"):
            validate_cr001_record(record)

    def test_cr001_02_rejects_non_numeric_or_out_of_range_intensity(self):
        invalid_intensity_values = (True, "0.9", -0.01, 1.01)

        for invalid_intensity in invalid_intensity_values:
            with self.subTest(invalid_intensity=invalid_intensity):
                record = _valid_record()
                record["appeal_point_and_art_style"]["expected_style_genes"]["genre"][
                    "intensity"
                ] = [invalid_intensity]

                with self.assertRaisesRegex(CR001ValidationError, "between 0 and 1"):
                    validate_cr001_record(record)

    def test_cr001_02_rejects_missing_summary(self):
        record = _valid_record()
        record["cr001_summary"] = " "

        with self.assertRaisesRegex(CR001ValidationError, "cr001_summary"):
            validate_cr001_record(record)


if __name__ == "__main__":
    unittest.main()
