from pathlib import Path
from contextlib import redirect_stdout
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
    DEFAULT_ANALYSIS_PROMPT,
    DEFAULT_BATCH_ANALYSIS_PROMPT,
    GEMINI_TRAIT_ASPECTS,
    GeminiImageAnalysisClient,
    GeminiImageProbeError,
    GeminiPhase0Extractor,
    build_batch_generate_content_payload,
    build_generate_content_payload,
    extract_response_text,
    guess_image_mime_type,
    main,
    map_gemini_traits_to_candidates,
    parse_args,
    parse_gemini_batch_trait_response,
    parse_gemini_trait_response,
)
from style_fit_profiler.config import ReferenceImageAnalysisPolicy  # noqa: E402
from style_fit_profiler.phase0 import (  # noqa: E402
    build_style_gene_candidates_document,
    run_phase0,
    validate_style_gene_candidate_aspects,
    validate_style_gene_candidates_document,
)


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
                "--raw",
            ]
        )

        self.assertEqual(args.image_path, Path("reference_images/ref-001.png"))
        self.assertEqual(args.model, "gemini-test-model")
        self.assertEqual(args.prompt_file, Path("prompt.txt"))
        self.assertTrue(args.raw)

    def test_exp_001e_manual_command_requires_env_api_key_before_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GeminiImageProbeError, "GEMINI_API_KEY"):
                main(["reference_images/ref-001.png"])

    def test_exp_001e_manual_command_uses_client_wrapper_without_real_api(self):
        calls = []

        class FakeClient:
            def __init__(self, *, api_key, model, prompt):
                calls.append(("init", api_key, model, prompt))

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
            result = main(["reference_images/ref-001.png", "--raw"])

        self.assertEqual(result, 0)
        self.assertIn('"candidates"', stdout.getvalue())
        self.assertEqual(
            calls,
            [
                ("init", "test-api-key", "gemini-2.5-flash", DEFAULT_ANALYSIS_PROMPT),
                ("generate_content_response", Path("reference_images/ref-001.png")),
            ],
        )


if __name__ == "__main__":
    unittest.main()
