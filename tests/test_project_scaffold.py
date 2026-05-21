from importlib import import_module
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class ProjectScaffoldTests(unittest.TestCase):
    def test_p0_00_scaffold_files_exist(self):
        self.assertTrue((PROJECT_ROOT / "pyproject.toml").is_file())
        self.assertTrue((PROJECT_ROOT / "src" / "style_fit_profiler" / "__init__.py").is_file())
        self.assertTrue((PROJECT_ROOT / "tests").is_dir())

    def test_package_imports_from_src_layout(self):
        package = import_module("style_fit_profiler")

        self.assertTrue(hasattr(package, "ReferenceImageAnalysisPolicy"))

    def test_gitignore_excludes_python_execution_artifacts(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("__pycache__/", gitignore)
        self.assertIn("*.py[cod]", gitignore)
        self.assertIn(".venv/", gitignore)


if __name__ == "__main__":
    unittest.main()
