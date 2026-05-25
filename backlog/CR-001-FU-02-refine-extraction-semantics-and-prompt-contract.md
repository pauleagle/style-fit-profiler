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
  - allele-registry
  - output-stability
  - batch-single-consistency
  - model-comparison
  - semantic-calibration-loop
  - devils-advocate-review
  - manual-review-workflow
current_extractor_model: gemini-2.5-flash
refinement_type: semantic-calibration
schema_policy: no-breaking-schema-change-by-default
production_model_default: gemini-2.5-flash
calibration_strategy: dual-model-semantic-comparison
review_strategy: devils-advocate-strict-review
```

## Summary

CR-001 native artifact has become the Phase 0 primary baseline.

After the initial CR-001 implementation, the program structure and artifact flow are mostly stable, but the extraction quality still depends heavily on prompt wording, semantic definitions, allowed keywords, model capability, and model interpretation.

This follow-up focuses on refining the extraction semantics and prompt contract so that CR-001 output becomes more stable, reusable, and aligned with human expectations.

The intended calibration strategy is:

```text
single reference image
  -> large model CR-001 extraction
  -> gemini-2.5-flash CR-001 extraction
  -> semantic comparison
  -> Devil's Advocate strict review
  -> human analysis
  -> refine prompt / allele registry / field rules
  -> rerun
  -> loop until stable enough
```

This is a semantic calibration loop, not the default high-volume extraction path.

## Background

Observed current state:

- The CR-001 native artifact structure is usable.
- Batch and single entrypoints can produce CR-001-shaped output.
- However, the actual extracted meaning may still drift depending on:
  - prompt wording
  - reference image ambiguity
  - unclear allele definitions
  - overlapping keyword meanings
  - insufficient distinction between art style, appeal point, character traits, and impression colors
  - batch vs single invocation differences
  - model capability differences
  - insufficient adversarial review

Current extractor model:

```json
{
  "model": "gemini-2.5-flash"
}
```

User summary:

> 程式架構穩了，但是抽取用的 prompt 和給定的關鍵字還需要精修。

Additional refinement insight:

> For selected calibration images, compare a large model and Flash output, then use Devil's Advocate review to strictly challenge both outputs before updating the prompt or registry.

This follow-up exists to turn that insight into an explicit refinement item instead of treating prompt quality as an informal future concern.

## Non-goals

This follow-up does not introduce a new CR-001 native schema unless unavoidable.

It should not become a new independent CR unless it changes one of the following:

- artifact contract
- required top-level fields
- Phase 0 lifecycle
- downstream Phase 1 / Phase 2 assumptions
- formal scoring / ranking subsystem
- automated judge framework
- formal golden dataset architecture

If the work remains focused on prompt wording, semantic definitions, examples, extraction stability, model comparison, and manual Devil's Advocate review, it should remain a CR-001 follow-up.

## Decision

Use the following classification:

```yaml
item_type: follow-up
parent_cr: CR-001
refinement_type: semantic-calibration
schema_policy: no-breaking-schema-change-by-default
production_model_default: gemini-2.5-flash
calibration_strategy: dual-model-semantic-comparison
review_strategy: devils-advocate-strict-review
```

Meaning:

- CR-001 remains the parent change request.
- This item refines how CR-001 extraction interprets images.
- The goal is to improve semantic stability without changing the primary artifact structure.
- `gemini-2.5-flash` remains a suitable default for high-volume Phase 0 extraction.
- A larger / stronger model may be used as a semantic calibration reference for selected single-image probes.
- Devil's Advocate review is used to challenge both model outputs, not to automatically declare one model correct.
- If schema changes become necessary, they must be explicitly proposed and reviewed.

## Core problem

The core risk is not whether the code can produce JSON.

The core risk is whether the extracted JSON means what the human expects it to mean.

Examples of semantic risks:

- `genre` and `brush_shading` may overlap in model interpretation.
- `character_appeal_genes` may mix visual charm, personality impression, and clothing details.
- `impression_colors` may be guessed from visual impression instead of observed palette.
- Style tokens may be selected because they sound plausible, not because they are visually grounded.
- Batch output may differ from single output for the same reference image.
- Flash output may be structurally valid but semantically less precise than a larger model.
- A larger model may over-infer personality, story, or symbolic meaning if the prompt is too open.
- Both models may agree on a plausible but unsupported interpretation.
- Human may over-trust the better-written output.
- Prompt may not clearly distinguish objective observation from reusable design intent.

## Model consideration

Current extractor model:

```json
{
  "model": "gemini-2.5-flash"
}
```

`gemini-2.5-flash` is suitable for high-volume, low-latency multimodal extraction, but extraction semantics may still require prompt calibration and human review.

Observed semantic drift should not be treated only as a code bug. It may also come from:

- lightweight / price-performance model behavior
- ambiguous prompt wording
- insufficient allele definitions
- batch vs single context differences
- image ambiguity
- field boundary confusion

Recommended strategy:

```text
High-volume Phase 0 extraction:
  gemini-2.5-flash

Selected semantic calibration:
  large model + gemini-2.5-flash + Devil's Advocate review + human decision

Future optional enhancement:
  Flash extraction + large model / judge review
```

## Dual-Model Semantic Calibration Loop

For selected reference images, run both:

- a high-capability model for semantic reference extraction
- `gemini-2.5-flash` for production-oriented extraction

Then compare the two outputs field by field.

The goal is not to force exact JSON equality, but to identify whether semantic differences come from:

- prompt ambiguity
- allele registry ambiguity
- model capability differences
- image ambiguity
- field boundary confusion
- unsupported inference
- overly broad field definitions
- insufficient examples

Calibration loop:

```text
reference image
  -> large model CR-001 extraction
  -> flash CR-001 extraction
  -> semantic diff
  -> Devil's Advocate strict review
  -> human review
  -> prompt / registry / field-boundary refinement
  -> rerun
```

Flash remains suitable for high-volume extraction, while the larger model is used as a semantic calibration reference, not necessarily as the production default.

## Devil's Advocate strict review

Devil's Advocate review should be applied after both model outputs are available.

The DA role is not to pick a winner by default.

The DA role is to aggressively challenge both outputs and identify why each answer may be wrong, overconfident, under-specified, or semantically misaligned with CR-001.

### DA review goals

The DA review should check:

- Are selected tokens visibly grounded in the image?
- Are any tokens merely plausible but unsupported?
- Did either model confuse art style with character appeal?
- Did either model invent personality, story, symbolic intent, or production context?
- Did either model overfit to a one-off detail?
- Did either model omit an obvious visual appeal point?
- Did either model select overly generic tokens?
- Did the two models agree only because the prompt is leading?
- Is the field definition too broad?
- Is the allele registry too ambiguous?
- Should this disagreement lead to prompt refinement, registry refinement, or human decision?

### DA review output format

Recommended DA review structure:

```json
{
  "schema_version": "cr001_da_review.v1",
  "source_image": "reference_images/ref-001.png",
  "review_target": {
    "large_model_output": "...",
    "flash_output": "..."
  },
  "field_reviews": {
    "expected_style_genes": {
      "large_model_risks": [],
      "flash_risks": [],
      "agreement_assessment": "agreement | partial_agreement | disagreement",
      "da_verdict": "accept | revise_prompt | revise_registry | needs_human_decision"
    },
    "character_appeal_genes": {
      "large_model_risks": [],
      "flash_risks": [],
      "agreement_assessment": "agreement | partial_agreement | disagreement",
      "da_verdict": "accept | revise_prompt | revise_registry | needs_human_decision"
    },
    "impression_colors": {
      "large_model_risks": [],
      "flash_risks": [],
      "agreement_assessment": "agreement | partial_agreement | disagreement",
      "da_verdict": "accept | revise_prompt | needs_palette_validation | needs_human_decision"
    }
  },
  "recommended_action": {
    "prompt_changes": [],
    "registry_changes": [],
    "schema_questions": [],
    "human_decisions_needed": []
  }
}
```

### DA review rules

The DA reviewer must follow these rules:

```text
Do not assume the larger model is correct.
Do not assume Flash is wrong because it is lighter.
Do not accept agreement as correctness.
Do not reward fluent explanations unless visually grounded.
Do not allow unsupported character lore or symbolic inference.
Do not treat schema-valid JSON as semantically valid.
Prefer small prompt / registry fixes before proposing schema changes.
Escalate to human decision when multiple interpretations are valid.
```

## Dual-model comparison rules

### Case 1: Flash and large model agree

Interpretation:

```text
Potentially high confidence, but not automatically correct.
```

DA challenge:

```text
Check whether both models were led by prompt wording.
Check whether the shared interpretation is visually grounded.
```

Action:

```text
If DA finds no major issue, consider using the result as a stable reviewed example.
```

### Case 2: Flash drifts, large model is more reasonable

Interpretation:

```text
Possible Flash sensitivity to prompt ambiguity or insufficient allele definitions.
```

DA challenge:

```text
Verify that the large model is not over-explaining or inventing unsupported nuance.
```

Action:

```text
Tighten prompt wording.
Clarify field boundaries.
Add allele definitions or examples.
Rerun Flash.
```

### Case 3: Flash is reasonable, large model over-expands

Interpretation:

```text
Prompt may be too open.
Large model may infer personality, story, or symbolic meaning beyond the image.
```

DA challenge:

```text
Identify which details are not visually grounded.
```

Action:

```text
Restrict unsupported inference.
Emphasize visible evidence.
Clarify that CR-001 is visual extraction, not character lore generation.
```

### Case 4: Both models are unstable

Interpretation:

```text
Image may be ambiguous, schema may be under-specified, or allele registry may be insufficient.
```

DA challenge:

```text
Identify whether the instability comes from input, prompt, registry, or field design.
```

Action:

```text
Review reference image suitability.
Add field definitions.
Add examples.
Consider splitting overloaded fields only if necessary.
```

### Case 5: Both models are reasonable but different

Interpretation:

```text
The field definition is too broad or allows multiple valid interpretations.
```

DA challenge:

```text
Frame the decision that human must make.
Do not force false consensus.
```

Action:

```text
Human decides preferred interpretation.
Record the decision as prompt contract or allele registry guidance.
```

## Semantic diff categories

When comparing large-model and Flash outputs, classify differences as one of the following:

```text
acceptable wording variation
  The words differ, but the meaning is close enough.

semantic drift
  The extracted meaning changes materially.

allele mismatch
  Different tokens are selected and imply different visual judgments.

field boundary violation
  Content belongs in another field.

unsupported inference
  The model invents personality, story, symbolism, or intent not supported by the image.

missing salient feature
  A clearly visible or important appeal/style factor is omitted.

over-specific detail
  The output captures one-off details that are not reusable style genes.

generic-but-true
  The output is visually true but too generic to help future generation or comparison.

legacy leakage
  Old Phase 0 three-aspect schema concepts leak into CR-001 native output.
```

## Required refinement areas

### 1. Prompt contract

The CR-001 extraction prompt should explicitly define:

- what each field means
- what each field must not include
- whether the field is visual observation, inferred appeal, or reusable generation guidance
- how many tokens are expected
- how confidence / intensity should be interpreted
- how to behave when the image is ambiguous
- how to avoid over-explaining or inventing traits
- how to handle model uncertainty
- how to avoid legacy Phase 0 schema leakage

Recommended distinction:

```text
Observed visual fact:
  What can be directly seen in the image.

Inferred appeal point:
  Why the image is visually attractive or memorable.

Reusable style gene:
  A compact token useful for future generation, comparison, or recombination.

Impression color:
  Dominant or memorable color impression, preferably grounded in the visible image.

Generation guidance:
  A reusable instruction for future image generation, not a backstory.
```

### 2. Allele registry semantics

Each allele token should have at least a lightweight definition.

For example:

```yaml
clean-line-art:
  zh: 乾淨線稿
  en: Clean line art
  meaning: Clear, controlled, readable outlines with minimal sketch noise.
  avoid_confusing_with:
    - thick-contours
    - sketchy-lines

smooth-airbrush:
  zh: 平滑噴槍陰影
  en: Smooth airbrush shading
  meaning: Soft, blended shading with gradual transitions.
  avoid_confusing_with:
    - soft-gradient
    - textured-brush
```

The goal is not to over-document every token immediately, but to prevent ambiguous tokens from being selected inconsistently.

Start with:

- high-impact tokens
- frequently selected tokens
- frequently confused tokens
- tokens used in golden / reviewed examples
- tokens repeatedly challenged by DA review

### 3. Field boundary rules

The prompt should clearly separate the following:

| Field | Should contain | Should not contain |
| --- | --- | --- |
| `expected_style_genes` | reusable art style / rendering genes | character-specific personality or story |
| `character_appeal_genes` | visual charm and appeal factors | generic art style tokens only |
| `impression_colors` | visible or strongly perceived color impressions | unsupported symbolic colors |
| `cr001_summary` | concise human-readable synthesis | long reasoning or invented backstory |

### 4. Batch / single consistency

For the same image, single-image and batch extraction should produce semantically close results.

Exact JSON equality is not required, but major semantic categories should be stable.

Stability should be evaluated across:

- selected style gene categories
- top visual appeal points
- color impression
- summary wording
- absence of old Phase 0 schema leakage
- model-specific semantic drift

### 5. Reference image guidance

Reference image selection should be documented because CR-001 output depends heavily on input quality.

Recommended guidance:

- Use images that clearly show the target visual style.
- Avoid overly cropped images if clothing / pose / palette matters.
- Avoid mixed-style collages unless the goal is to extract mixed style.
- Prefer images with stable lighting and readable line / shading treatment.
- If the goal is character appeal, provide full or half-body images when possible.
- If the goal is art style extraction, avoid images where style is dominated by compression artifacts, filters, or screenshots.
- Use multiple references when trying to separate stable style genes from one-off character details.
- Use selected single-image references for dual-model semantic calibration before large batch extraction.

### 6. Manual review loop

CR-001 should support a human review loop:

```text
image
  -> CR-001 extraction
  -> human review
  -> mark stable / unstable fields
  -> refine prompt or allele definitions
  -> rerun same image
  -> compare drift
```

For calibration images, extend the loop:

```text
image
  -> large model extraction
  -> Flash extraction
  -> semantic diff
  -> Devil's Advocate review
  -> human review
  -> refine prompt / registry
  -> rerun both models
```

The review should distinguish:

- acceptable wording variation
- semantic drift
- incorrect allele selection
- missing appeal points
- over-specific character detail
- unsupported inference
- model capability difference
- prompt ambiguity
- DA-blocked overconfidence

## Suggested implementation checklist

- [ ] Review current CR-001 extraction prompt.
- [ ] Identify ambiguous wording in the prompt.
- [ ] Add field-level definitions.
- [ ] Add field boundary rules.
- [ ] Add instruction for uncertainty / ambiguity.
- [ ] Add instruction to avoid unsupported inference.
- [ ] Review current allele registry.
- [ ] Add definitions for high-impact or frequently confused tokens.
- [ ] Add `avoid_confusing_with` notes for overlapping tokens where useful.
- [ ] Add reference image selection guidance.
- [ ] Add a manual review rubric.
- [ ] Select a small set of calibration reference images.
- [ ] Run large model extraction for selected calibration images.
- [ ] Run `gemini-2.5-flash` extraction for the same images.
- [ ] Compare large-model and Flash outputs field by field.
- [ ] Run Devil's Advocate review against both outputs.
- [ ] Record DA findings as prompt / registry / human-decision items.
- [ ] Compare single vs batch result for the same reference image.
- [ ] Record known stable and unstable extraction fields.
- [ ] Refine prompt / allele registry based on observed semantic drift and DA review.
- [ ] Rerun calibration images after each prompt change.
- [ ] Update tests or golden examples only after prompt semantics are stable enough.
- [ ] Document that prompt quality is part of the CR-001 contract.

## Acceptance criteria

- CR-001 prompt clearly defines each output field.
- CR-001 prompt distinguishes visual observation, inferred appeal, reusable style gene, impression color, and generation guidance.
- `expected_style_genes` and `character_appeal_genes` no longer rely only on vague natural-language intuition.
- At least the most important / most ambiguous allele tokens have definitions.
- Selected calibration images can be extracted by both a large model and `gemini-2.5-flash`.
- Large-model and Flash differences can be classified using the semantic diff categories.
- DA review can challenge both outputs and produce actionable findings.
- DA review does not assume large model correctness or Flash inferiority.
- Batch and single extraction for the same image are semantically close enough for review.
- Legacy Phase 0 three-aspect schema does not leak into CR-001 extraction output.
- Manual review can identify whether a mismatch is caused by:
  - input image quality
  - prompt ambiguity
  - allele registry ambiguity
  - model randomness
  - model capability difference
  - field boundary confusion
  - schema insufficiency
  - unsupported inference
  - DA-identified overconfidence
- README / SPEC / backlog notes explain that CR-001 extraction quality is governed by prompt contract, allele semantics, model choice, DA review, and calibration workflow, not only by code structure.

## Suggested manual review rubric

Use this rubric when reviewing CR-001 extraction results.

### A. Style gene correctness

Questions:

- Are the selected style genes visibly supported by the image?
- Are selected tokens reusable for future generation?
- Are any selected tokens too generic to be useful?
- Are any tokens selected only because they sound plausible?
- Do Flash and large-model outputs agree on the major style categories?
- Did DA identify any unsupported or overconfident style token?

Result:

```text
stable / partially-stable / unstable
```

### B. Appeal point correctness

Questions:

- Does the output capture why the image is attractive or memorable?
- Does it separate character appeal from rendering style?
- Does it avoid inventing personality or backstory?
- Does the large model add useful nuance or unsupported inference?
- Does Flash omit important appeal points?
- Did DA identify field boundary violations?

Result:

```text
stable / partially-stable / unstable
```

### C. Color impression correctness

Questions:

- Are the colors actually visible or strongly perceived?
- Are colors too symbolic or unsupported?
- Do both models identify similar color impressions?
- Should palette extraction be model-only, image-processing-only, or cross-validated?
- Did DA recommend palette validation?

Result:

```text
model-ok / needs-palette-extraction / needs-cross-validation
```

### D. Batch / single consistency

Questions:

- Does batch output preserve the same major semantic interpretation as single output?
- Are differences only wording-level, or do they change the extracted meaning?

Result:

```text
consistent / minor-drift / major-drift
```

### E. Model comparison

Questions:

- Does Flash produce a structurally valid but less precise result?
- Does the larger model produce better semantics or over-infer?
- Are differences caused by prompt ambiguity or model capability?
- Which interpretation should become the preferred CR-001 contract?
- Did DA find both outputs flawed?

Result:

```text
flash-aligned / large-model-aligned / both-valid / both-unstable / needs-human-decision
```

### F. Devil's Advocate review

Questions:

- What is the strongest argument that the large-model output is wrong?
- What is the strongest argument that the Flash output is wrong?
- What did both models miss?
- What did both models overstate?
- Which disagreement requires human decision?
- Which disagreement can be fixed by prompt or registry changes?

Result:

```text
accept / revise-prompt / revise-registry / needs-human-decision / reject-reference-image
```

## Open questions

### 1. Impression colors source

Should `impression_colors` be determined by:

- LLM visual judgment
- image palette extraction
- cross-validation between LLM and palette extraction

Suggested default:

```text
Use LLM judgment for early CR-001 semantic exploration.
Add palette extraction later if color stability becomes important for downstream scoring or generation.
DA review may flag cases that need palette validation.
```

### 2. Allele registry depth

Should every allele token require a full definition now?

Suggested default:

```text
No. Start with high-impact and frequently confused tokens.
Expand definitions as review data and DA findings reveal ambiguity.
```

### 3. Golden examples

Should CR-001 define golden examples now?

Suggested default:

```text
Yes, but keep them lightweight.
Use a small number of DA-reviewed reference images as semantic anchors.
Do not overfit the prompt to one image.
```

### 4. Model randomness

Should CR-001 enforce deterministic extraction?

Suggested default:

```text
Prefer lower temperature and stable prompt wording.
Do not require exact string equality.
Evaluate semantic stability instead.
```

### 5. Large-model role

Should the larger model become the production default?

Suggested default:

```text
No, not by default.
Use the larger model as a semantic calibration reference for selected images.
Keep gemini-2.5-flash as the high-volume extractor unless quality data proves otherwise.
```

### 6. Calibration batch size

How many images should be used for initial calibration?

Suggested default:

```text
Start with 3 to 5 representative reference images.
Include at least one image that is likely to expose ambiguity in style, appeal, or color extraction.
```

### 7. DA automation level

Should Devil's Advocate review be manual, prompt-based, or automated?

Suggested default:

```text
Start as a manual / prompt-guided review step.
Only automate after the DA rubric becomes stable.
```

## Possible future escalation to CR-002

This follow-up may become a separate CR only if it grows into a broader subsystem.

Possible CR-002 trigger examples:

- semantic calibration framework
- style gene confidence scoring
- visual gene distance calculation
- cross-image style stability scoring
- automatic palette extraction pipeline
- LLM-as-judge evaluation for extraction quality
- formal golden dataset for image-to-gene extraction
- automated Devil's Advocate review pipeline

Possible future CR name:

```text
CR-002 Semantic Calibration for Visual Gene Extraction
```

Until then, this remains:

```text
CR-001-FU-02 Refine extraction semantics and prompt contract
```

## Backlink to CR-001

Add the following section to CR-001:

```md
## Follow-ups

- `CR-001-FU-02`: Refine extraction semantics and prompt contract.

Reason: CR-001 native artifact structure is stable enough to use as the Phase 0 primary baseline, but extraction quality still depends on prompt wording, allele semantics, model choice, dual-model calibration, Devil's Advocate review, and batch/single consistency.
```

## Playbook lesson

Future CR work should distinguish between:

```text
Code structure is stable.
Artifact shape is stable.
Extraction semantics are stable.
Model outputs are mutually consistent.
Devil's Advocate review has challenged the assumptions.
Human expectation is satisfied.
```

These are different levels of correctness.

Key rules:

> A JSON artifact can be schema-valid but semantically wrong.

> Agreement between two models is useful evidence, not proof.

> A larger model can be more detailed and still be less grounded.

> Flash can be lighter and still be correct if the prompt contract is clear enough.

> Devil's Advocate review should challenge both outputs before human accepts a semantic baseline.

For visual extraction workflows, prompt contract, allele semantics, model choice, and DA review must be treated as part of the implementation, not as informal wording.
