import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001ValidationError,
    build_cr001_native_artifact_document,
    validate_cr001_native_artifact_document,
    write_cr001_native_artifact_document,
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


class CR001NativeArtifactWriterTests(unittest.TestCase):
    def test_cr001_05b_writes_native_artifact_to_stable_phase0_path(self):
        artifact = build_cr001_native_artifact_document([_valid_record()])

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "run-001"

            output_path = write_cr001_native_artifact_document(
                run_dir=run_dir,
                artifact_document=artifact,
            )
            written_document = json.loads(
                (run_dir / output_path).read_text(encoding="utf-8")
            )

        self.assertEqual(output_path, "phase0/cr001_reference_image_analysis.json")
        self.assertEqual(written_document, artifact)

    def test_cr001_05b_writes_deterministic_pretty_json_with_trailing_newline(self):
        artifact = build_cr001_native_artifact_document([_valid_record()])

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)

            output_path = write_cr001_native_artifact_document(
                run_dir=run_dir,
                artifact_document=artifact,
            )
            output_text = (run_dir / output_path).read_text(encoding="utf-8")

        self.assertTrue(output_text.endswith("\n"))
        self.assertIn('  "schema_version": "cr001.v1"', output_text)
        self.assertIn('  "records": [', output_text)

    def test_cr001_05b_rejects_invalid_artifact_before_writing(self):
        artifact = build_cr001_native_artifact_document([_valid_record()])
        artifact["schema_version"] = "cr001.v2"

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)

            with self.assertRaisesRegex(CR001ValidationError, "schema_version"):
                write_cr001_native_artifact_document(
                    run_dir=run_dir,
                    artifact_document=artifact,
                )

            self.assertFalse((run_dir / "phase0").exists())

    def test_cr001_05b_does_not_overwrite_style_gene_pool(self):
        artifact = build_cr001_native_artifact_document([_valid_record()])

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            gene_pool_path = run_dir / "style_gene_pool.json"
            original_gene_pool = '{"version":"0.1.0","genes":{"rendering":[]}}\n'
            gene_pool_path.write_text(original_gene_pool, encoding="utf-8")

            write_cr001_native_artifact_document(
                run_dir=run_dir,
                artifact_document=artifact,
            )

            gene_pool_after_write = gene_pool_path.read_text(encoding="utf-8")

        self.assertEqual(gene_pool_after_write, original_gene_pool)

    def test_cr001_05b_validator_rejects_projection_artifact_shape(self):
        projection_document = {
            "version": "0.1.0",
            "source": "phase0_reference_image_analysis",
            "aspects": {},
        }

        with self.assertRaisesRegex(CR001ValidationError, "schema_version"):
            validate_cr001_native_artifact_document(projection_document)


if __name__ == "__main__":
    unittest.main()
