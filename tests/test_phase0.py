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
    run_phase0,
)


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
            (reference_dir / "b.JPG").write_bytes(b"jpg")
            (reference_dir / "a.png").write_bytes(b"png")
            (reference_dir / "notes.txt").write_text("not an image", encoding="utf-8")

            policy = ReferenceImageAnalysisPolicy(enabled=True)
            result = run_phase0(
                policy=policy,
                project_root=project_root,
                run_dir=project_root / "runs" / "run-001",
            )

        self.assertEqual(result.status, Phase0Status.REFERENCE_IMAGES_DISCOVERED)
        self.assertEqual(result.reference_image_paths, ("reference_images/a.png", "reference_images/b.JPG"))
        self.assertEqual(result.reason, "reference images discovered")


if __name__ == "__main__":
    unittest.main()
