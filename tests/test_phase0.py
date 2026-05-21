from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.config import ReferenceImageAnalysisPolicy  # noqa: E402
from style_fit_profiler.phase0 import Phase0Status, run_phase0  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
