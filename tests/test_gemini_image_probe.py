from pathlib import Path
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.gemini_image_probe import (  # noqa: E402
    CR001_IMAGE_BACKEND,
    DEFAULT_ANALYSIS_PROMPT,
    DEFAULT_BATCH_ANALYSIS_PROMPT,
    DEFAULT_IMAGE_BACKEND,
    DEFAULT_IMAGE_RUN_DIR,
    GEMINI_TRAIT_ASPECTS,
    GeminiImageAnalysisClient,
    GeminiImageProbeError,
    GeminiPhase0Extractor,
    build_batch_generate_content_payload,
    build_generate_content_payload,
    classify_gemini_provider_error,
    extract_gemini_retry_after_seconds,
    extract_response_text,
    guess_image_mime_type,
    main,
    map_gemini_traits_to_candidates,
    parse_args,
    parse_gemini_batch_trait_response,
    parse_gemini_trait_response,
    resolve_provider_retry_decision,
    sleep_for_provider_retry_delay,
)
from style_fit_profiler.config import (  # noqa: E402
    ProviderRetryPolicy,
    ReferenceImageAnalysisPolicy,
)
from style_fit_profiler.phase0 import (  # noqa: E402
    build_style_gene_candidates_document,
    run_phase0,
    validate_style_gene_candidate_aspects,
    validate_style_gene_candidates_document,
)


CR001_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "cr001"


def _png_header_bytes(*, width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def _valid_cr001_raw_response(*, source_image="reference_images/ref-001.png"):
    document = json.loads(
        (CR001_FIXTURE_DIR / "cr001_native_artifact_v1.json").read_text(
            encoding="utf-8"
        )
    )
    record = copy.deepcopy(document["records"][0])
    record["source_image"] = source_image
    return json.dumps(
        {
            "appeal_point_and_art_style": record["appeal_point_and_art_style"],
            "cr001_summary": record["cr001_summary"],
        }
    )


class GeminiImageProbeTests(unittest.TestCase):
    def test_build_payload_includes_inline_image_and_phase0_prompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"fake-png-bytes")

            payload = build_generate_content_payload(image_path=image_path)

        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(parts[0]["inline_data"]["data"], "ZmFrZS1wbmctYnl0ZXM=")
        self.assertIn("rendering", parts[1]["text"])
        self.assertIn("color_light", parts[1]["text"])
        self.assertIn("texture_artifacts", parts[1]["text"])
        self.assertEqual(payload["generationConfig"]["response_mime_type"], "application/json")

    def test_build_batch_payload_includes_all_images_and_source_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_image_path = Path(temp_dir) / "a.png"
            second_image_path = Path(temp_dir) / "b.png"
            first_image_path.write_bytes(b"fake-png-a")
            second_image_path.write_bytes(b"fake-png-b")

            payload = build_batch_generate_content_payload(
                image_paths=(first_image_path, second_image_path),
                source_images=(
                    "reference_images/a.png",
                    "reference_images/b.png",
                ),
            )

        parts = payload["contents"][0]["parts"]
        self.assertIn("Analyze each local reference image", parts[0]["text"])
        self.assertIn("reference_images/a.png", parts[0]["text"])
        self.assertIn("reference_images/b.png", parts[0]["text"])
        self.assertEqual(parts[1], {"text": "Image path: reference_images/a.png"})
        self.assertEqual(parts[2]["inline_data"]["data"], "ZmFrZS1wbmctYQ==")
        self.assertEqual(parts[3], {"text": "Image path: reference_images/b.png"})
        self.assertEqual(parts[4]["inline_data"]["data"], "ZmFrZS1wbmctYg==")
        self.assertEqual(payload["generationConfig"]["response_mime_type"], "application/json")

    def test_guess_image_mime_type_rejects_non_image_extension(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "MIME"):
            guess_image_mime_type(Path("notes.txt"))

    def test_extract_response_text_returns_first_text_part(self):
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"rendering":[],"color_light":[],"texture_artifacts":[],"notes":""}'
                            }
                        ]
                    }
                }
            ]
        }

        self.assertEqual(
            extract_response_text(response),
            '{"rendering":[],"color_light":[],"texture_artifacts":[],"notes":""}',
        )

    def test_default_prompt_mentions_no_artist_or_character_name_rule(self):
        self.assertIn("Do not invent artist names", DEFAULT_ANALYSIS_PROMPT)
        self.assertIn("Analyze each local reference image", DEFAULT_BATCH_ANALYSIS_PROMPT)


class GeminiProviderErrorClassificationTests(unittest.TestCase):
    def test_exp_001_fu_01a_classifies_resource_exhausted_with_retry_delay(self):
        provider_error = classify_gemini_provider_error(
            {
                "error": {
                    "code": 429,
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded. Please retry in 49.272417405s.",
                }
            }
        )

        self.assertEqual(provider_error.type, "provider_quota_exhausted")
        self.assertEqual(provider_error.provider_status, "RESOURCE_EXHAUSTED")
        self.assertTrue(provider_error.retryable)
        self.assertEqual(provider_error.provider_http_status, 429)
        self.assertAlmostEqual(provider_error.retry_after_seconds, 49.272417405)

    def test_exp_001_fu_01a_classifies_retryable_transient_statuses(self):
        cases = {
            "UNAVAILABLE": "provider_unavailable",
            "INTERNAL": "provider_internal_error",
            "DEADLINE_EXCEEDED": "provider_timeout",
        }

        for status, expected_type in cases.items():
            with self.subTest(status=status):
                provider_error = classify_gemini_provider_error(
                    {"error": {"status": status, "message": "temporary provider error"}}
                )

                self.assertEqual(provider_error.type, expected_type)
                self.assertEqual(provider_error.provider_status, status)
                self.assertTrue(provider_error.retryable)

    def test_exp_001_fu_01a_classifies_non_retryable_provider_statuses(self):
        cases = {
            "INVALID_ARGUMENT": "invalid_request",
            "UNAUTHENTICATED": "auth_error",
            "PERMISSION_DENIED": "permission_error",
            "SOMETHING_NEW": "unknown_provider_error",
        }

        for status, expected_type in cases.items():
            with self.subTest(status=status):
                provider_error = classify_gemini_provider_error(
                    {"error": {"status": status, "message": "provider rejected request"}}
                )

                self.assertEqual(provider_error.type, expected_type)
                self.assertEqual(provider_error.provider_status, status)
                self.assertFalse(provider_error.retryable)

    def test_exp_001_fu_01a_extracts_retry_delay_from_stringified_http_error(self):
        provider_error = classify_gemini_provider_error(
            GeminiImageProbeError(
                'Gemini API HTTP 429: {"error":{"status":"RESOURCE_EXHAUSTED",'
                '"message":"Please retry in 5s."}}'
            )
        )

        self.assertEqual(provider_error.type, "provider_quota_exhausted")
        self.assertTrue(provider_error.retryable)
        self.assertEqual(provider_error.retry_after_seconds, 5.0)

    def test_exp_001_fu_01a_retry_delay_parser_returns_none_without_delay(self):
        self.assertIsNone(extract_gemini_retry_after_seconds("Quota exceeded."))
        self.assertIsNone(extract_gemini_retry_after_seconds(""))


class ProviderRetryDecisionTests(unittest.TestCase):
    def test_exp_001_fu_01c_retries_retryable_error_with_remaining_attempts(self):
        provider_error = classify_gemini_provider_error(
            {"error": {"status": "UNAVAILABLE", "message": "temporary outage"}}
        )

        decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(max_attempts=3),
            attempt_index=1,
        )

        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.remaining_attempts, 2)
        self.assertIsNone(decision.wait_seconds)
        self.assertEqual(decision.total_delay_after_wait_seconds, 0)

    def test_exp_001_fu_01c_does_not_retry_non_retryable_or_exhausted_errors(self):
        non_retryable_error = classify_gemini_provider_error(
            {"error": {"status": "INVALID_ARGUMENT", "message": "bad payload"}}
        )
        retryable_error = classify_gemini_provider_error(
            {"error": {"status": "UNAVAILABLE", "message": "temporary outage"}}
        )

        self.assertFalse(
            resolve_provider_retry_decision(
                provider_error=non_retryable_error,
                policy=ProviderRetryPolicy(max_attempts=3),
                attempt_index=1,
            ).should_retry
        )
        self.assertFalse(
            resolve_provider_retry_decision(
                provider_error=retryable_error,
                policy=ProviderRetryPolicy(max_attempts=3),
                attempt_index=3,
            ).should_retry
        )

    def test_exp_001_fu_01c_uses_bounded_provider_delay_when_enabled(self):
        provider_error = classify_gemini_provider_error(
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded. Please retry in 49.272417405s.",
                }
            }
        )

        decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(
                max_attempts=3,
                delay_retry_enabled=True,
                retry_buffer_seconds=2,
                max_single_delay_seconds=60,
                max_total_delay_seconds=120,
            ),
            attempt_index=1,
        )

        self.assertTrue(decision.should_retry)
        self.assertAlmostEqual(decision.wait_seconds, 51.272417405)
        self.assertAlmostEqual(decision.total_delay_after_wait_seconds, 51.272417405)

    def test_exp_001_fu_01c_caps_single_and_total_delay(self):
        provider_error = classify_gemini_provider_error(
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded. Please retry in 49.272417405s.",
                }
            }
        )

        single_cap_decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(
                delay_retry_enabled=True,
                max_single_delay_seconds=20,
                max_total_delay_seconds=120,
            ),
            attempt_index=1,
        )
        total_cap_decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(
                delay_retry_enabled=True,
                max_single_delay_seconds=60,
                max_total_delay_seconds=55,
            ),
            attempt_index=1,
            total_delay_seconds=40,
        )

        self.assertEqual(single_cap_decision.wait_seconds, 20)
        self.assertEqual(total_cap_decision.wait_seconds, 15)
        self.assertEqual(total_cap_decision.total_delay_after_wait_seconds, 55)

    def test_exp_001_fu_01c_uses_default_backoff_without_provider_delay(self):
        provider_error = classify_gemini_provider_error(
            {"error": {"status": "UNAVAILABLE", "message": "temporary outage"}}
        )

        decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(
                delay_retry_enabled=True,
                default_initial_backoff_seconds=5,
                retry_buffer_seconds=2,
            ),
            attempt_index=1,
        )

        self.assertEqual(decision.wait_seconds, 7)

    def test_exp_001_fu_01c_respects_delay_retry_budget_without_blocking_retry(self):
        provider_error = classify_gemini_provider_error(
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded. Please retry in 5s.",
                }
            }
        )

        decision = resolve_provider_retry_decision(
            provider_error=provider_error,
            policy=ProviderRetryPolicy(
                max_attempts=3,
                delay_retry_enabled=True,
                delay_retry_times=1,
            ),
            attempt_index=1,
            delay_retry_count=1,
        )

        self.assertTrue(decision.should_retry)
        self.assertIsNone(decision.wait_seconds)

    def test_exp_001_fu_01c_uses_injected_sleeper_only_when_waiting(self):
        calls = []
        delayed_decision = resolve_provider_retry_decision(
            provider_error=classify_gemini_provider_error(
                {"error": {"status": "UNAVAILABLE", "message": "temporary outage"}}
            ),
            policy=ProviderRetryPolicy(delay_retry_enabled=True),
            attempt_index=1,
        )
        immediate_decision = resolve_provider_retry_decision(
            provider_error=classify_gemini_provider_error(
                {"error": {"status": "UNAVAILABLE", "message": "temporary outage"}}
            ),
            policy=ProviderRetryPolicy(delay_retry_enabled=False),
            attempt_index=1,
        )

        sleep_for_provider_retry_delay(delayed_decision, sleeper=calls.append)
        sleep_for_provider_retry_delay(immediate_decision, sleeper=calls.append)

        self.assertEqual(calls, [7])


class GeminiTraitResponseParserTests(unittest.TestCase):
    def test_exp_001a_parses_valid_trait_response(self):
        traits = parse_gemini_trait_response(
            """
            {
              "rendering": ["anime art style", " clean lines "],
              "color_light": ["vibrant colors"],
              "texture_artifacts": [],
              "notes": "brief summary"
            }
            """
        )

        self.assertEqual(tuple(traits), GEMINI_TRAIT_ASPECTS)
        self.assertEqual(traits["rendering"], ("anime art style", "clean lines"))
        self.assertEqual(traits["color_light"], ("vibrant colors",))
        self.assertEqual(traits["texture_artifacts"], ())

    def test_exp_001a_rejects_invalid_json(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "invalid Gemini trait JSON"):
            parse_gemini_trait_response("{not json")

    def test_exp_001a_rejects_missing_aspect(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "missing aspect"):
            parse_gemini_trait_response(
                """
                {
                  "rendering": [],
                  "color_light": [],
                  "notes": ""
                }
                """
            )

    def test_exp_001a_rejects_unknown_top_level_key(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "unknown key"):
            parse_gemini_trait_response(
                """
                {
                  "rendering": [],
                  "color_light": [],
                  "texture_artifacts": [],
                  "composition": []
                }
                """
            )

    def test_exp_001a_rejects_non_list_traits(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "must be a list"):
            parse_gemini_trait_response(
                """
                {
                  "rendering": "anime",
                  "color_light": [],
                  "texture_artifacts": []
                }
                """
            )

    def test_exp_001a_rejects_blank_or_non_string_trait(self):
        invalid_trait_responses = (
            """
            {
              "rendering": [" "],
              "color_light": [],
              "texture_artifacts": []
            }
            """,
            """
            {
              "rendering": [42],
              "color_light": [],
              "texture_artifacts": []
            }
            """,
        )

        for response_text in invalid_trait_responses:
            with self.subTest(response_text=response_text):
                with self.assertRaisesRegex(GeminiImageProbeError, "trait"):
                    parse_gemini_trait_response(response_text)

    def test_exp_001a_rejects_non_string_notes(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "notes"):
            parse_gemini_trait_response(
                """
                {
                  "rendering": [],
                  "color_light": [],
                  "texture_artifacts": [],
                  "notes": ["not", "a", "string"]
                }
                """
            )

    def test_exp_001f_parses_batch_trait_response_per_source_image(self):
        analyses = parse_gemini_batch_trait_response(
            """
            {
              "images": [
                {
                  "path": "reference_images/a.png",
                  "rendering": [" clean linework "],
                  "color_light": ["soft warm light"],
                  "texture_artifacts": [],
                  "notes": "first"
                },
                {
                  "path": "reference_images/b.png",
                  "rendering": ["painterly finish"],
                  "color_light": [],
                  "texture_artifacts": ["subtle grain"],
                  "notes": "second"
                }
              ]
            }
            """,
            expected_source_images=(
                "reference_images/a.png",
                "reference_images/b.png",
            ),
        )

        self.assertEqual(
            [analysis.source_image for analysis in analyses],
            ["reference_images/a.png", "reference_images/b.png"],
        )
        self.assertEqual(tuple(analyses[0].traits_by_aspect), GEMINI_TRAIT_ASPECTS)
        self.assertEqual(analyses[0].traits_by_aspect["rendering"], ("clean linework",))
        self.assertEqual(analyses[1].traits_by_aspect["texture_artifacts"], ("subtle grain",))
        self.assertEqual(analyses[1].notes, "second")

    def test_exp_001f_rejects_batch_trait_response_missing_expected_image(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "missing image"):
            parse_gemini_batch_trait_response(
                """
                {
                  "images": [
                    {
                      "path": "reference_images/a.png",
                      "rendering": [],
                      "color_light": [],
                      "texture_artifacts": [],
                      "notes": ""
                    }
                  ]
                }
                """,
                expected_source_images=(
                    "reference_images/a.png",
                    "reference_images/b.png",
                ),
            )


class GeminiTraitCandidateMapperTests(unittest.TestCase):
    def test_exp_001b_maps_traits_to_schema_valid_candidates(self):
        candidates_by_aspect = map_gemini_traits_to_candidates(
            traits_by_aspect={
                "rendering": ("anime art style", "clean lines"),
                "color_light": ("vibrant colors",),
                "texture_artifacts": (),
            },
            source_image="reference_images/ref-001.png",
            model="gemini-test-model",
        )

        validate_style_gene_candidate_aspects(candidates_by_aspect)
        candidate_document = build_style_gene_candidates_document(
            candidates_by_aspect=candidates_by_aspect
        )
        validate_style_gene_candidates_document(candidate_document)

        self.assertEqual(tuple(candidates_by_aspect), GEMINI_TRAIT_ASPECTS)
        first_candidate = candidates_by_aspect["rendering"][0]
        self.assertRegex(first_candidate.id, r"^rendering_anime_art_style_[a-f0-9]{8}$")
        self.assertEqual(first_candidate.prompt, "anime art style")
        self.assertEqual(first_candidate.confidence, 0.5)
        self.assertEqual(first_candidate.source_images, ("reference_images/ref-001.png",))
        self.assertIn("gemini experimental extractor", first_candidate.notes)
        self.assertIn("gemini-test-model", first_candidate.notes)
        self.assertEqual(candidates_by_aspect["texture_artifacts"], ())

    def test_exp_001b_candidate_ids_are_stable(self):
        traits_by_aspect = {
            "rendering": ("anime art style",),
            "color_light": (),
            "texture_artifacts": (),
        }

        first_candidates = map_gemini_traits_to_candidates(
            traits_by_aspect=traits_by_aspect,
            source_image="reference_images/ref-001.png",
        )
        second_candidates = map_gemini_traits_to_candidates(
            traits_by_aspect=traits_by_aspect,
            source_image="reference_images/ref-001.png",
        )

        digest = hashlib.sha256(
            b"rendering\x00anime art style\x00reference_images/ref-001.png"
        ).hexdigest()[:8]
        self.assertEqual(first_candidates, second_candidates)
        self.assertEqual(
            first_candidates["rendering"][0].id,
            f"rendering_anime_art_style_{digest}",
        )

    def test_exp_001b_deduplicates_duplicate_traits_by_candidate_id(self):
        candidates_by_aspect = map_gemini_traits_to_candidates(
            traits_by_aspect={
                "rendering": (" clean lines ", "clean lines"),
                "color_light": (),
                "texture_artifacts": (),
            },
            source_image="reference_images/ref-001.png",
        )

        self.assertEqual(len(candidates_by_aspect["rendering"]), 1)
        self.assertEqual(candidates_by_aspect["rendering"][0].prompt, "clean lines")

    def test_exp_001b_rejects_missing_or_unknown_aspect(self):
        with self.assertRaisesRegex(GeminiImageProbeError, "missing aspect"):
            map_gemini_traits_to_candidates(
                traits_by_aspect={
                    "rendering": (),
                    "color_light": (),
                },
                source_image="reference_images/ref-001.png",
            )

        with self.assertRaisesRegex(GeminiImageProbeError, "unknown aspect"):
            map_gemini_traits_to_candidates(
                traits_by_aspect={
                    "rendering": (),
                    "color_light": (),
                    "texture_artifacts": (),
                    "composition": (),
                },
                source_image="reference_images/ref-001.png",
            )


class GeminiImageAnalysisClientTests(unittest.TestCase):
    def test_exp_001c_client_uses_injected_payload_builder_and_transport(self):
        calls = []

        def payload_builder(*, image_path, prompt):
            calls.append(("payload_builder", image_path, prompt))
            return {"request": "payload"}

        def generate_content(*, api_key, payload, model, timeout_seconds):
            calls.append(("generate_content", api_key, payload, model, timeout_seconds))
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"rendering":[],"color_light":[],'
                                        '"texture_artifacts":[],"notes":""}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

        client = GeminiImageAnalysisClient(
            api_key="test-api-key",
            model="gemini-test-model",
            prompt="custom prompt",
            timeout_seconds=7,
            payload_builder=payload_builder,
            generate_content=generate_content,
        )

        response_text = client.analyze_image(Path("reference_images/ref-001.png"))

        self.assertEqual(
            response_text,
            '{"rendering":[],"color_light":[],"texture_artifacts":[],"notes":""}',
        )
        self.assertEqual(
            calls,
            [
                (
                    "payload_builder",
                    Path("reference_images/ref-001.png"),
                    "custom prompt",
                ),
                (
                    "generate_content",
                    "test-api-key",
                    {"request": "payload"},
                    "gemini-test-model",
                    7,
                ),
            ],
        )

    def test_exp_001c_client_surfaces_transport_errors(self):
        def generate_content(**kwargs):
            raise GeminiImageProbeError("Gemini API HTTP 500: boom")

        client = GeminiImageAnalysisClient(
            api_key="test-api-key",
            payload_builder=lambda **kwargs: {"request": "payload"},
            generate_content=generate_content,
        )

        with self.assertRaisesRegex(GeminiImageProbeError, "HTTP 500"):
            client.analyze_image(Path("reference_images/ref-001.png"))

    def test_exp_001f_client_uses_injected_batch_payload_builder_and_transport(self):
        calls = []

        def batch_payload_builder(*, image_paths, source_images, prompt):
            calls.append(("batch_payload_builder", image_paths, source_images, prompt))
            return {"request": "batch-payload"}

        def generate_content(*, api_key, payload, model, timeout_seconds):
            calls.append(("generate_content", api_key, payload, model, timeout_seconds))
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"images":[]}'
                                }
                            ]
                        }
                    }
                ]
            }

        client = GeminiImageAnalysisClient(
            api_key="test-api-key",
            model="gemini-test-model",
            prompt="custom batch prompt",
            timeout_seconds=7,
            batch_payload_builder=batch_payload_builder,
            generate_content=generate_content,
        )

        response_text = client.analyze_images(
            image_paths=(
                Path("reference_images/a.png"),
                Path("reference_images/b.png"),
            ),
            source_images=(
                "reference_images/a.png",
                "reference_images/b.png",
            ),
        )

        self.assertEqual(response_text, '{"images":[]}')
        self.assertEqual(
            calls,
            [
                (
                    "batch_payload_builder",
                    (Path("reference_images/a.png"), Path("reference_images/b.png")),
                    ("reference_images/a.png", "reference_images/b.png"),
                    "custom batch prompt",
                ),
                (
                    "generate_content",
                    "test-api-key",
                    {"request": "batch-payload"},
                    "gemini-test-model",
                    7,
                ),
            ],
        )


class GeminiPhase0ExtractorTests(unittest.TestCase):
    def test_exp_001d_extractor_reads_manifest_records_and_outputs_valid_candidates(self):
        class FakeClient:
            model = "gemini-fake-model"

            def __init__(self):
                self.calls = []

            def analyze_image(self, image_path):
                self.calls.append(image_path)
                return """
                {
                  "rendering": ["clean linework"],
                  "color_light": ["soft warm rim light"],
                  "texture_artifacts": ["subtle paper grain"],
                  "notes": "fixture response"
                }
                """

        fake_client = FakeClient()
        extractor = GeminiPhase0Extractor(
            project_root=Path("C:/project"),
            client=fake_client,
        )

        candidates_by_aspect = extractor(
            (
                {
                    "path": "reference_images/ref-001.png",
                    "file_hash": "sha256:abc",
                    "image_size": {"width": 2, "height": 3},
                    "analysis_status": "pending",
                },
            )
        )

        validate_style_gene_candidate_aspects(candidates_by_aspect)
        candidate_document = build_style_gene_candidates_document(
            candidates_by_aspect=candidates_by_aspect
        )
        validate_style_gene_candidates_document(candidate_document)

        self.assertEqual(fake_client.calls, [Path("C:/project/reference_images/ref-001.png")])
        self.assertEqual(
            candidates_by_aspect["rendering"][0].source_images,
            ("reference_images/ref-001.png",),
        )
        self.assertIn("gemini-fake-model", candidates_by_aspect["rendering"][0].notes)

    def test_exp_001d_extractor_is_opt_in_for_run_phase0(self):
        class FakeClient:
            model = "gemini-fake-model"

            def analyze_image(self, image_path):
                return """
                {
                  "rendering": ["clean linework"],
                  "color_light": [],
                  "texture_artifacts": [],
                  "notes": "fixture response"
                }
                """

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            gene_pool_path = project_root / "style_gene_pool.json"
            original_gene_pool = '{"version":"0.1.0","genes":{"rendering":[]}}\n'
            gene_pool_path.write_text(original_gene_pool, encoding="utf-8")

            result = run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
                extractor=GeminiPhase0Extractor(
                    project_root=project_root,
                    client=FakeClient(),
                ),
            )
            output_document = json.loads(
                (
                    run_dir / result.style_gene_candidates_path
                ).read_text(encoding="utf-8")
            )
            gene_pool_after_run = gene_pool_path.read_text(encoding="utf-8")
            default_empty_document = build_style_gene_candidates_document()

        self.assertIn(
            "gemini experimental extractor",
            output_document["aspects"]["rendering"][0]["notes"],
        )
        self.assertNotEqual(output_document, default_empty_document)
        self.assertEqual(gene_pool_after_run, original_gene_pool)

    def test_exp_001d_extractor_reports_source_image_on_api_failure(self):
        class FailingClient:
            model = "gemini-fake-model"

            def analyze_image(self, image_path):
                raise GeminiImageProbeError("Gemini API HTTP 500: boom")

        extractor = GeminiPhase0Extractor(
            project_root=Path("C:/project"),
            client=FailingClient(),
        )

        with self.assertRaisesRegex(
            GeminiImageProbeError,
            "reference_images/ref-001.png.*HTTP 500",
        ):
            extractor(
                (
                    {
                        "path": "reference_images/ref-001.png",
                        "file_hash": "sha256:abc",
                        "image_size": {"width": 2, "height": 3},
                        "analysis_status": "pending",
                    },
                )
            )


class GeminiManualIntegrationCommandTests(unittest.TestCase):
    def test_exp_001e_manual_command_exposes_probe_options(self):
        args = parse_args(
            [
                "reference_images/ref-001.png",
                "--model",
                "gemini-test-model",
                "--prompt-file",
                "prompt.txt",
                "--timeout-seconds",
                "7",
                "--raw-output",
                "runs/raw.json",
                "--raw",
            ]
        )

        self.assertEqual(args.backend, DEFAULT_IMAGE_BACKEND)
        self.assertEqual(args.backend, CR001_IMAGE_BACKEND)
        self.assertEqual(args.project_root, Path("."))
        self.assertEqual(args.image_path, Path("reference_images/ref-001.png"))
        self.assertEqual(args.run_dir, DEFAULT_IMAGE_RUN_DIR)
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.prompt_file, Path("prompt.txt"))
        self.assertEqual(args.timeout_seconds, 7)
        self.assertEqual(args.raw_output, Path("runs/raw.json"))
        self.assertTrue(args.raw)

    def test_exp_001e_manual_command_requires_env_api_key_before_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GeminiImageProbeError, "GEMINI_API_KEY"):
                main(["reference_images/ref-001.png"])

    def test_exp_001e_manual_command_defaults_to_cr001_native_backend(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, timeout_seconds):
                calls.append(("init", api_key, model, timeout_seconds))
                self.model = model

            def analyze_image(self, *, image_path, source_image):
                calls.append(("analyze_image", image_path.name, source_image))
                return _valid_cr001_raw_response(source_image=source_image)

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "manual-gemini-single"
            reference_dir.mkdir()
            (reference_dir / "ref-001.png").write_bytes(
                _png_header_bytes(width=2, height=3)
            )

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.cr001.CR001GeminiAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "reference_images/ref-001.png",
                        "--project-root",
                        str(project_root),
                        "--run-dir",
                        str(run_dir),
                        "--model",
                        "gemini-test-model",
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            manifest = json.loads(
                (run_dir / "phase0" / "reference_image_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            artifact = json.loads(
                (run_dir / "phase0" / "cr001_reference_image_analysis.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-test-model", 60),
                ("analyze_image", "ref-001.png", "reference_images/ref-001.png"),
            ],
        )
        self.assertEqual(
            [record["path"] for record in manifest["images"]],
            ["reference_images/ref-001.png"],
        )
        self.assertEqual(
            [record["source_image"] for record in artifact["records"]],
            ["reference_images/ref-001.png"],
        )
        self.assertTrue(stdout_record["valid"])
        self.assertEqual(
            stdout_record["native_artifact_path"],
            "phase0/cr001_reference_image_analysis.json",
        )

    def test_exp_001e_manual_command_rejects_legacy_only_flags_for_cr001_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            prompt_file = project_root / "prompt.txt"
            prompt_file.write_text("legacy prompt", encoding="utf-8")
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                self.assertRaisesRegex(GeminiImageProbeError, "backend legacy"),
            ):
                main(
                    [
                        "reference_images/ref-001.png",
                        "--project-root",
                        str(project_root),
                        "--prompt-file",
                        str(prompt_file),
                    ]
                )

            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                self.assertRaisesRegex(GeminiImageProbeError, "backend legacy"),
            ):
                main(["reference_images/ref-001.png", "--raw"])

    def test_exp_001e_legacy_manual_command_uses_client_wrapper_without_real_api(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                calls.append(("init", api_key, model, prompt, timeout_seconds))

            def generate_content_response(self, image_path):
                calls.append(("generate_content_response", image_path))
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": (
                                            '{"rendering":[],"color_light":[],'
                                            '"texture_artifacts":[],"notes":""}'
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
            patch("style_fit_profiler.gemini_image_probe.GeminiImageAnalysisClient", FakeClient),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main(["--backend", "legacy", "reference_images/ref-001.png", "--raw"])

        self.assertEqual(result, 0)
        self.assertIn('"candidates"', stdout.getvalue())
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-2.5-flash", DEFAULT_ANALYSIS_PROMPT, 60),
                ("generate_content_response", Path("reference_images/ref-001.png")),
            ],
        )

    def test_exp_001e_legacy_manual_command_can_save_raw_response_before_extracting_text(self):
        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                pass

            def generate_content_response(self, image_path):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": (
                                            '{"rendering":[],"color_light":[],'
                                            '"texture_artifacts":[],"notes":""}'
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            raw_output = Path(temp_dir) / "runs" / "raw-response.json"
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_image_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "reference_images/ref-001.png",
                        "--raw-output",
                        str(raw_output),
                    ]
                )

            raw_record = json.loads(raw_output.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertIn('"rendering"', stdout.getvalue())
        self.assertIn("candidates", raw_record)

    def test_exp_001_fu_01d_legacy_single_classifies_provider_error_without_retry(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, prompt, timeout_seconds):
                pass

            def generate_content_response(self, image_path):
                calls.append(image_path)
                raise GeminiImageProbeError(
                    'Gemini API HTTP 429: {"error":{"code":429,'
                    '"status":"RESOURCE_EXHAUSTED",'
                    '"message":"Quota exceeded. Please retry in 5s."}}'
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            raw_output = Path(temp_dir) / "runs" / "provider-error.json"
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"}, clear=True),
                patch("style_fit_profiler.gemini_image_probe.GeminiImageAnalysisClient", FakeClient),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main(
                    [
                        "--backend",
                        "legacy",
                        "reference_images/ref-001.png",
                        "--raw-output",
                        str(raw_output),
                    ]
                )

            stdout_record = json.loads(stdout.getvalue())
            raw_record = json.loads(raw_output.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertEqual(calls, [Path("reference_images/ref-001.png")])
        self.assertFalse(stdout_record["valid"])
        self.assertEqual(
            stdout_record["provider_error"]["type"],
            "provider_quota_exhausted",
        )
        self.assertTrue(stdout_record["provider_error"]["retryable"])
        self.assertEqual(stdout_record["provider_error"]["retry_after_seconds"], 5.0)
        self.assertEqual(raw_record["provider_error"], stdout_record["provider_error"])


if __name__ == "__main__":
    unittest.main()
