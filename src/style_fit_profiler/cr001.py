"""CR-001 appeal point and art style extraction contracts."""

from __future__ import annotations


CR001_EXPECTED_STYLE_LOCI = (
    "genre",
    "line_art",
    "brush_shading",
    "saturation",
    "lighting",
    "texture",
)
CR001_CHARACTER_APPEAL_LOCI = (
    "facial_features",
    "body_type",
    "clothing_genre",
    "clothing_fit",
)
CR001_CANONICAL_LOCI = CR001_EXPECTED_STYLE_LOCI + CR001_CHARACTER_APPEAL_LOCI

CR001_ALLELE_REGISTRY = {
    "genre": (
        "cel-shading",
        "anime-heavy-paint",
        "semi-realistic-anime",
        "flat-illustration",
        "2D-pop-art",
        "vintage-manga",
        "watercolor-anime",
        "oil-painterly",
    ),
    "line_art": (
        "clean-line-art",
        "sketchy-lines",
        "dynamic-linework",
        "thick-contours",
        "lineless",
        "colored-line-art",
        "soft-pencil-sketch",
    ),
    "brush_shading": (
        "smooth-airbrush",
        "hard-edge-shadow",
        "textured-brush",
        "impasto-stroke",
        "soft-gradient",
        "cross-hatching",
        "halftone-dot",
    ),
    "saturation": (
        "vibrant-high-saturation",
        "pastel-tones",
        "muted-low-saturation",
        "morandi-palette",
        "monochrome",
        "neon-fluorescent",
    ),
    "lighting": (
        "bright-ambient",
        "high-contrast-chiaroscuro",
        "rim-lighting",
        "soft-volumetric-light",
        "cinematic-backlight",
        "overcast-diffused",
    ),
    "texture": (
        "clean-digital-canvas",
        "grainy-paper",
        "canvas-texture",
        "watercolor-bleed",
        "vintage-film-grain",
        "noise-artifacts",
    ),
    "facial_features": (
        "large-expressive-eyes",
        "tsundere-eyes",
        "soft-blush-cheeks",
        "sharp-jawline",
        "prominent-eyelashes",
        "detailed-hair-highlights",
        "warm-smile",
        "neutral-stare",
    ),
    "body_type": (
        "slender-build",
        "athletic-toned",
        "hourglass-silhouette",
        "petite-proportion",
        "stylized-chibi",
        "realistic-anatomy",
        "elongated-limbs",
    ),
    "clothing_genre": (
        "japanese-school-uniform",
        "classic-sailor-fuku",
        "techwear-futuristic",
        "gothic-lolita",
        "modern-casualwear",
        "fantasy-armor",
        "traditional-kimono",
        "cyberpunk-gear",
    ),
    "clothing_fit": (
        "oversized-fit",
        "tailored-slim-fit",
        "pleated-silhouette",
        "high-waist-cut",
        "asymmetric-layering",
        "puff-sleeves",
        "structural-drapery",
    ),
}
