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
    BATCH_STYLE_GENE_CANDIDATES_SOURCE,
    STYLE_GENE_CANDIDATES_SOURCE,
    STYLE_GENE_CANDIDATES_VERSION,
    Phase0Batch,
    Phase0BatchResult,
    Phase0BatchStatus,
    StyleGeneCandidate,
    aggregate_phase0_batch_results,
    build_phase0_batch_run_report,
    build_phase0_batch_candidates_document,
    build_style_gene_candidates_document,
    deterministic_mock_phase0_extractor,
    discover_reference_images,
    extract_style_gene_candidates,
    plan_phase0_batches,
    run_phase0_batches,
    run_phase0,
    select_failed_phase0_batches,
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
            candidate_output_exists = (
                run_dir / "phase0" / "style_gene_candidates.json"
            ).is_file()

        self.assertEqual(result.status, Phase0Status.PHASE0_OUTPUT_WRITTEN)
        self.assertEqual(result.reference_image_paths, ("reference_images/a.png", "reference_images/b.JPG"))
        self.assertEqual(result.reference_image_manifest_path, "phase0/reference_image_manifest.json")
        self.assertEqual(result.style_gene_candidates_path, "phase0/style_gene_candidates.json")
        self.assertEqual(result.reason, "phase0 output written")
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
        self.assertTrue(candidate_output_exists)

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


class Phase0BatchPlannerTests(unittest.TestCase):
    def test_exp_002a_empty_input_returns_no_batches(self):
        self.assertEqual(
            plan_phase0_batches(
                reference_image_manifest_records=(),
                batch_size=2,
            ),
            (),
        )

    def test_exp_002a_single_batch_preserves_batch_metadata(self):
        manifest_records = (
            {
                "path": "reference_images/b.png",
                "file_hash": "sha256:b",
                "image_size": {"width": 2, "height": 3},
                "analysis_status": "pending",
            },
            {
                "path": "reference_images/a.png",
                "file_hash": "sha256:a",
                "image_size": {"width": 2, "height": 3},
                "analysis_status": "pending",
            },
        )

        batches = plan_phase0_batches(
            reference_image_manifest_records=manifest_records,
            batch_size=5,
        )

        self.assertEqual(
            batches,
            (
                Phase0Batch(
                    index=0,
                    input_paths=("reference_images/a.png", "reference_images/b.png"),
                    records=(manifest_records[1], manifest_records[0]),
                ),
            ),
        )

    def test_exp_002a_multiple_batches_are_deterministic_by_path(self):
        manifest_records = (
            {"path": "reference_images/c.png"},
            {"path": "reference_images/a.png"},
            {"path": "reference_images/b.png"},
        )

        batches = plan_phase0_batches(
            reference_image_manifest_records=manifest_records,
            batch_size=2,
        )

        self.assertEqual(
            [batch.input_paths for batch in batches],
            [
                ("reference_images/a.png", "reference_images/b.png"),
                ("reference_images/c.png",),
            ],
        )
        self.assertEqual([batch.index for batch in batches], [0, 1])

    def test_exp_002a_supports_input_ordering_rule(self):
        manifest_records = (
            {"path": "reference_images/c.png"},
            {"path": "reference_images/a.png"},
            {"path": "reference_images/b.png"},
        )

        batches = plan_phase0_batches(
            reference_image_manifest_records=manifest_records,
            batch_size=2,
            ordering="input",
        )

        self.assertEqual(
            [batch.input_paths for batch in batches],
            [
                ("reference_images/c.png", "reference_images/a.png"),
                ("reference_images/b.png",),
            ],
        )

    def test_exp_002a_rejects_invalid_batch_size_or_ordering(self):
        for invalid_batch_size in (0, -1, True, "2"):
            with self.subTest(invalid_batch_size=invalid_batch_size):
                with self.assertRaisesRegex(Phase0Error, "batch size"):
                    plan_phase0_batches(
                        reference_image_manifest_records=(),
                        batch_size=invalid_batch_size,
                    )

        with self.assertRaisesRegex(Phase0Error, "batch ordering"):
            plan_phase0_batches(
                reference_image_manifest_records=(),
                batch_size=1,
                ordering="random",
            )


class Phase0BatchRunnerTests(unittest.TestCase):
    def test_exp_002b_runner_records_completed_batch_status(self):
        batch = Phase0Batch(
            index=0,
            input_paths=("reference_images/a.png",),
            records=({"path": "reference_images/a.png"},),
        )
        calls = []

        def analyzer(received_batch):
            calls.append(received_batch)
            return {
                "rendering": (
                    StyleGeneCandidate(
                        id="rendering_batch_a",
                        prompt="batch rendering trait",
                        confidence=0.5,
                        source_images=("reference_images/a.png",),
                        notes="batch analyzer",
                    ),
                ),
                "color_light": (),
                "texture_artifacts": (),
            }

        results = run_phase0_batches(batches=(batch,), analyzer=analyzer)

        self.assertEqual(calls, [batch])
        self.assertEqual(
            results,
            (
                Phase0BatchResult(
                    batch_index=0,
                    input_paths=("reference_images/a.png",),
                    status=Phase0BatchStatus.COMPLETED,
                    candidates_by_aspect={
                        "rendering": (
                            StyleGeneCandidate(
                                id="rendering_batch_a",
                                prompt="batch rendering trait",
                                confidence=0.5,
                                source_images=("reference_images/a.png",),
                                notes="batch analyzer",
                            ),
                        ),
                        "color_light": (),
                        "texture_artifacts": (),
                    },
                ),
            ),
        )

    def test_exp_002b_runner_records_failure_and_continues_remaining_batches(self):
        batches = (
            Phase0Batch(index=0, input_paths=("reference_images/a.png",), records=({"path": "reference_images/a.png"},)),
            Phase0Batch(index=1, input_paths=("reference_images/b.png",), records=({"path": "reference_images/b.png"},)),
            Phase0Batch(index=2, input_paths=("reference_images/c.png",), records=({"path": "reference_images/c.png"},)),
        )
        calls = []

        def analyzer(batch):
            calls.append(batch.index)
            if batch.index == 1:
                raise Phase0Error("provider unavailable")
            return {
                "rendering": (),
                "color_light": (),
                "texture_artifacts": (),
            }

        results = run_phase0_batches(batches=batches, analyzer=analyzer)

        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(
            [result.status for result in results],
            [
                Phase0BatchStatus.COMPLETED,
                Phase0BatchStatus.FAILED,
                Phase0BatchStatus.COMPLETED,
            ],
        )
        self.assertEqual(results[1].batch_index, 1)
        self.assertEqual(results[1].input_paths, ("reference_images/b.png",))
        self.assertIn("provider unavailable", results[1].error)
        self.assertIsNone(results[1].candidates_by_aspect)

    def test_exp_002b_runner_uses_planner_order_deterministically(self):
        batches = plan_phase0_batches(
            reference_image_manifest_records=(
                {"path": "reference_images/c.png"},
                {"path": "reference_images/a.png"},
                {"path": "reference_images/b.png"},
            ),
            batch_size=1,
        )
        calls = []

        def analyzer(batch):
            calls.append(batch.input_paths)
            return {
                "rendering": (),
                "color_light": (),
                "texture_artifacts": (),
            }

        run_phase0_batches(batches=batches, analyzer=analyzer)

        self.assertEqual(
            calls,
            [
                ("reference_images/a.png",),
                ("reference_images/b.png",),
                ("reference_images/c.png",),
            ],
        )


class Phase0BatchAggregatorTests(unittest.TestCase):
    def test_exp_002c_aggregator_merges_completed_batches_by_aspect(self):
        batch_results = (
            Phase0BatchResult(
                batch_index=0,
                input_paths=("reference_images/a.png",),
                status=Phase0BatchStatus.COMPLETED,
                candidates_by_aspect={
                    "rendering": (
                        StyleGeneCandidate(
                            id="rendering_a",
                            prompt="rendering trait a",
                            confidence=0.5,
                            source_images=("reference_images/a.png",),
                            notes="batch 0",
                        ),
                    ),
                    "color_light": (),
                    "texture_artifacts": (),
                },
            ),
            Phase0BatchResult(
                batch_index=1,
                input_paths=("reference_images/b.png",),
                status=Phase0BatchStatus.COMPLETED,
                candidates_by_aspect={
                    "rendering": (),
                    "color_light": (
                        StyleGeneCandidate(
                            id="color_light_b",
                            prompt="color trait b",
                            confidence=0.6,
                            source_images=("reference_images/b.png",),
                            notes="batch 1",
                        ),
                    ),
                    "texture_artifacts": (),
                },
            ),
        )

        candidates_by_aspect = aggregate_phase0_batch_results(batch_results)
        document = build_phase0_batch_candidates_document(
            batch_results=batch_results,
        )

        validate_style_gene_candidate_aspects(candidates_by_aspect)
        validate_style_gene_candidates_document(document)
        self.assertEqual(document["source"], BATCH_STYLE_GENE_CANDIDATES_SOURCE)
        self.assertEqual(
            [candidate.id for candidate in candidates_by_aspect["rendering"]],
            ["rendering_a"],
        )
        self.assertEqual(
            [candidate.id for candidate in candidates_by_aspect["color_light"]],
            ["color_light_b"],
        )

    def test_exp_002c_aggregator_merges_duplicate_candidate_source_images(self):
        duplicate_candidate_a = StyleGeneCandidate(
            id="rendering_shared_trait",
            prompt="shared rendering trait",
            confidence=0.5,
            source_images=("reference_images/a.png",),
            notes="batch 0",
        )
        duplicate_candidate_b = StyleGeneCandidate(
            id="rendering_shared_trait",
            prompt="shared rendering trait",
            confidence=0.5,
            source_images=("reference_images/b.png", "reference_images/a.png"),
            notes="batch 1",
        )

        candidates_by_aspect = aggregate_phase0_batch_results(
            (
                Phase0BatchResult(
                    batch_index=0,
                    input_paths=("reference_images/a.png",),
                    status=Phase0BatchStatus.COMPLETED,
                    candidates_by_aspect={
                        "rendering": (duplicate_candidate_a,),
                        "color_light": (),
                        "texture_artifacts": (),
                    },
                ),
                Phase0BatchResult(
                    batch_index=1,
                    input_paths=("reference_images/b.png",),
                    status=Phase0BatchStatus.COMPLETED,
                    candidates_by_aspect={
                        "rendering": (duplicate_candidate_b,),
                        "color_light": (),
                        "texture_artifacts": (),
                    },
                ),
            )
        )

        self.assertEqual(len(candidates_by_aspect["rendering"]), 1)
        self.assertEqual(
            candidates_by_aspect["rendering"][0].source_images,
            ("reference_images/a.png", "reference_images/b.png"),
        )

    def test_exp_002c_aggregator_rejects_missing_aspect_or_invalid_schema(self):
        with self.assertRaisesRegex(Phase0Error, "missing aspect"):
            aggregate_phase0_batch_results(
                (
                    Phase0BatchResult(
                        batch_index=0,
                        input_paths=("reference_images/a.png",),
                        status=Phase0BatchStatus.COMPLETED,
                        candidates_by_aspect={
                            "rendering": (),
                            "color_light": (),
                        },
                    ),
                )
            )

        with self.assertRaisesRegex(Phase0Error, "source_images"):
            build_phase0_batch_candidates_document(
                batch_results=(
                    Phase0BatchResult(
                        batch_index=0,
                        input_paths=("reference_images/a.png",),
                        status=Phase0BatchStatus.COMPLETED,
                        candidates_by_aspect={
                            "rendering": (
                                StyleGeneCandidate(
                                    id="rendering_invalid",
                                    prompt="invalid",
                                    confidence=0.5,
                                    source_images=(),
                                    notes="",
                                ),
                            ),
                            "color_light": (),
                            "texture_artifacts": (),
                        },
                    ),
                )
            )


class Phase0BatchFailureIsolationTests(unittest.TestCase):
    def test_exp_002d_failed_batch_does_not_block_partial_success_output(self):
        batch_results = (
            Phase0BatchResult(
                batch_index=0,
                input_paths=("reference_images/a.png",),
                status=Phase0BatchStatus.COMPLETED,
                candidates_by_aspect={
                    "rendering": (
                        StyleGeneCandidate(
                            id="rendering_a",
                            prompt="rendering trait a",
                            confidence=0.5,
                            source_images=("reference_images/a.png",),
                            notes="batch 0",
                        ),
                    ),
                    "color_light": (),
                    "texture_artifacts": (),
                },
            ),
            Phase0BatchResult(
                batch_index=1,
                input_paths=("reference_images/b.png",),
                status=Phase0BatchStatus.FAILED,
                error="provider unavailable",
            ),
        )

        document = build_phase0_batch_candidates_document(batch_results=batch_results)
        report = build_phase0_batch_run_report(batch_results=batch_results)

        validate_style_gene_candidates_document(document)
        self.assertEqual(
            [candidate["id"] for candidate in document["aspects"]["rendering"]],
            ["rendering_a"],
        )
        self.assertEqual(report["summary"]["completed_batches"], 1)
        self.assertEqual(report["summary"]["failed_batches"], 1)
        self.assertEqual(report["summary"]["retryable_batch_indexes"], [1])
        self.assertEqual(
            report["batches"][1],
            {
                "batch_index": 1,
                "input_paths": ["reference_images/b.png"],
                "status": "failed",
                "error": "provider unavailable",
                "output_paths": [],
                "retryable": True,
            },
        )

    def test_exp_002d_failed_batches_can_be_selected_for_retry(self):
        batches = (
            Phase0Batch(index=0, input_paths=("reference_images/a.png",), records=({"path": "reference_images/a.png"},)),
            Phase0Batch(index=1, input_paths=("reference_images/b.png",), records=({"path": "reference_images/b.png"},)),
            Phase0Batch(index=2, input_paths=("reference_images/c.png",), records=({"path": "reference_images/c.png"},)),
        )
        batch_results = (
            Phase0BatchResult(
                batch_index=0,
                input_paths=("reference_images/a.png",),
                status=Phase0BatchStatus.COMPLETED,
                candidates_by_aspect={
                    "rendering": (),
                    "color_light": (),
                    "texture_artifacts": (),
                },
            ),
            Phase0BatchResult(
                batch_index=1,
                input_paths=("reference_images/b.png",),
                status=Phase0BatchStatus.FAILED,
                error="timeout",
            ),
            Phase0BatchResult(
                batch_index=2,
                input_paths=("reference_images/c.png",),
                status=Phase0BatchStatus.FAILED,
                error="quota",
            ),
        )

        retry_batches = select_failed_phase0_batches(
            batches=batches,
            batch_results=batch_results,
        )

        self.assertEqual(retry_batches, (batches[1], batches[2]))


class DeterministicMockExtractorTests(unittest.TestCase):
    def test_p0_08_mock_extractor_returns_equivalent_candidates_for_same_input(self):
        manifest_records = (
            {
                "path": "reference_images/ref-002.png",
                "file_hash": "sha256:def",
                "image_size": {"width": 4, "height": 5},
                "analysis_status": "pending",
            },
            {
                "path": "reference_images/ref-001.png",
                "file_hash": "sha256:abc",
                "image_size": {"width": 2, "height": 3},
                "analysis_status": "pending",
            },
        )

        first_document = build_style_gene_candidates_document(
            candidates_by_aspect=deterministic_mock_phase0_extractor(manifest_records)
        )
        second_document = build_style_gene_candidates_document(
            candidates_by_aspect=deterministic_mock_phase0_extractor(manifest_records)
        )

        validate_style_gene_candidates_document(first_document)
        self.assertEqual(first_document, second_document)
        self.assertEqual(
            [record["source_images"] for record in first_document["aspects"]["rendering"]],
            [["reference_images/ref-001.png"], ["reference_images/ref-002.png"]],
        )
        self.assertEqual(
            {
                aspect: len(candidates)
                for aspect, candidates in first_document["aspects"].items()
            },
            {
                "rendering": 2,
                "color_light": 2,
                "texture_artifacts": 2,
            },
        )


class AspectClassificationTests(unittest.TestCase):
    def test_p0_09_accepts_fixed_aspects_with_matching_id_prefixes(self):
        candidates_by_aspect = deterministic_mock_phase0_extractor(
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

    def test_p0_09_rejects_unknown_or_missing_aspect_key(self):
        valid_candidates = deterministic_mock_phase0_extractor(
            (
                {
                    "path": "reference_images/ref-001.png",
                    "file_hash": "sha256:abc",
                    "image_size": {"width": 2, "height": 3},
                    "analysis_status": "pending",
                },
            )
        )

        missing_aspect = dict(valid_candidates)
        del missing_aspect["texture_artifacts"]

        with self.assertRaisesRegex(Phase0Error, "missing aspect"):
            validate_style_gene_candidate_aspects(missing_aspect)

        unknown_aspect = dict(valid_candidates)
        unknown_aspect["composition"] = ()

        with self.assertRaisesRegex(Phase0Error, "unknown aspect"):
            validate_style_gene_candidate_aspects(unknown_aspect)

    def test_p0_09_extractor_adapter_rejects_unknown_aspect_key(self):
        def extractor(reference_image_manifest_records):
            return {
                "rendering": (),
                "color_light": (),
                "texture_artifacts": (),
                "composition": (),
            }

        with self.assertRaisesRegex(Phase0Error, "unknown aspect"):
            extract_style_gene_candidates(
                extractor=extractor,
                reference_image_manifest_records=(),
            )

    def test_p0_09_rejects_candidate_id_prefix_that_does_not_match_aspect(self):
        candidates_by_aspect = deterministic_mock_phase0_extractor(
            (
                {
                    "path": "reference_images/ref-001.png",
                    "file_hash": "sha256:abc",
                    "image_size": {"width": 2, "height": 3},
                    "analysis_status": "pending",
                },
            )
        )
        candidates_by_aspect = {
            aspect: list(candidates)
            for aspect, candidates in candidates_by_aspect.items()
        }
        candidates_by_aspect["rendering"][0] = StyleGeneCandidate(
            id="color_light_wrong_prefix",
            prompt="wrong prefix",
            confidence=0.5,
            source_images=("reference_images/ref-001.png",),
            notes="",
        )

        with self.assertRaisesRegex(Phase0Error, "candidate gene id prefix"):
            validate_style_gene_candidate_aspects(candidates_by_aspect)


class Phase0OutputWriterTests(unittest.TestCase):
    def test_p0_10_enabled_policy_writes_manifest_and_candidate_gene_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            png_bytes = _png_header_bytes(width=2, height=3)
            (reference_dir / "a.png").write_bytes(png_bytes)

            result = run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
            )

            manifest = json.loads(
                (run_dir / "phase0" / "reference_image_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate_document = json.loads(
                (run_dir / "phase0" / "style_gene_candidates.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result.status, Phase0Status.PHASE0_OUTPUT_WRITTEN)
        self.assertEqual(result.reason, "phase0 output written")
        self.assertEqual(result.reference_image_manifest_path, "phase0/reference_image_manifest.json")
        self.assertEqual(result.style_gene_candidates_path, "phase0/style_gene_candidates.json")
        self.assertEqual(
            manifest["images"][0],
            {
                "path": "reference_images/a.png",
                "file_hash": _sha256_digest(png_bytes),
                "image_size": {"width": 2, "height": 3},
                "analysis_status": "pending",
            },
        )
        validate_style_gene_candidates_document(candidate_document)
        self.assertEqual(
            candidate_document["aspects"]["rendering"][0]["source_images"],
            ["reference_images/a.png"],
        )

    def test_p0_10_enabled_policy_writes_custom_extractor_candidates(self):
        extractor_inputs = []

        def extractor(reference_image_manifest_records):
            extractor_inputs.append(tuple(reference_image_manifest_records))
            return {
                "rendering": (
                    StyleGeneCandidate(
                        id="rendering_custom_ref_001",
                        prompt="custom rendering trait",
                        confidence=0.7,
                        source_images=("reference_images/a.png",),
                        notes="custom extractor",
                    ),
                ),
                "color_light": (),
                "texture_artifacts": (),
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
                extractor=extractor,
            )

            candidate_document = json.loads(
                (run_dir / "phase0" / "style_gene_candidates.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            [record["path"] for record in extractor_inputs[0]],
            ["reference_images/a.png"],
        )
        self.assertEqual(
            candidate_document["aspects"]["rendering"][0],
            {
                "id": "rendering_custom_ref_001",
                "prompt": "custom rendering trait",
                "confidence": 0.7,
                "source_images": ["reference_images/a.png"],
                "notes": "custom extractor",
            },
        )


class GenePoolOverwriteProtectionTests(unittest.TestCase):
    def test_p0_11_phase0_success_does_not_overwrite_style_gene_pool(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            gene_pool_path = project_root / "style_gene_pool.json"
            original_gene_pool = '{"version":"0.1.0","genes":{"rendering":[]}}\n'
            gene_pool_path.write_text(original_gene_pool, encoding="utf-8")

            run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
            )

            gene_pool_after_run = gene_pool_path.read_text(encoding="utf-8")

        self.assertEqual(gene_pool_after_run, original_gene_pool)

    def test_p0_11_phase0_failure_does_not_overwrite_style_gene_pool(self):
        def invalid_extractor(reference_image_manifest_records):
            return {
                "rendering": (),
                "color_light": (),
                "texture_artifacts": (),
                "composition": (),
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))
            gene_pool_path = project_root / "style_gene_pool.json"
            original_gene_pool = '{"version":"0.1.0","genes":{"rendering":[]}}\n'
            gene_pool_path.write_text(original_gene_pool, encoding="utf-8")

            with self.assertRaisesRegex(Phase0Error, "unknown aspect"):
                run_phase0(
                    policy=ReferenceImageAnalysisPolicy(enabled=True),
                    project_root=project_root,
                    run_dir=run_dir,
                    extractor=invalid_extractor,
                )

            gene_pool_after_run = gene_pool_path.read_text(encoding="utf-8")

        self.assertEqual(gene_pool_after_run, original_gene_pool)


class AC01APhase0ReferenceAnalysisTests(unittest.TestCase):
    def test_p0_12_ac01a_enabled_path_outputs_traceable_candidate_genes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            run_dir = project_root / "runs" / "run-001"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            result = run_phase0(
                policy=ReferenceImageAnalysisPolicy(enabled=True),
                project_root=project_root,
                run_dir=run_dir,
            )

            manifest_path = run_dir / result.reference_image_manifest_path
            candidates_path = run_dir / result.style_gene_candidates_path
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            candidate_document = json.loads(candidates_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, Phase0Status.PHASE0_OUTPUT_WRITTEN)
        self.assertEqual(
            {record["path"] for record in manifest["images"]},
            {"reference_images/a.png"},
        )
        self.assertEqual(
            set(candidate_document["aspects"]),
            set(STYLE_GENE_CANDIDATE_ASPECTS),
        )
        for candidates in candidate_document["aspects"].values():
            self.assertGreaterEqual(len(candidates), 1)
            for candidate in candidates:
                self.assertIn("reference_images/a.png", candidate["source_images"])

    def test_p0_12_ac01a_disabled_path_skips_reference_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "run-001"

            result = run_phase0(
                policy=ReferenceImageAnalysisPolicy(
                    enabled=False,
                    input_dir="missing_reference_images",
                ),
                project_root=project_root,
                run_dir=run_dir,
            )

        self.assertEqual(result.status, Phase0Status.SKIPPED)
        self.assertEqual(result.reason, "reference image analysis disabled")

    def test_p0_12_ac01a_rejects_missing_or_empty_reference_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            with self.assertRaisesRegex(Phase0Error, "reference image directory does not exist"):
                run_phase0(
                    policy=ReferenceImageAnalysisPolicy(enabled=True),
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-001",
                )

            (project_root / "reference_images").mkdir()

            with self.assertRaisesRegex(Phase0Error, "no supported reference images found"):
                run_phase0(
                    policy=ReferenceImageAnalysisPolicy(enabled=True),
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-002",
                )

    def test_p0_12_ac01a_rejects_invalid_candidate_schema(self):
        def invalid_extractor(reference_image_manifest_records):
            return {
                "rendering": (
                    StyleGeneCandidate(
                        id="rendering_invalid",
                        prompt="invalid candidate",
                        confidence=0.5,
                        source_images=(),
                        notes="",
                    ),
                ),
                "color_light": (),
                "texture_artifacts": (),
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            reference_dir = project_root / "reference_images"
            reference_dir.mkdir()
            (reference_dir / "a.png").write_bytes(_png_header_bytes(width=2, height=3))

            with self.assertRaisesRegex(Phase0Error, "source_images"):
                run_phase0(
                    policy=ReferenceImageAnalysisPolicy(enabled=True),
                    project_root=project_root,
                    run_dir=project_root / "runs" / "run-001",
                    extractor=invalid_extractor,
                )


if __name__ == "__main__":
    unittest.main()
