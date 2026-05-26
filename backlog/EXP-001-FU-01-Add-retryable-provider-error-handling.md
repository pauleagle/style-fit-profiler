# EXP-001-FU-01 Add retryable provider error handling

## Metadata

```yaml
item_id: EXP-001-FU-01
item_type: follow-up
parent_type: EXP
parent_id: EXP-001
status: proposed
drill_down_status: ready-for-atomic-decomposition
title: Add retryable provider error handling
source_role: working-draft
formal_spec_path: specs/backlog/EXP-001-FU-01-retryable-provider-error-handling.md
parent_spec_path: specs/backlog/EXP-001-gemini-image-analysis-extractor.md
root_spec_path: SPEC.md
related_items:
  - EXP-002
  - CR-001
integration_status: ready-for-atomic-decomposition
workflow_step: Step 4.5 - Workflow Decomposition / Atomic Work Items
```

## Status

Proposed

## Parent

- EXP-001 (`specs/backlog/EXP-001-gemini-image-analysis-extractor.md`)
- Related: CR-001 runtime execution flow
- Formal spec: `specs/backlog/EXP-001-FU-01-retryable-provider-error-handling.md`
- Root index: `SPEC.md`

## Type

Follow-up / Runtime Infrastructure

## Drill-down Decision Update

Formal spec source: `specs/backlog/EXP-001-FU-01-retryable-provider-error-handling.md`.

Current accepted drill-down decisions:

- Single-image commands do not automatically retry provider errors. They may classify provider errors for diagnostics, but should fail fast.
- Batch commands preserve the existing retry attempt count behavior through `max_attempts`.
- Batch delay retry is controlled by config and defaults to disabled.
- Retry policy values are owned by `style_profiler_config.json` under `reference_image_analysis_policy.provider_retry_policy`.
- Default retry policy values:

```json
{
  "max_attempts": 3,
  "delay_retry_enabled": false,
  "delay_retry_times": 2,
  "retry_buffer_seconds": 2,
  "default_initial_backoff_seconds": 5,
  "max_single_delay_seconds": 60,
  "max_total_delay_seconds": 120,
  "jitter_enabled": true
}
```

This working draft may contain older exploratory wording below; the formal spec path above is the current implementation contract.

## Summary

Add retryable provider error handling to the EXP-001 batch/model-calling runtime.

This follow-up focuses on handling transient provider-side failures such as Gemini quota exhaustion, rate limits, and temporary service unavailability without corrupting the batch output or aborting the entire run unnecessarily.

The first concrete case is Gemini returning:

```json
{
  "status": "RESOURCE_EXHAUSTED",
  "message": "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests ... Please retry in 49.272417405s."
}
```

This is not a CR-001 schema problem and should not be treated as prompt failure or extraction failure. It belongs to the runtime/provider execution layer.

---

## Motivation

EXP-001 has moved from single-image proof-of-concept execution toward batch execution.

At this stage, runtime reliability becomes part of the system contract:

- A single provider error should not invalidate the entire batch.
- Retryable errors should be retried using bounded policy.
- Non-retryable errors should fail fast with clear diagnostics.
- Failed attempts should be recorded in machine-readable form.
- Future resume/retry flows should be able to continue from partial results.

This follow-up establishes the first version of that runtime error handling contract.

---

## Problem Statement

Current model-calling behavior is not yet formalized for provider errors.

When the provider returns a quota/rate-limit error such as `RESOURCE_EXHAUSTED`, the runner needs to decide:

1. Is the error retryable?
2. How long should it wait before retrying?
3. How many attempts are allowed?
4. How should failed attempts be recorded?
5. Should the batch continue when one image/model call fails?
6. How should retry history appear in the output artifact?

Without explicit handling, the pipeline may:

- crash the whole batch,
- lose partial results,
- retry too aggressively,
- hide provider-side instability,
- or incorrectly classify runtime errors as extraction/schema errors.

---

## Scope

### In Scope

- Detect retryable provider errors.
- Support Gemini `RESOURCE_EXHAUSTED` as the first concrete retryable case.
- Extract retry delay from provider error message when available.
- Apply bounded retry attempts.
- Add a small safety buffer to provider-suggested retry delay.
- Record failed attempts in batch-level metadata or per-record metadata.
- Continue batch execution when one image/model call fails after max attempts.
- Preserve enough diagnostic information for manual review.
- Keep CR-001 native artifact schema separate from runtime execution metadata unless explicitly wrapped by a batch result format.

### Out of Scope

- Paid quota management.
- Automatic billing/project switching.
- Full provider fallback routing.
- Global scheduler.
- Dashboard/UI monitoring.
- Long-running background job orchestration.
- Semantic DA review of extracted JSON.
- CR-001 schema redesign.
- Palette extraction validation.
- Multi-model consensus merge policy.

These may be handled by later follow-ups.

---

## Error Classification

The runtime should classify provider/model-call failures into explicit categories.

| Provider status / condition | Runtime category | Retryable | Expected action |
| --- | --- | --- | --- |
| `RESOURCE_EXHAUSTED` | `provider_quota_exhausted` | Yes | Extract retry delay if available, then retry with bounded attempts |
| `UNAVAILABLE` | `provider_unavailable` | Yes | Retry with exponential backoff |
| `INTERNAL` | `provider_internal_error` | Yes | Retry with exponential backoff |
| `DEADLINE_EXCEEDED` | `provider_timeout` | Yes | Retry with bounded attempts |
| `INVALID_ARGUMENT` | `invalid_request` | No | Fail fast; likely prompt/payload/config issue |
| `UNAUTHENTICATED` | `auth_error` | No | Fail fast; API key or auth configuration issue |
| `PERMISSION_DENIED` | `permission_error` | No | Fail fast; model/project permission issue |
| JSON parse failure | `invalid_model_output` | Maybe | Retry once or route to repair flow |
| Schema validation failure | `schema_validation_failed` | Maybe | Do not blindly retry unless configured |
| Unknown error | `unknown_provider_error` | No by default | Fail safely and record diagnostics |

---

## Retry Policy v1

### Defaults

```json
{
  "max_attempts": 3,
  "retry_buffer_seconds": 2,
  "default_initial_backoff_seconds": 5,
  "max_backoff_seconds": 60,
  "jitter_enabled": true
}
```

### Behavior

1. Call provider.
2. If success:
   - store raw response,
   - parse JSON,
   - validate schema,
   - write success result.
3. If provider returns a retryable error:
   - classify the error,
   - extract retry delay if available,
   - wait `retry_after_seconds + retry_buffer_seconds`,
   - retry until `max_attempts` is reached.
4. If still failed after max attempts:
   - record failed result,
   - mark the specific image/model call as failed,
   - continue the rest of the batch when possible.
5. If provider returns a non-retryable error:
   - record failed result,
   - do not retry,
   - continue or abort depending on batch policy.

---

## Retry Delay Extraction

For Gemini `RESOURCE_EXHAUSTED`, the provider message may include text similar to:

```text
Please retry in 49.272417405s.
```

The runtime should extract:

```json
{
  "retry_after_seconds": 49.272417405
}
```

Then apply:

```text
actual_wait_seconds = retry_after_seconds + retry_buffer_seconds
```

Example:

```text
49.272417405 + 2 = 51.272417405 seconds
```

If no retry delay is found, use exponential backoff.

---

## Proposed Runtime Flow

```text
for each source image:
  for each configured model:
    attempt = 1

    while attempt <= max_attempts:
      result = call_provider(image, model, prompt)

      if result.success:
        save_success_record(...)
        break

      error = classify_provider_error(result.error)

      save_attempt_record(...)

      if not error.retryable:
        save_failed_record(...)
        break

      if attempt == max_attempts:
        save_failed_record(...)
        break

      wait_seconds = resolve_retry_delay(error)
      sleep(wait_seconds)

      attempt += 1

continue batch
write batch summary
```

---

## Output Record Requirements

Runtime error metadata should be machine-readable.

A failed record may look like:

```json
{
  "source_image": "reference_images/ref-001.png",
  "model": "gemini-2.5-flash",
  "status": "failed",
  "attempts": 3,
  "error": {
    "type": "provider_quota_exhausted",
    "provider_status": "RESOURCE_EXHAUSTED",
    "retryable": true,
    "message": "Quota exceeded for free tier requests",
    "retry_after_seconds": 49.272417405
  }
}
```

A successful record after retry may look like:

```json
{
  "source_image": "reference_images/ref-001.png",
  "model": "gemini-2.5-flash",
  "status": "success",
  "attempts": 2,
  "warnings": [
    {
      "type": "provider_quota_exhausted_retried",
      "provider_status": "RESOURCE_EXHAUSTED",
      "retry_after_seconds": 49.272417405
    }
  ]
}
```

---

## Batch Summary Requirements

The batch runner should produce a summary section such as:

```json
{
  "batch_summary": {
    "total_jobs": 8,
    "succeeded": 7,
    "failed": 1,
    "retried": 2,
    "retryable_failures": 1,
    "non_retryable_failures": 0
  }
}
```

This allows later tooling to answer:

- Did the batch complete?
- Which records failed?
- Which failures were retryable?
- Which records succeeded only after retry?
- Is this result safe for downstream projection?

---

## Separation from CR-001 Native Artifact

CR-001 native artifact should remain focused on extracted semantic/style data.

Runtime execution metadata should not pollute the core CR-001 record unless the artifact format explicitly supports a wrapper.

Recommended separation:

```text
phase0/cr001_reference_image_analysis.json
  -> semantic extraction artifact

phase0/cr001_reference_image_analysis.batch.json
  -> batch execution wrapper with runtime status, attempts, errors, warnings
```

Alternative structure:

```json
{
  "schema_version": "exp001.batch_result.v1",
  "source": "exp001_batch_runner",
  "batch_summary": {},
  "records": [
    {
      "runtime": {
        "status": "success",
        "attempts": 2,
        "warnings": []
      },
      "cr001_record": {}
    }
  ]
}
```

---

## Acceptance Criteria

- [ ] Gemini `RESOURCE_EXHAUSTED` is detected and classified as retryable.
- [ ] Retry delay is extracted from provider message when present.
- [ ] Retry delay includes a configurable safety buffer.
- [ ] Retry attempts are bounded by `max_attempts`.
- [ ] Non-retryable errors are not retried.
- [ ] Failed image/model calls are recorded without crashing the entire batch.
- [ ] Successful retries include warning metadata.
- [ ] Failed retries include final error metadata.
- [ ] Batch summary includes success/failure/retry counts.
- [ ] CR-001 semantic artifact remains separate from runtime execution metadata.
- [ ] Tests cover retryable, non-retryable, and max-attempts behavior.

---

## Suggested Tests

### Unit Tests

- `classifyProviderError()` returns `provider_quota_exhausted` for Gemini `RESOURCE_EXHAUSTED`.
- `classifyProviderError()` marks `RESOURCE_EXHAUSTED` as retryable.
- `extractRetryAfterSeconds()` parses `Please retry in 49.272417405s.`
- `resolveRetryDelay()` adds the configured buffer.
- `shouldRetry()` returns false when `attempt >= max_attempts`.
- `shouldRetry()` returns false for non-retryable errors.
- `buildFailedRuntimeRecord()` produces machine-readable error metadata.
- `buildRetriedSuccessWarning()` records retry history on success.

### Integration Tests

- Simulate one `RESOURCE_EXHAUSTED` response followed by success.
- Simulate repeated `RESOURCE_EXHAUSTED` until max attempts are reached.
- Simulate `INVALID_ARGUMENT` and verify no retry occurs.
- Simulate one failed image in a batch and verify the batch continues.
- Verify batch summary counts succeeded, failed, and retried jobs correctly.

---

## Implementation Notes

A possible TypeScript-oriented module split:

```text
src/runtime/providerError.ts
src/runtime/retryPolicy.ts
src/runtime/batchResult.ts
src/runtime/providerCaller.ts
```

Suggested function names:

```ts
classifyProviderError(error: unknown): ProviderError
extractRetryAfterSeconds(message: string): number | null
resolveRetryDelay(error: ProviderError, policy: RetryPolicy, attempt: number): number
shouldRetry(error: ProviderError, attempt: number, policy: RetryPolicy): boolean
buildRuntimeAttemptRecord(...)
buildRuntimeFailureRecord(...)
buildRuntimeSuccessWarning(...)
```

Suggested types:

```ts
type RuntimeErrorType =
  | "provider_quota_exhausted"
  | "provider_unavailable"
  | "provider_internal_error"
  | "provider_timeout"
  | "invalid_request"
  | "auth_error"
  | "permission_error"
  | "invalid_model_output"
  | "schema_validation_failed"
  | "unknown_provider_error";

type ProviderError = {
  type: RuntimeErrorType;
  providerStatus?: string;
  retryable: boolean;
  message?: string;
  retryAfterSeconds?: number;
};

type RetryPolicy = {
  maxAttempts: number;
  retryBufferSeconds: number;
  defaultInitialBackoffSeconds: number;
  maxBackoffSeconds: number;
  jitterEnabled: boolean;
};
```

---

## Future Follow-ups

Potential next items:

```text
EXP-001-FU-02 Add resumable batch state
EXP-001-FU-03 Add provider fallback policy
EXP-001-FU-04 Add manual usage gate and stop threshold
EXP-001-FU-05 Add batch execution report
EXP-001-FU-06 Add model-call cost and quota observation hooks
```

---

## Decision Notes

This follow-up should stay in EXP/runtime infrastructure rather than CR-001 schema work.

Reason:

```text
CR-001 defines what the extraction result means.
EXP runtime defines how provider calls are executed, retried, failed, and resumed.
```

Keeping these layers separate prevents runtime instability from leaking into semantic schema design.
