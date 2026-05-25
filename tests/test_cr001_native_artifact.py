import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001ValidationError,
    build_cr001_native_artifact_document,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


def _valid_record():
    document = json.loads(
        (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return copy.deepcopy(document["records"][0])


class CR001NativeArtifactBuilderTests(unittest.TestCase):
    def test_cr001_05a_builds_native_artifact_container_contract(self):
        record = _valid_record()

        artifact = build_cr001_native_artifact_document([record])

        self.assertEqual(tuple(artifact), ("schema_version", "source", "records"))
        self.assertEqual(artifact["schema_version"], "cr001.v1")
        self.assertEqual(artifact["source"], "cr001_reference_image_analysis")
        self.assertEqual(artifact["records"], [record])

    def test_cr001_05a_normalizes_record_palette_in_artifact_copy(self):
        record = _valid_record()
        record["appeal_point_and_art_style"]["impression_colors"] = {
            "main": "#88c8ff",
            "secondary": "#f8b0d0",
            "accent": "#fff2a8",
        }

        artifact = build_cr001_native_artifact_document([record])

        self.assertEqual(
            artifact["records"][0]["appeal_point_and_art_style"]["impression_colors"],
            {
                "main": "#88C8FF",
                "secondary": "#F8B0D0",
                "accent": "#FFF2A8",
            },
        )
        self.assertEqual(
            record["appeal_point_and_art_style"]["impression_colors"]["main"],
            "#88c8ff",
        )

    def test_cr001_05a_rejects_missing_source_image_linkage(self):
        record = _valid_record()
        del record["source_image"]

        with self.assertRaisesRegex(CR001ValidationError, "source_image"):
            build_cr001_native_artifact_document([record])

    def test_cr001_05a_rejects_invalid_source_image_linkage(self):
        record = _valid_record()
        record["source_image"] = "C:\\reference_images\\ref-001.png"

        with self.assertRaisesRegex(CR001ValidationError, "source_image"):
            build_cr001_native_artifact_document([record])

    def test_cr001_05a_rejects_invalid_record_schema(self):
        record = _valid_record()
        del record["appeal_point_and_art_style"]["character_appeal_genes"]

        with self.assertRaisesRegex(CR001ValidationError, "character_appeal_genes"):
            build_cr001_native_artifact_document([record])

    def test_cr001_05a_does_not_include_phase0_projection_fields(self):
        artifact = build_cr001_native_artifact_document([_valid_record()])

        self.assertNotIn("aspects", artifact)
        self.assertNotIn("style_gene_candidates", artifact)
        self.assertNotIn("style_gene_pool", artifact)


if __name__ == "__main__":
    unittest.main()
