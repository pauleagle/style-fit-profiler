from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.config import (  # noqa: E402
    ALLOWED_REFERENCE_IMAGE_ASPECTS,
    ConfigValidationError,
    ReferenceImageAnalysisPolicy,
)


class ReferenceImageAnalysisPolicyTests(unittest.TestCase):
    def test_default_policy_matches_phase0_disabled_spec(self):
        policy = ReferenceImageAnalysisPolicy()

        self.assertFalse(policy.enabled)
        self.assertEqual(policy.input_dir, "reference_images")
        self.assertEqual(policy.output_file, "style_gene_candidates.json")
        self.assertEqual(policy.aspects, ALLOWED_REFERENCE_IMAGE_ASPECTS)

    def test_from_mapping_accepts_spec_fields(self):
        policy = ReferenceImageAnalysisPolicy.from_mapping(
            {
                "enabled": True,
                "input_dir": "my_reference_images",
                "output_file": "phase0_candidates.json",
                "aspects": ["rendering", "color_light", "texture_artifacts"],
            }
        )

        self.assertTrue(policy.enabled)
        self.assertEqual(policy.input_dir, "my_reference_images")
        self.assertEqual(policy.output_file, "phase0_candidates.json")
        self.assertEqual(
            policy.aspects,
            ("rendering", "color_light", "texture_artifacts"),
        )

    def test_from_mapping_uses_defaults_for_missing_policy(self):
        policy = ReferenceImageAnalysisPolicy.from_mapping(None)

        self.assertFalse(policy.enabled)
        self.assertEqual(policy.aspects, ALLOWED_REFERENCE_IMAGE_ASPECTS)

    def test_rejects_non_object_policy(self):
        with self.assertRaisesRegex(ConfigValidationError, "must be an object"):
            ReferenceImageAnalysisPolicy.from_mapping(["not", "an", "object"])

    def test_rejects_non_list_aspects(self):
        with self.assertRaisesRegex(ConfigValidationError, "aspects"):
            ReferenceImageAnalysisPolicy.from_mapping({"aspects": 42})

        with self.assertRaisesRegex(ConfigValidationError, "aspects"):
            ReferenceImageAnalysisPolicy.from_mapping({"aspects": "rendering"})

    def test_rejects_empty_aspects(self):
        with self.assertRaisesRegex(ConfigValidationError, "at least one aspect"):
            ReferenceImageAnalysisPolicy.from_mapping({"aspects": []})

    def test_rejects_unknown_policy_field(self):
        with self.assertRaisesRegex(ConfigValidationError, "unknown field"):
            ReferenceImageAnalysisPolicy.from_mapping({"enable": True})

    def test_rejects_unknown_aspect(self):
        with self.assertRaisesRegex(ConfigValidationError, "unsupported aspect"):
            ReferenceImageAnalysisPolicy.from_mapping(
                {
                    "aspects": ["rendering", "composition"],
                }
            )

    def test_rejects_duplicate_aspect(self):
        with self.assertRaisesRegex(ConfigValidationError, "duplicate aspect"):
            ReferenceImageAnalysisPolicy.from_mapping(
                {
                    "aspects": ["rendering", "rendering"],
                }
            )

    def test_rejects_non_boolean_enabled(self):
        with self.assertRaisesRegex(ConfigValidationError, "enabled"):
            ReferenceImageAnalysisPolicy.from_mapping({"enabled": "yes"})

    def test_rejects_blank_paths(self):
        with self.assertRaisesRegex(ConfigValidationError, "input_dir"):
            ReferenceImageAnalysisPolicy.from_mapping({"input_dir": " "})

        with self.assertRaisesRegex(ConfigValidationError, "output_file"):
            ReferenceImageAnalysisPolicy.from_mapping({"output_file": ""})


if __name__ == "__main__":
    unittest.main()
