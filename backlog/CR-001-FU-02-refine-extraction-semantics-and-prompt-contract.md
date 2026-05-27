# CR-001-FU-02 Refine extraction semantics and prompt contract

## Metadata

```yaml
item_id: CR-001-FU-02
item_type: follow-up
parent_cr: CR-001
title: Refine extraction semantics and prompt contract
status: proposed
scope: prompt-semantics
affected_area:
  - cr001-extraction-prompt
  - allele-registry-semantics
  - output-stability
  - batch-response-comparison
  - model-comparison
  - semantic-calibration-loop
  - devils-advocate-review
  - minimal-validation-cleanup
current_extractor_models:
  - gemini-2.5-flash
  - gemini-3.5-flash
production_model_default: gemini-2.5-flash
calibration_models:
  - gemini-2.5-flash
  - gemini-3.5-flash
refinement_type: da-driven-prompt-refinement
calibration_strategy: dual-model-batch-semantic-comparison
review_strategy: devils-advocate-strict-review
schema_policy: no-breaking-schema-change
code_change_policy: prompt-first-minimal-validation-only
provider_policy: gemini-only-for-this-follow-up
related_future_followups:
  - CR-001-FU-03 Add multi-provider vision model adapter layer
```

## Summary

CR-001 native artifact is already usable as the Phase 0 primary baseline.

The current problem is not that the program cannot produce JSON. The current problem is that different model runs may produce structurally valid JSON with different semantic interpretations.

This follow-up defines a narrow refinement loop:

```text
fixed reference image set
  -> run gemini-2.5-flash batch extraction
  -> run gemini-3.5-flash batch extraction
  -> compare the two batch responses field by field
  -> run Devil's Advocate review against both outputs
  -> derive prompt contract corrections
  -> change only the CR-001 extraction prompt by default
  -> rerun the same batch
  -> check whether semantic drift decreases
```

CR-001-FU-02 is primarily a prompt semantics item.

Code changes are allowed only when they externalize existing magic values, add deterministic validation, or make the DA comparison loop repeatable. It must not become a provider abstraction, schema redesign, or pipeline rewrite.

## Background

Observed current state:

- CR-001 native artifact structure is stable enough for review.
- Batch response files can be produced by multiple Gemini models.
- Both `gemini-2.5-flash` and `gemini-3.5-flash` can produce `cr001.v1`-shaped output.
- The main instability is semantic, not structural.
- The largest observed disagreements are around style category, saturation, facial expression, clothing semantics, and color impression.

Working conclusion:

> 程式架構穩了，但是抽取用的 prompt 和給定的關鍵字還需要精修。

Updated FU-02 interpretation:

> FU-02 should run DA over two model batch responses, refine only the prompt contract by default, then rerun the next round. Code changes are allowed only for small validation/config cleanup when hardcoded assumptions block repeatable review.

## Decision

Use the following classification:

```yaml
item_type: follow-up
parent_cr: CR-001
refinement_type: da-driven-prompt-refinement
schema_policy: no-breaking-schema-change
code_change_policy: prompt-first-minimal-validation-only
provider_policy: gemini-only-for-this-follow-up
```

Meaning:

- CR-001 remains the parent change request.
- FU-02 improves how CR-001 asks models to observe and classify images.
- The artifact schema remains unchanged.
- The default implementation path is prompt-only.
- Minor code cleanup is allowed only if it supports validation, repeatability, or externalization of magic values.
- Multi-provider support is explicitly deferred to CR-001-FU-03 or another future item.

## Scope boundary

### In scope

- Refine CR-001 extraction prompt.
- Clarify field-level semantics.
- Clarify tag selection rules.
- Clarify intensity scoring rules.
- Clarify conflict and coexistence rules between tags.
- Clarify `impression_colors.main`, `secondary`, and `accent` semantics.
- Compare `gemini-2.5-flash` and `gemini-3.5-flash` batch responses.
- Use Devil's Advocate review to challenge both model outputs.
- Record prompt contract updates from DA findings.
- Add minimal deterministic validation when needed.
- Externalize hardcoded expected lists if they are blocking review repeatability.

### Out of scope

- OpenAI / Claude / Mistral provider adapter.
- Generic `VisionProvider` architecture.
- Request body abstraction across vendors.
- Response normalization framework for all providers.
- CR-001 native schema redesign.
- Required top-level field changes.
- Registry taxonomy redesign.
- Phase 0 projection compatibility output.
- Formal LLM-as-judge automation.
- Large golden dataset architecture.
- Downstream Phase 1 / Phase 2 scoring redesign.

## Core problem

A CR-001 artifact can be schema-valid but semantically wrong.

Typical risks:

- `vibrant-high-saturation` may be selected only because the image contains pink, red, or blue accents.
- `cel-shading` may be selected only because the image is anime-style.
- `anime-heavy-paint` and `semi-realistic-anime` may be used interchangeably without a clear boundary.
- `warm-smile` may be selected because the character has blush, even when the mouth and eyes do not support a smile.
- `impression_colors.main` may switch between largest area color, clothing color, and strongest memory color.
- A stronger model may produce more nuanced but less grounded interpretation.
- A cheaper model may produce simpler but sometimes more stable interpretation.
- Both models may agree because the prompt is leading.

FU-02 exists to convert these observations into prompt contract rules.

## FU-02 execution model

### Round loop

```text
Round N
  1. Freeze the reference image set.
  2. Freeze the CR-001 schema and registry version.
  3. Run gemini-2.5-flash batch extraction.
  4. Run gemini-3.5-flash batch extraction.
  5. Compare outputs field by field.
  6. Run Devil's Advocate review.
  7. Classify disagreements.
  8. Produce prompt-only correction notes.
  9. Update the extraction prompt.
  10. Rerun the same images in Round N+1.
```

### Round input

```yaml
round_input:
  reference_images:
    - reference_images/ref-001.png
    - reference_images/ref-002.png
    - reference_images/ref-003.png
    - reference_images/ref-004.png
  model_outputs:
    - cr001_reference_image_analysis-gemini-2.5-flash.json
    - cr001_reference_image_analysis-gemini-3.5-flash.json
  current_prompt: current CR-001 extraction prompt
  registry: current CR-001 allele registry
```

### Round output

```yaml
round_output:
  da_comparison_note: required
  prompt_contract_updates: required
  registry_questions: optional
  code_cleanup_questions: optional
  next_round_focus: required
```

## Code change policy

FU-02 is prompt-first.

Code changes are allowed only when they satisfy all of the following:

1. They do not change the CR-001 native artifact schema.
2. They do not introduce new provider architecture.
3. They do not change the main CR-001 pipeline lifecycle.
4. They improve validation, repeatability, or reviewability.
5. They externalize an existing hardcoded assumption rather than introduce new behavior.

Allowed code cleanup examples:

```text
- move allowed gene lists from hardcoded arrays into registry/config
- move expected model names from magic strings into config
- compute expected image count from input images instead of hardcoded 4
- centralize schema_version as a constant
- centralize output filename pattern if currently duplicated
- validate selected/intensity length equality
- validate intensity range is 0.0 to 1.0
- validate selected tokens exist in registry
- validate impression_colors are legal #RRGGBB hex strings
- validate source_image paths correspond to input image list
```

Disallowed FU-02 code changes:

```text
- add OpenAI / Claude / Mistral support
- create generic provider adapter
- redesign request/response abstraction
- add cross-provider raw response normalization
- add new CR-001 schema fields
- rename existing artifact fields
- rewrite registry taxonomy
- add Phase 0 projection compatibility output
```

## Devil's Advocate review role

The DA reviewer must not pick a winner by default.

The DA reviewer must challenge both outputs and ask:

- Which selected tags are visually grounded?
- Which selected tags are plausible but unsupported?
- Which fields contain content that belongs elsewhere?
- Which model is over-generalizing?
- Which model is over-infering?
- Which model is under-describing important visual signals?
- Which disagreement is caused by prompt ambiguity?
- Which disagreement is caused by registry ambiguity?
- Which disagreement requires human preference?
- Which disagreement can be fixed by prompt wording alone?

DA rules:

```text
Do not assume gemini-3.5-flash is correct because it is stronger.
Do not assume gemini-2.5-flash is wrong because it is lighter.
Do not accept agreement as proof.
Do not reward fluent summaries unless visually grounded.
Do not allow unsupported character lore or symbolic inference.
Do not treat schema-valid JSON as semantically valid.
Prefer prompt fixes before registry changes.
Prefer registry clarification before schema changes.
Escalate to human decision when multiple interpretations are valid.
```

## DA review artifact

Recommended review structure:

```json
{
  "schema_version": "cr001_da_review.v1",
  "round_id": "CR-001-FU-02-R1",
  "reference_set": "refset-001",
  "models_compared": [
    "gemini-2.5-flash",
    "gemini-3.5-flash"
  ],
  "stable_consensus_genes": [],
  "disputed_genes": [
    {
      "source_image": "reference_images/ref-002.png",
      "field_path": "expected_style_genes.saturation",
      "model_a": {
        "model": "gemini-2.5-flash",
        "selected": ["vibrant-high-saturation"]
      },
      "model_b": {
        "model": "gemini-3.5-flash",
        "selected": ["muted-low-saturation", "pastel-tones"]
      },
      "da_assessment": "model_b_more_visually_grounded",
      "recommended_action": "revise_prompt",
      "prompt_contract_update": "Do not select vibrant-high-saturation only because an image contains pink, red, or blue accents. Judge the overall palette intensity, contrast, and visual stimulation."
    }
  ],
  "likely_misclassifications": [],
  "prompt_contract_updates": [],
  "registry_questions": [],
  "code_cleanup_questions": [],
  "next_round_focus": []
}
```

## Semantic diff categories

Use these labels when comparing the two batch outputs.

```text
agreement
  The two models select essentially the same meaning.

acceptable_variation
  The words differ but the CR-001 meaning remains close enough.

semantic_drift
  The extracted meaning changes materially.

allele_mismatch
  Different selected tokens imply different visual judgments.

field_boundary_violation
  Content belongs in another field.

unsupported_inference
  The model invents personality, story, symbolism, or intent not supported by the image.

missing_salient_feature
  A clearly visible or important appeal/style factor is omitted.

over_specific_detail
  The output captures a one-off detail that is not reusable as a style gene.

generic_but_true
  The output is visually true but too generic to help generation, comparison, or recombination.

prompt_leakage
  The model appears to select a token because the prompt wording led it there.

registry_ambiguity
  The registry token boundary is not clear enough for stable selection.

needs_human_preference
  Multiple interpretations are valid and the project owner must choose the preferred convention.
```

## Prompt contract updates from current observation

### 1. Saturation rules

Problem observed:

- One model may classify a soft or pastel image as `vibrant-high-saturation` because it contains pink, red, or blue accents.

Prompt rule:

```text
Do not classify an image as vibrant-high-saturation only because it contains pink, red, or blue accents.
Judge the overall palette.
Prefer pastel-tones when the image is soft, high-key, gentle, low-contrast, or dominated by light color transitions.
Prefer muted-low-saturation when grey, beige, desaturated hair, desaturated clothing, or low-chroma surfaces dominate the visual impression.
Use vibrant-high-saturation only when the overall image has strong chroma, strong visual stimulation, or clearly saturated dominant colors.
```

Coexistence rule:

```text
pastel-tones may coexist with low or moderate vibrant-high-saturation only when the image is mostly pastel but contains a clearly saturated accent.
muted-low-saturation and high-intensity vibrant-high-saturation should not coexist unless the image has a clear split palette and the reason is visible.
```

### 2. Genre rules

Problem observed:

- `anime-heavy-paint`, `semi-realistic-anime`, and `cel-shading` can be selected inconsistently.

Prompt rule:

```text
Use semi-realistic-anime when the face remains anime-stylized but lighting, hair rendering, clothing volume, material treatment, or proportions are more polished and semi-realistic than flat anime rendering.
Use anime-heavy-paint when painterly rendering, layered shading, or heavy illustration treatment is a major part of the style impression.
Use cel-shading only when there are clear hard-edged shadow regions or anime-cell-like shadow boundaries.
Do not select cel-shading merely because the image is anime-style.
```

### 3. Line art rules

Prompt rule:

```text
Use clean-line-art when outlines are controlled, readable, and mostly free of sketch noise.
Use colored-line-art when line color visibly blends with local object colors or is not pure black/neutral.
Do not select colored-line-art only because the image has colored objects; the line itself must appear colored or softened into the color palette.
```

### 4. Brush and shading rules

Prompt rule:

```text
Use smooth-airbrush when shadows and blush are softly blended with gradual transitions.
Use soft-gradient when larger surfaces transition gradually between light and shadow or between nearby colors.
Use hard-edge-shadow only when visible shadow boundaries are crisp enough to affect the rendering style.
Do not select hard-edge-shadow just because some object edges are sharp.
```

### 5. Facial expression rules

Problem observed:

- `warm-smile` may be selected when the character merely has blush or friendly facial design.

Prompt rule:

```text
Do not select warm-smile unless the mouth shape, cheek expression, or eye expression visibly supports a smile.
Blush alone is not a smile.
Large eyes alone are not emotional warmth.
Use neutral-stare when the mouth is relaxed or closed and the expression is calm, quiet, or emotionally restrained.
Use soft-blush-cheeks only for visible cheek blush or warm cheek coloring; do not use it as a proxy for personality.
```

### 6. Body type and proportion rules

Prompt rule:

```text
Use body_type only for visible body proportion and silhouette cues.
Do not infer body type from clothing genre alone.
Do not overstate body type when the image is cropped or the body is not clearly visible.
Prefer lower intensity when the visible evidence is partial.
```

### 7. Clothing genre and fit rules

Prompt rule:

```text
Use clothing_genre for recognizable outfit category.
Use clothing_fit for silhouette and fit behavior.
Do not mix clothing genre with art style.
Do not infer personality or story from clothing genre.
For school uniforms, distinguish classic-sailor-fuku from broader japanese-school-uniform when the sailor collar and traditional sailor structure are clearly visible.
Use modern-casualwear for everyday non-uniform clothing.
Use oversized-fit only when garment volume or looseness is visibly part of the silhouette.
```

### 8. Impression color rules

Problem observed:

- `main` may alternate between largest area color, clothing color, or strongest memory color.

Prompt rule:

```text
impression_colors.main should be the most dominant visual impression color for the image or character design.
impression_colors.secondary should be the strongest supporting palette color.
impression_colors.accent should be a smaller but memorable focus color.
Do not use symbolic colors that are not visible.
Do not treat background color as main unless it strongly dominates the visual impression.
When area dominance and character memorability conflict, prefer the color most important for recreating the character/style impression and mention ambiguity in review notes if needed.
```

Future note:

```text
Palette extraction may later be added for cross-validation, but FU-02 keeps impression color as prompt-level semantic judgment unless repeated instability requires a separate follow-up.
```

## Field boundary rules

| Field | Should contain | Should not contain |
| --- | --- | --- |
| `expected_style_genes` | reusable art style, rendering, lighting, texture, color treatment | personality, story, clothing category by itself |
| `character_appeal_genes` | visible facial appeal, silhouette, clothing appeal, character design cues | pure rendering style only, unsupported personality |
| `impression_colors` | visible or strongly perceived palette colors | symbolic or invented colors |
| `cr001_summary` | concise human-readable synthesis | long reasoning, backstory, unsupported lore |

## Intensity scoring rules

Use intensity as visible support strength, not personal preference.

```text
1.0
  Dominant, unmistakable, and central to the image.

0.8 - 0.9
  Strongly visible and important, but not the only defining feature.

0.6 - 0.7
  Present and relevant, but secondary or partially visible.

0.4 - 0.5
  Weak, ambiguous, or only lightly supported.

Below 0.4
  Avoid selecting unless the schema requires a low-confidence marker.
```

Rules:

```text
Do not assign high intensity only because a token sounds plausible.
Do not assign 1.0 to multiple overlapping tags unless each is independently dominant.
Lower intensity when the image is cropped, ambiguous, or partially occluded.
When two tags overlap, prefer the more specific grounded tag and lower or omit the broader one.
```

## Registry refinement policy

FU-02 may identify registry ambiguity, but it should not redesign the registry by default.

Allowed registry updates:

```text
- add lightweight definitions for frequently confused tokens
- add avoid_confusing_with notes
- add selection examples for existing tokens
- mark unresolved token boundary questions
```

Avoid in FU-02:

```text
- large taxonomy rewrite
- mass renaming
- changing output schema to fit new taxonomy
- adding many new tokens before prompt rules are tested
```

Recommended lightweight registry definition format:

```yaml
vibrant-high-saturation:
  zh: 高彩度鮮明色彩
  en: Vibrant high saturation
  meaning: Overall palette has strong chroma and strong visual stimulation.
  select_when:
    - dominant colors are clearly saturated
    - the image feels vivid rather than soft or muted
  avoid_confusing_with:
    - pastel-tones
    - muted-low-saturation
  do_not_select_when:
    - only small accents are saturated
    - the image is mostly soft, pale, grey, or low-contrast
```

## Manual review rubric

### A. Style gene correctness

Questions:

- Are selected style genes visibly supported by the image?
- Are selected tokens reusable for future generation or comparison?
- Are selected tokens too generic?
- Are selected tokens selected only because they sound plausible?
- Did the two Gemini outputs agree on major style categories?
- Did DA identify unsupported or overconfident style tokens?

Result:

```text
stable / partially_stable / unstable
```

### B. Appeal point correctness

Questions:

- Does the output capture why the image is visually attractive or memorable?
- Does it separate character appeal from rendering style?
- Does it avoid inventing personality or backstory?
- Does either model omit important visual appeal points?
- Does either model overstate expression, body type, or clothing meaning?

Result:

```text
stable / partially_stable / unstable
```

### C. Color impression correctness

Questions:

- Are colors actually visible or strongly perceived?
- Does `main` mean the same thing across models?
- Are colors too symbolic or unsupported?
- Is instability caused by prompt ambiguity or actual palette ambiguity?
- Should the case be flagged for future palette extraction?

Result:

```text
model_ok / needs_prompt_rule / needs_palette_validation / needs_human_preference
```

### D. Batch consistency

Questions:

- Does batch output preserve the same major semantic interpretation across models?
- Are differences only wording-level, or do they change the extracted meaning?
- Does the same image receive stable major categories after prompt revision?

Result:

```text
consistent / minor_drift / major_drift
```

### E. DA conclusion

Questions:

- What is the strongest argument that the 2.5 output is wrong?
- What is the strongest argument that the 3.5 output is wrong?
- What did both models miss?
- What did both models overstate?
- Which disagreement requires human decision?
- Which disagreement can be fixed by prompt wording?

Result:

```text
accept / revise_prompt / revise_registry / needs_human_decision / defer_to_future_followup
```

## Suggested implementation checklist

### Prompt refinement

- [ ] Review current CR-001 extraction prompt.
- [ ] Add explicit field definitions.
- [ ] Add field boundary rules.
- [ ] Add saturation selection rules.
- [ ] Add genre selection rules.
- [ ] Add expression selection rules.
- [ ] Add impression color semantics.
- [ ] Add intensity scoring rules.
- [ ] Add uncertainty handling rules.
- [ ] Add unsupported inference prohibition.
- [ ] Add conflict/coexistence guidance for overlapping tags.

### DA comparison loop

- [ ] Select fixed reference image set for FU-02 round 1.
- [ ] Run `gemini-2.5-flash` batch extraction.
- [ ] Run `gemini-3.5-flash` batch extraction.
- [ ] Compare outputs field by field.
- [ ] Classify each major difference using semantic diff categories.
- [ ] Run DA review against both outputs.
- [ ] Record prompt contract updates.
- [ ] Rerun same batch after prompt revision.
- [ ] Compare whether major semantic drift decreases.

### Minimal validation cleanup

- [ ] Check whether allowed gene lists are hardcoded in code.
- [ ] Externalize hardcoded allowed lists to registry/config if needed.
- [ ] Check whether expected input image count is hardcoded.
- [ ] Replace hardcoded image count with input list length if needed.
- [ ] Validate selected/intensity length equality.
- [ ] Validate intensity range.
- [ ] Validate selected tags against registry.
- [ ] Validate `impression_colors` hex format.
- [ ] Validate `source_image` paths against input images.

### Documentation

- [ ] Record FU-02 round notes.
- [ ] Record known stable genes.
- [ ] Record disputed genes.
- [ ] Record unresolved human preference decisions.
- [ ] Link FU-02 from CR-001 follow-up list.
- [ ] Defer provider adapter discussion to FU-03.

## Acceptance criteria

- CR-001 extraction prompt clearly defines each output field.
- Prompt rules distinguish visual observation, reusable style gene, character appeal, impression color, and generation guidance.
- Prompt rules explicitly address saturation, genre, facial expression, clothing fit, and impression color ambiguity.
- `gemini-2.5-flash` and `gemini-3.5-flash` batch outputs can be compared using a stable DA review format.
- DA review produces actionable prompt contract updates.
- At least one rerun is performed after prompt update.
- Semantic drift is reduced or clearly classified as registry ambiguity / human preference / future follow-up.
- CR-001 native artifact schema remains unchanged.
- Any code changes are limited to deterministic validation or externalization of hardcoded assumptions.
- No multi-provider adapter work is introduced in FU-02.

## Open questions

### 1. Should `impression_colors` use LLM judgment or palette extraction?

Suggested default:

```text
Use LLM judgment for FU-02 prompt semantics.
Flag unstable cases for future palette extraction or cross-validation.
Do not add image-processing palette extraction inside FU-02 unless repeated instability blocks progress.
```

### 2. Should registry definitions be expanded now?

Suggested default:

```text
Only expand definitions for high-impact and frequently confused tokens.
Do not perform a full registry taxonomy rewrite in FU-02.
```

### 3. Should gemini-3.5-flash replace gemini-2.5-flash as production default?

Suggested default:

```text
No. Use gemini-3.5-flash as calibration/reference output for FU-02.
Keep gemini-2.5-flash as production default unless repeated test data proves otherwise.
```

### 4. Should non-Gemini models be added now?

Suggested default:

```text
No. Non-Gemini models require provider adapter and response normalization design.
Track that as CR-001-FU-03 or another dedicated follow-up.
```

### 5. When should FU-02 escalate to schema change?

Suggested default:

```text
Only escalate if multiple prompt rounds prove that the current schema cannot express the needed distinction.
Schema change must be proposed explicitly and should not be slipped into FU-02.
```

## Future follow-up boundary

### CR-001-FU-03 candidate

```text
CR-001-FU-03 Add multi-provider vision model adapter layer
```

Purpose:

```text
Support Gemini, OpenAI, Claude, Mistral, or other vision-capable providers through a provider adapter boundary, raw response capture, response normalization, and provider-aware config.
```

FU-02 should not implement this.

## Backlink to CR-001

Add or update the CR-001 follow-up section:

```md
## Follow-ups

- `CR-001-FU-02`: Refine extraction semantics and prompt contract.
  - Scope: DA-driven prompt refinement over dual Gemini batch responses.
  - Default change type: prompt-only.
  - Allowed code change: minimal validation/config cleanup only.
  - Explicitly deferred: multi-provider adapter and schema redesign.
```

## Playbook lesson

Future CR work should distinguish these layers:

```text
Code structure is stable.
Artifact shape is stable.
Extraction semantics are stable.
Model outputs are mutually consistent.
DA review has challenged the assumptions.
Human expectation is satisfied.
```

These are different levels of correctness.

Key rules:

> A JSON artifact can be schema-valid but semantically wrong.
>
> Agreement between two models is useful evidence, not proof.
>
> A stronger model can be more detailed and still be less grounded.
>
> A lighter model can be correct if the prompt contract is clear enough.
>
> Devil's Advocate review should challenge both outputs before human accepts a semantic baseline.
>
> FU-02 should refine the prompt contract first; provider architecture belongs in FU-03.
