from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from style_fit_profiler import cr001  # noqa: E402
from style_fit_profiler.cr001 import (  # noqa: E402
    CR001_ALLELE_REGISTRY,
    CR001_CHARACTER_APPEAL_LOCI,
    CR001_EXPECTED_STYLE_LOCI,
    build_cr001_gemini_prompt,
)


class CR001GeminiPromptContractTests(unittest.TestCase):
    def test_cr001_06a_prompt_includes_all_canonical_registry_tokens(self):
        prompt = build_cr001_gemini_prompt()

        for locus, alleles in CR001_ALLELE_REGISTRY.items():
            with self.subTest(locus=locus):
                self.assertIn(f'"{locus}"', prompt)
                for allele in alleles:
                    self.assertIn(f'"{allele}"', prompt)

    def test_cr001_06a_prompt_is_generated_from_live_registry(self):
        original_genre_alleles = cr001.CR001_ALLELE_REGISTRY["genre"]
        cr001.CR001_ALLELE_REGISTRY["genre"] = original_genre_alleles + (
            "test-only-sentinel-style",
        )
        try:
            prompt = build_cr001_gemini_prompt()
        finally:
            cr001.CR001_ALLELE_REGISTRY["genre"] = original_genre_alleles

        self.assertIn('"test-only-sentinel-style"', prompt)

    def test_cr001_06a_prompt_groups_required_v1_loci(self):
        prompt = build_cr001_gemini_prompt()

        self.assertIn("expected_style_genes", prompt)
        self.assertIn("character_appeal_genes", prompt)
        for locus in CR001_EXPECTED_STYLE_LOCI:
            self.assertLess(prompt.index("expected_style_genes"), prompt.index(f'"{locus}"'))
        for locus in CR001_CHARACTER_APPEAL_LOCI:
            self.assertLess(
                prompt.index("character_appeal_genes"),
                prompt.index(f'"{locus}"'),
            )

    def test_cr001_06a_prompt_forbids_free_form_alleles_and_extra_keys(self):
        prompt = build_cr001_gemini_prompt()

        self.assertIn("Do not invent allele names", prompt)
        self.assertIn("Return JSON only", prompt)
        self.assertIn("Do not include source_image", prompt)
        self.assertIn("Do not include schema_version", prompt)
        self.assertNotIn("composition", prompt)
        self.assertNotIn("mood_atmosphere", prompt)
        self.assertNotIn("appeal_archetype", prompt)

    def test_cr001_06a_prompt_describes_optional_palette_without_registry_drift(self):
        prompt = build_cr001_gemini_prompt()

        self.assertIn("impression_colors", prompt)
        self.assertIn("optional", prompt)
        self.assertIn("uppercase #RRGGBB", prompt)
        self.assertIn('"main"', prompt)
        self.assertIn('"secondary"', prompt)
        self.assertIn('"accent"', prompt)
        self.assertNotIn('"impression_colors": { "selected"', prompt)

    def test_cr001_06a_prompt_can_include_source_label_for_manual_review_context(self):
        prompt = build_cr001_gemini_prompt(
            source_image_label="reference_images/ref-001.png"
        )

        self.assertIn("reference_images/ref-001.png", prompt)
        self.assertIn("The caller will attach exactly one reference image", prompt)


if __name__ == "__main__":
    unittest.main()
