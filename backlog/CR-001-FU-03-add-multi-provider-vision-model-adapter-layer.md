# CR-001-FU-03 Add Multi-Provider Vision Model Adapter Layer

## Status

Backlog / Proposed

## Parent

- CR-001 Appeal Point and Art Style Extraction
- Related follow-up:
  - CR-001-FU-02 Refine Extraction Semantics and Prompt Contract

## Summary

CR-001 currently validates the reference image analysis flow primarily through Gemini-based batch extraction.

To compare Gemini with non-Gemini vision-capable models, such as OpenAI, Claude, Mistral / Pixtral, or future local vision models, the current Gemini-specific request and response handling should be extracted behind a provider adapter boundary.

This follow-up introduces a minimal multi-provider vision model adapter layer while keeping the CR-001 native artifact schema unchanged.

The goal is not to redesign CR-001, but to make the existing extraction pipeline provider-aware, repeatable, and easier to compare across models.

---

## Motivation

CR-001-FU-02 focuses on DA-driven prompt refinement:

```text
same reference images
→ two model batch responses
→ DA comparison
→ prompt-only refinement
→ next round
```

However, once models outside Gemini are introduced, the pipeline needs to handle provider differences:

- image input format differs by provider
- request body shape differs by provider
- response format differs by provider
- JSON output may be wrapped in text or markdown
- provider metadata is needed for comparison
- raw responses should be captured before normalization
- schema validation should remain provider-independent

Without a provider adapter boundary, adding more models may lead to duplicated logic, provider-specific conditionals, and fragile parsing scattered across the CR-001 pipeline.

---

## Problem Statement

The CR-001 pipeline should not directly depend on Gemini-specific API structures.

Current risk areas include:

- provider-specific request construction living inside the main extraction flow
- model names or provider assumptions being hardcoded
- JSON parsing assuming one provider response shape
- raw response capture lacking provider metadata
- output filenames not encoding provider / model identity consistently
- validation not clearly separated from model invocation
- future OpenAI / Claude / Mistral support requiring invasive code changes

---

## Goal

Introduce a provider-aware adapter boundary for vision model extraction.

The pipeline should be able to call different providers through the same internal interface:

```text
CR-001 pipeline
  → VisionProvider adapter
  → raw response capture
  → JSON extraction / repair
  → schema validation
  → CR-001 native artifact output
  → cross-model comparison / DA review
```

The CR-001 artifact schema should remain stable.

---

## Non-Goals

This follow-up should not:

- change `schema_version: cr001.v1`
- rename CR-001 native artifact fields
- redesign `expected_style_genes`
- redesign `character_appeal_genes`
- redesign `impression_colors`
- introduce Phase 0 projection output
- rewrite the entire pipeline
- perform prompt semantics refinement
- decide final model ranking
- implement full router policy integration
- introduce complex retry / quota policy unless required for basic execution

Prompt semantics refinement belongs to CR-001-FU-02.

Provider adapter and response normalization belong to CR-001-FU-03.

---

## Proposed Scope

### In Scope

- introduce provider-aware model config
- define a provider-neutral `VisionProvider` interface
- implement existing Gemini flow as the first adapter
- prepare extension points for OpenAI / Claude / Mistral
- centralize image input normalization
- capture raw provider response with metadata
- extract JSON from provider responses through a shared utility
- validate normalized output against CR-001 schema
- standardize output filenames with provider and model identity
- add minimal comparison-friendly metadata

### Out of Scope

- changing CR-001 extraction prompt semantics
- changing the gene registry design
- adding new style gene tags
- adding DA scoring logic
- adding model-fit ranking
- adding automatic provider selection
- adding local VLM support unless trivial through the same interface

---

## Design Principle

### Keep CR-001 artifact schema provider-independent

The CR-001 native artifact remains the stable output contract:

```json
{
  "schema_version": "cr001.v1",
  "source": "cr001_reference_image_analysis",
  "records": []
}
```

Provider-specific details should be stored in raw response metadata or execution metadata, not inside the core semantic records unless a separate metadata field is explicitly introduced.

---

## Suggested Architecture

```text
src/
  cr001/
    providers/
      VisionProvider.ts
      GeminiVisionProvider.ts
      OpenAIVisionProvider.ts
      ClaudeVisionProvider.ts
      MistralVisionProvider.ts
    io/
      imageInput.ts
      rawResponseWriter.ts
      outputNaming.ts
    parsing/
      extractJsonCandidate.ts
      parseModelJson.ts
      repairJsonCandidate.ts
    validation/
      validateCr001Artifact.ts
      validateGeneRegistry.ts
    runner/
      runCr001Batch.ts
```

This structure is illustrative. Actual paths may follow the existing repository layout.

---

## Provider-Neutral Interface

Suggested interface:

```ts
export type VisionProviderId =
  | "google"
  | "openai"
  | "anthropic"
  | "mistral"
  | "local";

export type VisionExtractionImage = {
  sourceImage: string;
  mimeType: string;
  dataBase64: string;
};

export type VisionExtractionInput = {
  provider: VisionProviderId;
  model: string;
  prompt: string;
  images: VisionExtractionImage[];
  temperature?: number;
  maxOutputTokens?: number;
};

export type VisionExtractionRawResult = {
  provider: VisionProviderId;
  model: string;
  rawText: string;
  rawResponse?: unknown;
  usage?: unknown;
  startedAt?: string;
  finishedAt?: string;
};

export interface VisionProvider {
  generate(input: VisionExtractionInput): Promise<VisionExtractionRawResult>;
}
```

The CR-001 runner should depend on `VisionProvider`, not directly on Gemini API objects.

---

## Provider-Aware Config

Current model config should evolve from model-only configuration:

```json
{
  "model": "gemini-2.5-flash"
}
```

Into provider-aware configuration:

```json
{
  "provider": "google",
  "model": "gemini-2.5-flash",
  "role": "extractor",
  "input_modalities": ["image", "text"],
  "output_format": "json"
}
```

For comparison runs:

```json
{
  "cr001_batch_models": [
    {
      "provider": "google",
      "model": "gemini-2.5-flash",
      "role": "cheap_extractor_baseline"
    },
    {
      "provider": "google",
      "model": "gemini-3.5-flash",
      "role": "semantic_extractor"
    },
    {
      "provider": "openai",
      "model": "gpt-vision-capable-model",
      "role": "schema_compliance_judge"
    },
    {
      "provider": "anthropic",
      "model": "claude-sonnet",
      "role": "semantic_reviewer"
    }
  ]
}
```

Actual model names should be resolved by runtime config and may change over time.

---

## Raw Response Capture

Each provider response should be captured before JSON extraction.

Suggested raw output path:

```text
phase0/raw/
  cr001_google_gemini-2.5-flash_refset-001_raw.json
  cr001_google_gemini-3.5-flash_refset-001_raw.json
  cr001_openai_gpt-vision-capable-model_refset-001_raw.json
  cr001_anthropic_claude-sonnet_refset-001_raw.json
```

Suggested raw response metadata:

```json
{
  "schema_version": "cr001.raw_response.v1",
  "provider": "google",
  "model": "gemini-2.5-flash",
  "source": "cr001_reference_image_analysis",
  "reference_set_id": "refset-001",
  "input_images": [
    "reference_images/ref-001.png",
    "reference_images/ref-002.png",
    "reference_images/ref-003.png",
    "reference_images/ref-004.png"
  ],
  "started_at": "2026-XX-XXT00:00:00Z",
  "finished_at": "2026-XX-XXT00:00:00Z",
  "raw_text": "",
  "raw_response": {}
}
```

---

## Normalized Output Naming

Normalized CR-001 output should encode provider and model:

```text
phase0/
  cr001_reference_image_analysis.google.gemini-2.5-flash.json
  cr001_reference_image_analysis.google.gemini-3.5-flash.json
  cr001_reference_image_analysis.openai.gpt-vision-capable-model.json
  cr001_reference_image_analysis.anthropic.claude-sonnet.json
```

The current default output may remain for backward compatibility, but the comparison workflow should prefer explicit provider/model filenames.

---

## JSON Extraction and Parsing

Different providers may return JSON in different shapes:

- pure JSON
- JSON inside markdown code block
- explanatory text followed by JSON
- tool-call style JSON
- malformed but recoverable JSON
- valid JSON with schema-extra fields

The shared parsing layer should handle:

```text
raw provider response
→ extract JSON candidate
→ parse JSON
→ optionally repair trivial formatting issues
→ validate CR-001 schema
→ normalize field order
→ write CR-001 native artifact
```

The parsing layer must not contain provider-specific semantic rules.

Provider-specific response shape handling should happen before the shared JSON extraction layer.

---

## Validation Requirements

Validation should remain provider-independent.

Minimum checks:

- `schema_version` exists
- `schema_version` equals `cr001.v1`
- `source` equals `cr001_reference_image_analysis`
- `records` is an array
- `records.length` equals input image count
- each `source_image` maps to one input image
- each gene group has `selected` and `intensity`
- `selected.length === intensity.length`
- each intensity is a number between `0.0` and `1.0`
- selected tags exist in the configured registry
- `impression_colors.main` is a valid hex color if present
- `impression_colors.secondary` is a valid hex color if present
- `impression_colors.accent` is a valid hex color if present
- no hallucinated source image path
- no missing record for an input image

Optional checks:

- warn on unknown extra fields
- warn on empty selected arrays
- warn on repeated tags
- warn on conflicting tags if conflict rules exist
- warn when all images receive identical genes suspiciously

---

## Minimal Provider Adapter Acceptance Path

The first implementation does not need to support every provider immediately.

A good MVP path:

```text
Step 1:
  Extract existing Gemini call into GeminiVisionProvider.

Step 2:
  Make CR-001 runner call VisionProvider interface.

Step 3:
  Add provider-aware config.

Step 4:
  Add raw response capture with provider/model metadata.

Step 5:
  Add shared JSON extraction and validation.

Step 6:
  Confirm current Gemini outputs remain compatible.

Step 7:
  Add one non-Gemini provider adapter as proof of boundary.
```

The first non-Gemini adapter can be OpenAI or Claude, depending on available API access.

---

## Relationship with CR-001-FU-02

CR-001-FU-02:

```text
Purpose:
  Improve extraction semantics and prompt contract.

Primary operation:
  DA compare two model batch responses.
  Refine prompt.
  Rerun next round.

Allowed code changes:
  Only minimal validation/config cleanup.
```

CR-001-FU-03:

```text
Purpose:
  Make CR-001 able to call multiple vision providers safely.

Primary operation:
  Extract provider adapter layer.
  Normalize raw responses.
  Validate provider-independent CR-001 artifact.
```

Boundary rule:

```text
If the issue is "the model selected the wrong gene",
handle it in FU-02.

If the issue is "the system cannot call or parse another provider cleanly",
handle it in FU-03.
```

---

## Implementation Guardrails

Code changes are allowed when they:

1. move provider-specific request logic behind an adapter
2. centralize image input formatting
3. centralize raw response capture
4. centralize JSON extraction
5. centralize schema validation
6. improve repeatability of cross-model comparison
7. preserve CR-001 native artifact schema
8. avoid changing prompt semantics

Code changes are not allowed when they:

1. rewrite CR-001 schema without a separate CR
2. add semantic tag rules unrelated to provider support
3. change registry meanings
4. mix DA review logic into provider adapters
5. introduce automatic model ranking
6. introduce router policy decisions

---

## Testing Plan

### 1. Regression Test Existing Gemini Flow

Given:

```text
provider: google
model: gemini-2.5-flash
```

Expected:

```text
- provider adapter produces raw response
- JSON extraction succeeds
- CR-001 artifact validates
- output schema remains cr001.v1
```

Repeat for:

```text
provider: google
model: gemini-3.5-flash
```

### 2. Raw Response Capture Test

Expected:

```text
- raw response file exists
- provider is recorded
- model is recorded
- input image list is recorded
- raw_text or raw_response is present
```

### 3. Validation Failure Test

Feed malformed artifact:

```text
- unknown tag
- invalid hex color
- selected/intensity length mismatch
- missing source_image
```

Expected:

```text
- validator fails deterministically
- error message identifies the broken field
```

### 4. Provider Boundary Test

Add a mock provider:

```ts
class MockVisionProvider implements VisionProvider {
  async generate(input: VisionExtractionInput): Promise<VisionExtractionRawResult> {
    return {
      provider: input.provider,
      model: input.model,
      rawText: JSON.stringify({
        schema_version: "cr001.v1",
        source: "cr001_reference_image_analysis",
        records: []
      })
    };
  }
}
```

Expected:

```text
- runner can call provider through interface
- no Gemini-specific dependency is required
```

### 5. Non-Gemini Smoke Test

Given one non-Gemini provider adapter:

```text
provider: openai | anthropic | mistral
```

Expected:

```text
- image input is accepted
- raw response is captured
- JSON candidate is extracted
- schema validation runs
- normalized artifact is written
```

---

## Acceptance Criteria

This follow-up is complete when:

- existing Gemini CR-001 batch extraction still works
- Gemini call logic is behind a provider adapter
- CR-001 runner depends on a provider-neutral interface
- model config includes provider and model identity
- raw responses are captured with provider/model metadata
- normalized output filename includes provider/model identity
- JSON extraction is shared and not Gemini-specific
- CR-001 validation is provider-independent
- at least one provider adapter can be tested through the common interface
- CR-001 native artifact schema remains unchanged
- FU-02 prompt refinement loop remains unaffected

---

## Suggested Commit Breakdown

### Commit 1

```text
Add provider-aware vision extraction types
```

### Commit 2

```text
Extract Gemini vision call into provider adapter
```

### Commit 3

```text
Add raw response capture for CR-001 provider runs
```

### Commit 4

```text
Add shared JSON extraction and CR-001 validation boundary
```

### Commit 5

```text
Update CR-001 batch runner to use provider config
```

### Commit 6

```text
Add mock or non-Gemini provider smoke test
```

---

## Open Questions

1. Should provider/model metadata be included only in raw response files, or also in normalized CR-001 artifacts?

2. Should normalized artifacts preserve the current default filename for backward compatibility?

3. Which non-Gemini provider should be implemented first?

4. Should JSON repair be allowed automatically, or should malformed JSON fail fast?

5. Should provider API failures be handled here, or deferred to a separate retry / provider error handling follow-up?

6. Should model roles such as `extractor`, `reviewer`, and `judge` live in CR-001 config or in a higher-level routing config?

---

## Recommended Decision

For the first version:

```text
- Keep CR-001 normalized artifact schema unchanged.
- Store provider/model metadata in raw response files and filenames.
- Preserve existing Gemini output path as compatibility output if needed.
- Implement Gemini provider adapter first.
- Add mock provider test before adding real non-Gemini provider.
- Defer retry/quota policy to a separate follow-up unless blocking.
```

---

## Notes

This follow-up supports future cross-model experiments, but it should remain infrastructure-focused.

The immediate value is to prevent provider-specific logic from leaking into the CR-001 semantic extraction flow.

The long-term value is that CR-001 can compare:

```text
Gemini extractor
OpenAI extractor / judge
Claude semantic reviewer
Mistral cross-vendor baseline
local VLM candidate
```

without changing the native CR-001 artifact contract.
