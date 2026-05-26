from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.config import (  # noqa: E402
    ALLOWED_REFERENCE_IMAGE_ASPECTS,
    ConfigValidationError,
    ProviderRetryPolicy,
    ReferenceImageAnalysisPolicy,
)


class ReferenceImageAnalysisPolicyTests(unittest.TestCase):
    def test_default_policy_matches_phase0_disabled_spec(self):
        policy = ReferenceImageAnalysisPolicy()

        self.assertFalse(policy.enabled)
        self.assertEqual(policy.input_dir, "reference_images")
        self.assertEqual(policy.output_file, "style_gene_candidates.json")
        self.assertEqual(policy.aspects, ALLOWED_REFERENCE_IMAGE_ASPECTS)
        self.assertEqual(policy.provider_retry_policy, ProviderRetryPolicy())

    def test_from_mapping_accepts_spec_fields(self):
        policy = ReferenceImageAnalysisPolicy.from_mapping(
            {
                "enabled": True,
                "input_dir": "my_reference_images",
                "output_file": "phase0_candidates.json",
                "aspects": ["rendering", "color_light", "texture_artifacts"],
                "provider_retry_policy": {
                    "max_attempts": 4,
                    "delay_retry_enabled": True,
                    "delay_retry_times": 3,
                    "retry_buffer_seconds": 1.5,
                    "default_initial_backoff_seconds": 7,
                    "max_single_delay_seconds": 30,
                    "max_total_delay_seconds": 90,
                    "jitter_enabled": False,
                },
            }
        )

        self.assertTrue(policy.enabled)
        self.assertEqual(policy.input_dir, "my_reference_images")
        self.assertEqual(policy.output_file, "phase0_candidates.json")
        self.assertEqual(
            policy.aspects,
            ("rendering", "color_light", "texture_artifacts"),
        )
        self.assertEqual(
            policy.provider_retry_policy,
            ProviderRetryPolicy(
                max_attempts=4,
                delay_retry_enabled=True,
                delay_retry_times=3,
                retry_buffer_seconds=1.5,
                default_initial_backoff_seconds=7,
                max_single_delay_seconds=30,
                max_total_delay_seconds=90,
                jitter_enabled=False,
            ),
        )

    def test_from_mapping_uses_defaults_for_missing_policy(self):
        policy = ReferenceImageAnalysisPolicy.from_mapping(None)

        self.assertFalse(policy.enabled)
        self.assertEqual(policy.aspects, ALLOWED_REFERENCE_IMAGE_ASPECTS)
        self.assertEqual(policy.provider_retry_policy, ProviderRetryPolicy())

    def test_exp_001_fu_01b_provider_retry_policy_uses_spec_defaults(self):
        policy = ProviderRetryPolicy()

        self.assertEqual(policy.max_attempts, 3)
        self.assertFalse(policy.delay_retry_enabled)
        self.assertEqual(policy.delay_retry_times, 2)
        self.assertEqual(policy.retry_buffer_seconds, 2)
        self.assertEqual(policy.default_initial_backoff_seconds, 5)
        self.assertEqual(policy.max_single_delay_seconds, 60)
        self.assertEqual(policy.max_total_delay_seconds, 120)
        self.assertTrue(policy.jitter_enabled)

    def test_exp_001_fu_01b_provider_retry_policy_caps_delay_retry_times(self):
        policy = ProviderRetryPolicy(max_attempts=2, delay_retry_times=5)

        self.assertEqual(policy.max_attempts, 2)
        self.assertEqual(policy.delay_retry_times, 1)

    def test_exp_001_fu_01b_rejects_invalid_provider_retry_policy_values(self):
        invalid_values = (
            {"max_attempts": 0},
            {"max_attempts": True},
            {"delay_retry_enabled": "yes"},
            {"delay_retry_times": -1},
            {"delay_retry_times": 1.5},
            {"retry_buffer_seconds": -1},
            {"default_initial_backoff_seconds": 0},
            {"max_single_delay_seconds": 0},
            {"max_total_delay_seconds": 0},
            {"jitter_enabled": 1},
        )

        for provider_retry_policy in invalid_values:
            with self.subTest(provider_retry_policy=provider_retry_policy):
                with self.assertRaises(ConfigValidationError):
                    ProviderRetryPolicy.from_mapping(provider_retry_policy)

    def test_exp_001_fu_01b_rejects_unknown_provider_retry_policy_field(self):
        with self.assertRaisesRegex(ConfigValidationError, "unknown field"):
            ProviderRetryPolicy.from_mapping({"backoff": 1})

    def test_exp_001_fu_01b_rejects_non_object_provider_retry_policy(self):
        with self.assertRaisesRegex(ConfigValidationError, "must be an object"):
            ProviderRetryPolicy.from_mapping(["not", "an", "object"])

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
