import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001_ALLELE_REGISTRY,
    CR001_CANONICAL_LOCI,
    CR001_CHARACTER_APPEAL_LOCI,
    CR001_EXPECTED_STYLE_LOCI,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


class CR001AlleleRegistryTests(unittest.TestCase):
    def test_cr001_01_registry_declares_canonical_v1_loci_in_order(self):
        self.assertEqual(
            CR001_EXPECTED_STYLE_LOCI,
            (
                "genre",
                "line_art",
                "brush_shading",
                "saturation",
                "lighting",
                "texture",
            ),
        )
        self.assertEqual(
            CR001_CHARACTER_APPEAL_LOCI,
            (
                "facial_features",
                "body_type",
                "clothing_genre",
                "clothing_fit",
            ),
        )
        self.assertEqual(
            tuple(CR001_ALLELE_REGISTRY),
            CR001_CANONICAL_LOCI,
        )

    def test_cr001_01_registry_contains_specified_alleles(self):
        self.assertEqual(
            CR001_ALLELE_REGISTRY["genre"],
            (
                "cel-shading",
                "anime-heavy-paint",
                "semi-realistic-anime",
                "flat-illustration",
                "2D-pop-art",
                "vintage-manga",
                "watercolor-anime",
                "oil-painterly",
            ),
        )
        self.assertIn("morandi-palette", CR001_ALLELE_REGISTRY["saturation"])
        self.assertIn("large-expressive-eyes", CR001_ALLELE_REGISTRY["facial_features"])
        self.assertIn("japanese-school-uniform", CR001_ALLELE_REGISTRY["clothing_genre"])

    def test_cr001_01_registry_excludes_palette_auxiliary_output(self):
        self.assertNotIn("impression_colors", CR001_ALLELE_REGISTRY)

    def test_cr001_01_fixture_selected_alleles_are_registry_members(self):
        document = json.loads(
            (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
                encoding="utf-8"
            )
        )
        payload = document["records"][0]["appeal_point_and_art_style"]

        for group_name in ("expected_style_genes", "character_appeal_genes"):
            for locus, locus_payload in payload[group_name].items():
                self.assertIn(locus, CR001_ALLELE_REGISTRY)
                for allele in locus_payload["selected"]:
                    self.assertIn(allele, CR001_ALLELE_REGISTRY[locus])

    def test_cr001_01_registry_rejects_unknown_locus_and_custom_allele_by_lookup(self):
        self.assertNotIn("composition", CR001_ALLELE_REGISTRY)
        self.assertNotIn("custom-soft-style", CR001_ALLELE_REGISTRY["genre"])


if __name__ == "__main__":
    unittest.main()
