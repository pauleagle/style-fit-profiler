from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.gemini_image_probe import (  # noqa: E402
    DEFAULT_ANALYSIS_PROMPT,
    GeminiImageProbeError,
    build_generate_content_payload,
    extract_response_text,
    guess_image_mime_type,
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


if __name__ == "__main__":
    unittest.main()
