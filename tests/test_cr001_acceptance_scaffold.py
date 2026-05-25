import json
from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"

EXPECTED_STYLE_LOCI = (
    "genre",
    "line_art",
    "brush_shading",
    "saturation",
    "lighting",
    "texture",
)
CHARACTER_APPEAL_LOCI = (
    "facial_features",
    "body_type",
    "clothing_genre",
    "clothing_fit",
)
IMPRESSION_COLOR_CHANNELS = ("main", "secondary", "accent")
UPPERCASE_HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")


def _load_fixture(name):
    return json.loads((CR001_FIXTURE_DIR / name).read_text(encoding="utf-8"))


class CR001AcceptanceScaffoldTests(unittest.TestCase):
    def test_cr001_v1_native_artifact_fixture_defines_container_contract(self):
        document = _load_fixture("cr001_native_artifact_v1.json")

        self.assertEqual(tuple(document), ("schema_version", "source", "records"))
        self.assertEqual(document["schema_version"], "cr001.v1")
        self.assertEqual(document["source"], "cr001_reference_image_analysis")
        self.assertEqual(len(document["records"]), 1)

    def test_cr001_v1_record_fixture_preserves_required_gene_groups(self):
        document = _load_fixture("cr001_native_artifact_v1.json")
        record = document["records"][0]
        payload = record["appeal_point_and_art_style"]

        self.assertEqual(record["source_image"], "reference_images/ref-001.png")
        self.assertTrue(record["cr001_summary"].strip())
        self.assertEqual(
            tuple(payload["expected_style_genes"]),
            EXPECTED_STYLE_LOCI,
        )
        self.assertEqual(
            tuple(payload["character_appeal_genes"]),
            CHARACTER_APPEAL_LOCI,
        )

        for loci_group in (
            payload["expected_style_genes"],
            payload["character_appeal_genes"],
        ):
            for locus_payload in loci_group.values():
                self.assertEqual(tuple(locus_payload), ("selected", "intensity"))
                self.assertEqual(len(locus_payload["selected"]), len(locus_payload["intensity"]))

    def test_cr001_v1_fixture_keeps_impression_colors_as_uppercase_palette_auxiliary(self):
        document = _load_fixture("cr001_native_artifact_v1.json")
        impression_colors = document["records"][0]["appeal_point_and_art_style"][
            "impression_colors"
        ]

        self.assertEqual(tuple(impression_colors), IMPRESSION_COLOR_CHANNELS)
        for color in impression_colors.values():
            self.assertRegex(color, UPPERCASE_HEX_COLOR)


if __name__ == "__main__":
    unittest.main()
