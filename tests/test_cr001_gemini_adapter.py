from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.cr001 import (  # noqa: E402
    CR001GeminiAnalysisClient,
    CR001GeminiRawAnalysis,
    CR001GeminiRawExtractor,
    build_cr001_generate_content_payload,
)


class CR001GeminiPayloadTests(unittest.TestCase):
    def test_cr001_06b_payload_includes_inline_image_and_restricted_prompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "ref-001.png"
            image_path.write_bytes(b"fake-png-bytes")

            payload = build_cr001_generate_content_payload(
                image_path=image_path,
                source_image="reference_images/ref-001.png",
            )

        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(parts[0]["inline_data"]["data"], "ZmFrZS1wbmctYnl0ZXM=")
        self.assertIn("Visual Style & Appeal Point Encoder", parts[1]["text"])
        self.assertIn("reference_images/ref-001.png", parts[1]["text"])
        self.assertIn('"genre"', parts[1]["text"])
        self.assertIn('"facial_features"', parts[1]["text"])
        self.assertEqual(payload["generationConfig"]["response_mime_type"], "application/json")


class CR001GeminiAnalysisClientTests(unittest.TestCase):
    def test_cr001_06b_client_uses_injected_payload_builder_and_transport(self):
        calls = []

        def payload_builder(*, image_path, source_image):
            calls.append(("payload_builder", image_path, source_image))
            return {"request": "cr001-payload"}

        def generate_content(*, api_key, payload, model, timeout_seconds):
            calls.append(("generate_content", api_key, payload, model, timeout_seconds))
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"appeal_point_and_art_style":{},'
                                        '"cr001_summary":"raw fixture"}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

        client = CR001GeminiAnalysisClient(
            api_key="test-api-key",
            model="gemini-test-model",
            timeout_seconds=7,
            payload_builder=payload_builder,
            generate_content=generate_content,
        )

        response_text = client.analyze_image(
            image_path=Path("reference_images/ref-001.png"),
            source_image="reference_images/ref-001.png",
        )

        self.assertEqual(
            response_text,
            '{"appeal_point_and_art_style":{},"cr001_summary":"raw fixture"}',
        )
        self.assertEqual(
            calls,
            [
                (
                    "payload_builder",
                    Path("reference_images/ref-001.png"),
                    "reference_images/ref-001.png",
                ),
                (
                    "generate_content",
                    "test-api-key",
                    {"request": "cr001-payload"},
                    "gemini-test-model",
                    7,
                ),
            ],
        )


class CR001GeminiRawExtractorTests(unittest.TestCase):
    def test_cr001_06b_raw_extractor_reads_manifest_records_without_parsing(self):
        class FakeClient:
            model = "gemini-fake-model"

            def __init__(self):
                self.calls = []

            def analyze_image(self, *, image_path, source_image):
                self.calls.append((image_path, source_image))
                return '{"raw":"fixture"}'

        fake_client = FakeClient()
        extractor = CR001GeminiRawExtractor(
            project_root=Path("C:/project"),
            client=fake_client,
        )

        analyses = extractor(
            (
                {
                    "path": "reference_images/ref-001.png",
                    "file_hash": "sha256:abc",
                    "image_size": {"width": 2, "height": 3},
                    "analysis_status": "pending",
                },
            )
        )

        self.assertEqual(
            analyses,
            (
                CR001GeminiRawAnalysis(
                    source_image="reference_images/ref-001.png",
                    response_text='{"raw":"fixture"}',
                    model="gemini-fake-model",
                ),
            ),
        )
        self.assertEqual(
            fake_client.calls,
            [
                (
                    Path("C:/project/reference_images/ref-001.png"),
                    "reference_images/ref-001.png",
                )
            ],
        )

    def test_cr001_06b_raw_extractor_reports_source_image_on_failure(self):
        class FailingClient:
            model = "gemini-fake-model"

            def analyze_image(self, *, image_path, source_image):
                raise RuntimeError("transport boom")

        extractor = CR001GeminiRawExtractor(
            project_root=Path("C:/project"),
            client=FailingClient(),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "reference_images/ref-001.png.*transport boom",
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


if __name__ == "__main__":
    unittest.main()
