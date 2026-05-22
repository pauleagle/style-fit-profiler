from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.gemini_image_probe import (  # noqa: E402
    DEFAULT_ANALYSIS_PROMPT,
    GEMINI_TRAIT_ASPECTS,
    GeminiImageProbeError,
    build_generate_content_payload,
    extract_response_text,
    guess_image_mime_type,
    parse_gemini_trait_response,
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


if __name__ == "__main__":
    unittest.main()
