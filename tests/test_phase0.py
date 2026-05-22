import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.config import ReferenceImageAnalysisPolicy  # noqa: E402
from style_fit_profiler.phase0 import (  # noqa: E402
    Phase0Error,
    Phase0Status,
    STYLE_GENE_CANDIDATE_ASPECTS,
    STYLE_GENE_CANDIDATE_FIELDS,
    STYLE_GENE_CANDIDATES_SOURCE,
    STYLE_GENE_CANDIDATES_VERSION,
    StyleGeneCandidate,
    build_style_gene_candidates_document,
    discover_reference_images,
    extract_style_gene_candidates,
    run_phase0,
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


def _jpeg_header_bytes(*, width, height):
    return (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def _gif_header_bytes(*, width, height):
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little")


def _bmp_header_bytes(*, width, height):
    return (
        b"BM"
        + b"\x00" * 12
        + (40).to_bytes(4, "little")
        + width.to_bytes(4, "little", signed=True)
        + height.to_bytes(4, "little", signed=True)
    )


def _webp_vp8x_header_bytes(*, width, height):
    payload = (
        b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    return b"RIFF" + (len(payload) + 12).to_bytes(4, "little") + b"WEBPVP8X" + len(
        payload
    ).to_bytes(4, "little") + payload


def _tiff_header_bytes(*, width, height):
    return (
        b"II*\x00"
        + (8).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (256).to_bytes(2, "little")
        + (4).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + width.to_bytes(4, "little")
        + (257).to_bytes(2, "little")
        + (4).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + height.to_bytes(4, "little")
        + (0).to_bytes(4, "little")
    )


def _sha256_digest(data):
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class DisabledPhase0Tests(unittest.TestCase):
    def test_disabled_policy_does_not_require_reference_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "run-001"
            policy = ReferenceImageAnalysisPolicy(
                enabled=False,
                input_dir="missing_reference_images",
            )

            result = run_phase0(policy=policy, project_root=project_root, run_dir=run_dir)

        self.assertEqual(result.status, Phase0Status.SKIPPED)
        self.assertEqual(result.reason, "reference image analysis disabled")

    def test_disabled_policy_does_not_create_phase0_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "run-001"
            policy = ReferenceImageAnalysisPolicy(enabled=False)

            result = run_phase0(policy=policy, project_root=project_root, run_dir=run_dir)

            self.assertEqual(result.status, Phase0Status.SKIPPED)
            self.assertFalse((run_dir / "phase0").exists())

    def test_disabled_policy_does_not_call_extractor(self):
        calls = []

        def extractor(*args, **kwargs):
            calls.append((args, kwargs))

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "run-001"
            policy = ReferenceImageAnalysisPolicy(enabled=False)

            result = run_phase0(
                policy=policy,
                project_root=project_root,
                run_dir=run_dir,
                extractor=extractor,
            )

        self.assertEqual(result.status, Phase0Status.SKIPPED)
        self.assertEqual(calls, [])


class ReferenceImageDiscoveryTests(unittest.TestCase):
    def test_p0_03_enabled_policy_rejects_missing_reference_image_dir(self):
        # Spec P0-03 / Phase 0 error condition: enabled analysis requires input_dir.
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            policy = ReferenceImageAnalysisPolicy(
                enabled=True,
                input_dir="missing_reference_images",
            )

            with self.assertRaisesRegex(Phase0Error, "reference image directory does not exist"):
                run_phase0(
                    policy=policy,
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-001",
                )

    def test_p0_03_enabled_policy_rejects_empty_reference_image_dir(self):
        # Spec P0-03 / Phase 0 error condition: enabled analysis needs supported images.
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "reference_images").mkdir()
            policy = ReferenceImageAnalysisPolicy(enabled=True)

            with self.assertRaisesRegex(Phase0Error, "no supported reference images found"):
                run_phase0(
                    policy=policy,
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-001",
                )

    def test_p0_03_enabled_policy_ignores_unsupported_files(self):
        # Spec P0-03: discovery only accepts supported image file extensions.
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            reference_dir.mkdir()
            (reference_dir / "notes.txt").write_text("not an image", encoding="utf-8")

            policy = ReferenceImageAnalysisPolicy(enabled=True)

            with self.assertRaisesRegex(Phase0Error, "no supported reference images found"):
                run_phase0(
                    policy=policy,
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-001",
                )

    def test_p0_03_enabled_policy_discovers_supported_images_deterministically(self):
        # Spec P0-03: enabled analysis scans input_dir for supported image files.
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            reference_dir.mkdir()
            (reference_dir / "b.JPG").write_bytes(_jpeg_header_bytes(width=4, height=5))
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            (reference_dir / "notes.txt").write_text("not an image", encoding="utf-8")

            image_paths = discover_reference_images(
                project_root=project_root,
                input_dir="reference_images",
            )

        self.assertEqual(image_paths, ("reference_images/a.png", "reference_images/b.JPG"))


class ReferenceImageManifestTests(unittest.TestCase):
    def test_p0_04_enabled_policy_writes_reference_image_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            png_bytes = _png_header_bytes(width=2, height=3)
            jpeg_bytes = _jpeg_header_bytes(width=4, height=5)
            (reference_dir / "b.JPG").write_bytes(jpeg_bytes)
            (reference_dir / "a.png").write_bytes(png_bytes)

            policy = ReferenceImageAnalysisPolicy(enabled=True)
            result = run_phase0(
                policy=policy,
                project_root=project_root,
                run_dir=run_dir,
            )

            manifest_path = run_dir / "phase0" / "reference_image_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, Phase0Status.REFERENCE_IMAGE_MANIFEST_WRITTEN)
        self.assertEqual(result.reference_image_paths, ("reference_images/a.png", "reference_images/b.JPG"))
        self.assertEqual(result.reference_image_manifest_path, "phase0/reference_image_manifest.json")
        self.assertEqual(result.reason, "reference image manifest written")
        self.assertEqual(
            manifest,
            {
                "version": "0.1.0",
                "source": "phase0_reference_image_analysis",
                "images": [
                    {
                        "path": "reference_images/a.png",
                        "file_hash": _sha256_digest(png_bytes),
                        "image_size": {"width": 2, "height": 3},
                        "analysis_status": "pending",
                    },
                    {
                        "path": "reference_images/b.JPG",
                        "file_hash": _sha256_digest(jpeg_bytes),
                        "image_size": {"width": 4, "height": 5},
                        "analysis_status": "pending",
                    },
                ],
            },
        )
        self.assertFalse((run_dir / "phase0" / "style_gene_candidates.json").exists())

    def test_p0_04_manifest_reads_image_size_for_supported_formats(self):
        fixtures = {
            "reference_images/a.bmp": (_bmp_header_bytes(width=2, height=3), {"width": 2, "height": 3}),
            "reference_images/b.gif": (_gif_header_bytes(width=4, height=5), {"width": 4, "height": 5}),
            "reference_images/c.jpeg": (_jpeg_header_bytes(width=6, height=7), {"width": 6, "height": 7}),
            "reference_images/d.png": (_png_header_bytes(width=8, height=9), {"width": 8, "height": 9}),
            "reference_images/e.tiff": (_tiff_header_bytes(width=10, height=11), {"width": 10, "height": 11}),
            "reference_images/f.webp": (_webp_vp8x_header_bytes(width=12, height=13), {"width": 12, "height": 13}),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            for relative_path, (image_bytes, _) in fixtures.items():
                (project_root / relative_path).write_bytes(image_bytes)

            run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
            )

            manifest = json.loads(
                (run_dir / "phase0" / "reference_image_manifest.json").read_text(encoding="utf-8")
            )

        image_sizes = {record["path"]: record["image_size"] for record in manifest["images"]}
        self.assertEqual(
            image_sizes,
            {relative_path: image_size for relative_path, (_, image_size) in fixtures.items()},
        )


class CandidateGeneSchemaTests(unittest.TestCase):
    def test_p0_05_candidate_document_declares_required_aspects(self):
        document = build_style_gene_candidates_document()

        self.assertEqual(document["version"], STYLE_GENE_CANDIDATES_VERSION)
        self.assertEqual(document["source"], STYLE_GENE_CANDIDATES_SOURCE)
        self.assertEqual(tuple(document["aspects"]), STYLE_GENE_CANDIDATE_ASPECTS)
        self.assertEqual(
            document["aspects"],
            {
                "rendering": [],
                "color_light": [],
                "texture_artifacts": [],
            },
        )

    def test_p0_05_candidate_record_contains_spec_fields(self):
        candidate = StyleGeneCandidate(
            id="rendering_soft_airbrush_edges",
            prompt="soft airbrushed edges",
            confidence=0.72,
            source_images=("reference_images/ref-001.png",),
            notes="",
        )

        document = build_style_gene_candidates_document(
            candidates_by_aspect={"rendering": (candidate,)}
        )
        record = document["aspects"]["rendering"][0]

        self.assertEqual(tuple(record), STYLE_GENE_CANDIDATE_FIELDS)
        self.assertEqual(
            record,
            {
                "id": "rendering_soft_airbrush_edges",
                "prompt": "soft airbrushed edges",
                "confidence": 0.72,
                "source_images": ["reference_images/ref-001.png"],
                "notes": "",
            },
        )


def _valid_style_gene_candidates_document():
    return build_style_gene_candidates_document(
        candidates_by_aspect={
            "rendering": (
                StyleGeneCandidate(
                    id="rendering_soft_airbrush_edges",
                    prompt="soft airbrushed edges",
                    confidence=0.72,
                    source_images=("reference_images/ref-001.png",),
                    notes="",
                ),
            ),
            "color_light": (
                StyleGeneCandidate(
                    id="color_light_muted_cyan_rose",
                    prompt="muted cyan and rose palette",
                    confidence=0,
                    source_images=("reference_images/ref-001.png",),
                    notes="",
                ),
            ),
            "texture_artifacts": (
                StyleGeneCandidate(
                    id="texture_artifacts_paper_grain",
                    prompt="subtle paper grain texture",
                    confidence=1,
                    source_images=("reference_images/ref-002.png",),
                    notes="",
                ),
            ),
        }
    )


class CandidateGeneValidatorTests(unittest.TestCase):
    def test_p0_06_accepts_valid_candidate_document(self):
        validate_style_gene_candidates_document(_valid_style_gene_candidates_document())

    def test_p0_06_rejects_missing_required_schema_parts(self):
        document = _valid_style_gene_candidates_document()
        del document["aspects"]["texture_artifacts"]

        with self.assertRaisesRegex(Phase0Error, "missing aspect"):
            validate_style_gene_candidates_document(document)

        document = _valid_style_gene_candidates_document()
        del document["aspects"]["rendering"][0]["notes"]

        with self.assertRaisesRegex(Phase0Error, "missing candidate field"):
            validate_style_gene_candidates_document(document)

    def test_p0_06_rejects_duplicate_candidate_ids_across_file(self):
        document = _valid_style_gene_candidates_document()
        document["aspects"]["color_light"][0]["id"] = "rendering_soft_airbrush_edges"

        with self.assertRaisesRegex(Phase0Error, "duplicate candidate gene id"):
            validate_style_gene_candidates_document(document)

        document = _valid_style_gene_candidates_document()
        document["aspects"]["experimental"] = [
            {
                "id": "rendering_soft_airbrush_edges",
                "prompt": "extra aspect should still be scanned",
                "confidence": 0.5,
                "source_images": ["reference_images/ref-001.png"],
                "notes": "",
            }
        ]

        with self.assertRaisesRegex(Phase0Error, "duplicate candidate gene id"):
            validate_style_gene_candidates_document(document)

    def test_p0_06_rejects_blank_prompt(self):
        document = _valid_style_gene_candidates_document()
        document["aspects"]["rendering"][0]["prompt"] = " "

        with self.assertRaisesRegex(Phase0Error, "prompt"):
            validate_style_gene_candidates_document(document)

    def test_p0_06_rejects_confidence_outside_zero_to_one(self):
        for invalid_confidence in (-0.01, 1.01, True, "0.5"):
            with self.subTest(invalid_confidence=invalid_confidence):
                document = _valid_style_gene_candidates_document()
                document["aspects"]["rendering"][0]["confidence"] = invalid_confidence

                with self.assertRaisesRegex(Phase0Error, "confidence"):
                    validate_style_gene_candidates_document(document)

    def test_p0_06_rejects_empty_or_absolute_source_images(self):
        invalid_source_images = (
            [],
            [""],
            ["/reference_images/ref-001.png"],
            ["\\reference_images\\ref-001.png"],
            ["C:reference_images\\ref-001.png"],
            ["C:\\reference_images\\ref-001.png"],
        )

        for source_images in invalid_source_images:
            with self.subTest(source_images=source_images):
                document = _valid_style_gene_candidates_document()
                document["aspects"]["rendering"][0]["source_images"] = source_images

                with self.assertRaisesRegex(Phase0Error, "source_images"):
                    validate_style_gene_candidates_document(document)


class ExtractorInterfaceTests(unittest.TestCase):
    def test_p0_07_extractor_receives_manifest_records_and_returns_candidates(self):
        manifest_records = (
            {
                "path": "reference_images/ref-001.png",
                "file_hash": "sha256:abc",
                "image_size": {"width": 2, "height": 3},
                "analysis_status": "pending",
            },
        )
        calls = []

        def extractor(reference_image_manifest_records):
            calls.append(reference_image_manifest_records)
            return {
                "rendering": (
                    StyleGeneCandidate(
                        id="rendering_mock_ref_001",
                        prompt="mock rendering trait from ref 001",
                        confidence=0.5,
                        source_images=("reference_images/ref-001.png",),
                        notes="",
                    ),
                ),
                "color_light": (),
                "texture_artifacts": (),
            }

        candidates_by_aspect = extract_style_gene_candidates(
            extractor=extractor,
            reference_image_manifest_records=manifest_records,
        )

        self.assertEqual(calls, [manifest_records])
        self.assertEqual(tuple(candidates_by_aspect), STYLE_GENE_CANDIDATE_ASPECTS)
        self.assertEqual(
            candidates_by_aspect["rendering"][0].id,
            "rendering_mock_ref_001",
        )


if __name__ == "__main__":
    unittest.main()
