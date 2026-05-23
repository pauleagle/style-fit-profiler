"""Notebook helper builders for experimental Phase 0 Colab flows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


DEFAULT_COLAB_PROJECT_ROOT = "/content/style-fit-profiler"
DEFAULT_COLAB_RUN_ID = "colab-phase0"
DEFAULT_COLAB_NOTEBOOK_NAME = "style-fit-profiler-phase0.ipynb"


@dataclass(frozen=True)
class NotebookCell:
    """Small dependency-free representation of a generated notebook cell."""

    name: str
    source: str
    cell_type: Literal["code", "markdown"] = "code"

    def to_ipynb_cell(self) -> dict[str, Any]:
        if self.cell_type == "code":
            return {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"id": self.name},
                "outputs": [],
                "source": self.source,
            }

        return {
            "cell_type": "markdown",
            "metadata": {"id": self.name},
            "source": self.source,
        }


def build_colab_runtime_bootstrap_cells(
    *,
    project_root: str = DEFAULT_COLAB_PROJECT_ROOT,
    run_id: str = DEFAULT_COLAB_RUN_ID,
) -> tuple[NotebookCell, ...]:
    """Build EXP-003A Colab runtime setup and dependency initialization cells."""

    project_root_literal = json.dumps(project_root)
    run_id_literal = json.dumps(run_id)
    runtime_setup_source = f"""from pathlib import Path
import os
import sys

PROJECT_ROOT = Path({project_root_literal})
SRC_DIR = PROJECT_ROOT / "src"
REFERENCE_IMAGE_DIR = PROJECT_ROOT / "reference_images"
RUN_DIR = PROJECT_ROOT / "runs" / {run_id_literal}

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REFERENCE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)

print(f"Project root: {{PROJECT_ROOT}}")
print(f"Reference image dir: {{REFERENCE_IMAGE_DIR}}")
print(f"Run dir: {{RUN_DIR}}")
"""
    dependency_check_source = """import importlib.util

required_modules = ("style_fit_profiler",)
missing_modules = [
    module_name
    for module_name in required_modules
    if importlib.util.find_spec(module_name) is None
]

if missing_modules:
    raise RuntimeError(
        "Missing notebook dependencies: " + ", ".join(missing_modules)
    )

print("Notebook runtime dependencies are ready.")
"""

    return (
        NotebookCell(name="runtime-setup", source=runtime_setup_source),
        NotebookCell(name="dependency-check", source=dependency_check_source),
    )


def build_colab_runtime_bootstrap_notebook(
    *,
    project_root: str = DEFAULT_COLAB_PROJECT_ROOT,
    run_id: str = DEFAULT_COLAB_RUN_ID,
    notebook_name: str = DEFAULT_COLAB_NOTEBOOK_NAME,
) -> dict[str, Any]:
    """Build a minimal EXP-003A ipynb document for the runtime bootstrap cells."""

    return {
        "cells": [
            cell.to_ipynb_cell()
            for cell in build_colab_runtime_bootstrap_cells(
                project_root=project_root,
                run_id=run_id,
            )
        ],
        "metadata": {
            "colab": {"name": notebook_name},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
