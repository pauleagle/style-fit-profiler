import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler.notebook import (  # noqa: E402
    NotebookCell,
    build_colab_runtime_bootstrap_cells,
    build_colab_runtime_bootstrap_notebook,
)


class ColabRuntimeBootstrapTests(unittest.TestCase):
    def test_exp_003a_builds_runtime_setup_and_dependency_cells(self):
        cells = build_colab_runtime_bootstrap_cells(
            project_root="/content/style-fit-profiler",
            run_id="colab-smoke",
        )

        self.assertEqual(
            [cell.name for cell in cells],
            [
                "runtime-setup",
                "dependency-check",
            ],
        )
        self.assertTrue(all(cell.cell_type == "code" for cell in cells))
        self.assertIn("/content/style-fit-profiler", cells[0].source)
        self.assertIn("sys.path.insert", cells[0].source)
        self.assertIn("reference_images", cells[0].source)
        self.assertIn("runs", cells[0].source)
        self.assertIn("style_fit_profiler", cells[1].source)

    def test_exp_003a_notebook_document_is_ipynb_serializable(self):
        notebook = build_colab_runtime_bootstrap_notebook(
            project_root="/content/style-fit-profiler"
        )

        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["metadata"]["colab"]["name"], "style-fit-profiler-phase0.ipynb")
        self.assertEqual(len(notebook["cells"]), 2)
        json.dumps(notebook)

    def test_exp_003a_bootstrap_cells_do_not_embed_secret_values(self):
        notebook_text = json.dumps(
            build_colab_runtime_bootstrap_notebook(),
            ensure_ascii=False,
        )

        self.assertNotIn("GEMINI_API_KEY =", notebook_text)
        self.assertNotIn("<your key>", notebook_text)

    def test_exp_003a_notebook_cell_serializes_to_colab_code_cell(self):
        cell = NotebookCell(
            name="runtime-setup",
            source="print('ready')",
        )

        self.assertEqual(
            cell.to_ipynb_cell(),
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"id": "runtime-setup"},
                "outputs": [],
                "source": "print('ready')",
            },
        )


if __name__ == "__main__":
    unittest.main()
