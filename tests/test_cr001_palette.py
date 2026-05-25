import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001ValidationError,
    normalize_cr001_impression_colors,
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


class CR001ImpressionColorsValidatorTests(unittest.TestCase):
    def test_cr001_03_accepts_and_preserves_uppercase_hex_colors(self):
        impression_colors = {
            "main": "#88C8FF",
            "secondary": "#F8B0D0",
            "accent": "#FFF2A8",
        }

        self.assertEqual(
            normalize_cr001_impression_colors(impression_colors),
            impression_colors,
        )

    def test_cr001_03_normalizes_lowercase_hex_colors_to_uppercase(self):
        self.assertEqual(
            normalize_cr001_impression_colors(
                {
                    "main": "#88c8ff",
                    "secondary": "#f8b0d0",
                    "accent": "#fff2a8",
                }
            ),
            {
                "main": "#88C8FF",
                "secondary": "#F8B0D0",
                "accent": "#FFF2A8",
            },
        )

    def test_cr001_03_rejects_missing_channel(self):
        with self.assertRaisesRegex(CR001ValidationError, "missing channel"):
            normalize_cr001_impression_colors(
                {
                    "main": "#88C8FF",
                    "secondary": "#F8B0D0",
                }
            )

    def test_cr001_03_rejects_unknown_channel(self):
        with self.assertRaisesRegex(CR001ValidationError, "unknown channel"):
            normalize_cr001_impression_colors(
                {
                    "main": "#88C8FF",
                    "secondary": "#F8B0D0",
                    "accent": "#FFF2A8",
                    "background": "#FFFFFF",
                }
            )

    def test_cr001_03_rejects_invalid_hex_string(self):
        invalid_colors = ("soft-pink", "88C8FF", "#88C8F", "#88C8FFF", "#GGGGGG")

        for invalid_color in invalid_colors:
            with self.subTest(invalid_color=invalid_color):
                with self.assertRaisesRegex(CR001ValidationError, "#RRGGBB"):
                    normalize_cr001_impression_colors(
                        {
                            "main": invalid_color,
                            "secondary": "#F8B0D0",
                            "accent": "#FFF2A8",
                        }
                    )

    def test_cr001_03_rejects_non_string_value(self):
        with self.assertRaisesRegex(CR001ValidationError, "must be a string"):
            normalize_cr001_impression_colors(
                {
                    "main": "#88C8FF",
                    "secondary": 123,
                    "accent": "#FFF2A8",
                }
            )

    def test_cr001_03_record_validator_validates_optional_impression_colors_when_present(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["impression_colors"]["accent"] = "gold"

        with self.assertRaisesRegex(CR001ValidationError, "#RRGGBB"):
            validate_cr001_record(record)


if __name__ == "__main__":
    unittest.main()
