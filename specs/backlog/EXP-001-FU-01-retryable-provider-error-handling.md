# EXP-001-FU-01: Retryable Provider Error Handling

## Metadata

```yaml
item_id: EXP-001-FU-01
item_type: follow-up
parent_type: EXP
parent_id: EXP-001
status: proposed
drill_down_status: ready-for-atomic-decomposition
title: Retryable provider error handling
source_path: backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md
parent_spec_path: specs/backlog/EXP-001-gemini-image-analysis-extractor.md
root_spec_path: SPEC.md
related_items:
  - EXP-002
  - CR-001
integration_status: ready-for-atomic-decomposition
workflow_step: Step 4.5 - Workflow Decomposition / Atomic Work Items
```

## Parent Trace

- Parent spec: [`EXP-001: Gemini Image Analysis Extractor`](EXP-001-gemini-image-analysis-extractor.md)
- Root index: [`SPEC.md`](../../SPEC.md)
- Source draft: [`backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md`](../../backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md)
- Related runtime flows: `EXP-002` batch helpers and `CR-001` native batch execution.

This follow-up does not reopen the completed EXP-001 helper work. It blocks only the next reliability step where manual Gemini / batch runtime should tolerate transient provider failures without corrupting partial output or misclassifying provider errors as prompt, parser, schema, or CR-001 semantic failures.

## Drill-down Gate

Gate status: `pass`

Reason: human decisions have resolved the retry layer boundary, single-image coverage, and delay retry policy. The next step is to finalize accepted atomic items before implementation.

Current code evidence:

- `EXP-002` / legacy batch already has `max_attempts`, per-batch failure isolation, `retryable_batch_indexes`, `attempt_count`, `remaining_attempts`, and final invalid raw response status.
- `CR-001` batch execution already retries failed image scope and preserves partial valid native records.
- Current Gemini HTTP failures are surfaced as stringified `GeminiImageProbeError` messages from `call_gemini_generate_content(...)`; provider status, retry delay, and retryability are not yet machine-readable.
- Current invalid model output retry behavior exists in batch flows, but it is not the same problem as provider-side quota/rate-limit retry.

### Numbered Drill-down Items

| ID | Status | Question | Decision / Current Resolution | Blocks Atomic Decomposition |
|---|---|---|---|---|
| `DD-EXP-001-FU-01-001` | `resolved-by-spec-change` | Is this follow-up runtime infrastructure or CR-001 schema work? | Runtime infrastructure. CR-001 native semantic artifact must remain separate from provider execution metadata. | No |
| `DD-EXP-001-FU-01-002` | `resolved-by-spec-change` | Should provider retry be hidden inside `GeminiImageAnalysisClient` / `CR001GeminiAnalysisClient`? | No. Provider errors may be classified near the Gemini transport layer, but retry orchestration must remain visible to the batch/runtime layer so reports can record attempts and retry exhaustion. | No |
| `DD-EXP-001-FU-01-003` | `resolved-by-spec-change` | Does this replace existing invalid-output retry behavior? | No. Existing invalid JSON / schema retry behavior remains a separate validation retry path. `EXP-001-FU-01` adds typed provider-error classification and retry delay handling; it may later unify the report format, but it must not silently change parser/schema semantics. | No |
| `DD-EXP-001-FU-01-004` | `resolved-by-spec-change` | Which flows are the primary implementation targets? | Start with provider-backed manual batch flows: legacy `gemini_batch_probe` and CR-001 batch probe, because they already expose attempt metadata and partial-success reports. Shared helper code should avoid duplicating classification logic. | No |
| `DD-EXP-001-FU-01-005` | `resolved-by-human-decision` | Should single-image `gemini_image_probe` / CR-001 single probe also retry provider errors in this follow-up? | No automatic retry for single-image commands. Single-image provider failures may be classified for diagnostics, but the command should fail fast and surface the provider metadata. | No |
| `DD-EXP-001-FU-01-006` | `resolved-by-human-decision` | Should manual commands actually sleep for provider-suggested retry delay, or only record retry target metadata? | Batch delay retry is controlled by config. Default is disabled, so existing immediate retry attempts are preserved. When enabled, batch retry may wait within configured `delay_retry_times` and `max_total_delay_seconds`. | No |
| `DD-EXP-001-FU-01-007` | `resolved-by-spec-change` | Where should retry policy be configured? | Introduce an explicit policy object / dataclass with defaults. Existing `--max-attempts` remains CLI-facing; buffer/backoff values can be policy fields first and CLI flags only if needed for manual operations. | No |
| `DD-EXP-001-FU-01-008` | `resolved-by-spec-change` | What metadata must be added without polluting semantic artifacts? | Add provider error fields to runtime wrappers / batch reports: `error.type`, `provider_status`, `retryable`, `retry_after_seconds`, `attempt_count`, `max_attempts`, `remaining_attempts`, and retry exhaustion. Do not add these fields inside CR-001 native semantic records unless wrapped under a runtime section. | No |
| `DD-EXP-001-FU-01-009` | `resolved-by-spec-change` | Can implementation start before all possible future follow-ups are designed? | Yes, but only for bounded provider-error classification and retry delay v1. Resumable batch state, provider fallback, cost/quota observation, and global scheduling remain future follow-ups. | No |

Resolved human decisions:

1. Single-image probe commands do not retry provider errors automatically.
2. Batch delay retry is opt-in by config parameter and defaults to off.
3. Existing retry attempt count behavior is preserved.
4. Delay retry count and max total delay are config-owned defaults, not runner-local magic numbers.

### Proposed Atomic Split After Gate Pass

Draft atomic items, not yet accepted:

- `EXP-001-FU-01A`: Provider error classifier and Gemini retry-delay parser.
  - Scope: pure helper functions / types; no command behavior change.
  - Tests: classify `RESOURCE_EXHAUSTED`, auth/config errors, transient provider statuses, unknown errors, and retry-delay parsing.
- `EXP-001-FU-01B`: Retry policy and delay resolver.
  - Scope: config-owned policy object, bounded delay calculation, and optional injected sleeper contract.
  - Tests: preserved max attempts, delay disabled default, delay retry count, max total delay, retry buffer, max single delay, no-op sleeper, non-retryable errors.
- `EXP-001-FU-01C`: Legacy batch provider-error integration.
  - Scope: `gemini_batch_probe` / EXP batch report metadata; no delay by default.
  - Tests: simulated provider quota error followed by success; exhausted provider quota error; non-retryable provider error; delay disabled preserves immediate retry; delay enabled uses injected sleeper.
- `EXP-001-FU-01D`: CR-001 batch provider-error integration.
  - Scope: CR-001 batch run report provider metadata while keeping native artifact clean; no delay by default.
  - Tests: partial valid native records, failed provider metadata, retryable failed-image scope, delay policy read from config.
- `EXP-001-FU-01E`: Manual command docs and final traceability update.
  - Scope: README / spec notes for retry policy, no secrets, no real API tests.
  - Tests: documentation-only validation plus full unit suite if code changed.

## Summary

Add a bounded retry and provider-error classification contract for EXP-001 model-calling runtime.

The first concrete failure class is Gemini quota / rate-limit exhaustion, such as `RESOURCE_EXHAUSTED` with a provider-suggested retry delay. This belongs to runtime infrastructure, not CR-001 schema design and not extraction prompt semantics.

## Scope

In scope:

- Classify provider/model-call failures into retryable and non-retryable categories.
- Treat Gemini `RESOURCE_EXHAUSTED` as retryable and extract `retry_after_seconds` when present.
- Apply bounded retry attempts through explicit policy, not hardcoded magic numbers.
- Add optional batch delay retry through config-owned policy; default delay behavior is off.
- Add a small configurable buffer to provider-suggested retry delays when delay retry is enabled.
- Preserve partial successful records when a later image, batch, or model call fails.
- Record attempt count, final status, retryability, final error, and warning metadata in a machine-readable runtime wrapper or batch report.
- Keep CR-001 native semantic artifacts separate from runtime execution metadata unless wrapped by a formal batch-result artifact.

Out of scope:

- Paid quota management or project switching.
- Full provider fallback routing.
- Global scheduler, long-running job orchestration, or dashboard monitoring.
- CR-001 schema redesign, semantic calibration, palette validation, or model-consensus policy.

## Runtime Error Classification

The first version should classify at least:

| Provider status / condition | Runtime category | Retryable | Expected action |
|---|---|---:|---|
| `RESOURCE_EXHAUSTED` | `provider_quota_exhausted` | Yes | Extract retry delay if present; retry within bounded policy |
| `UNAVAILABLE` | `provider_unavailable` | Yes | Retry with bounded backoff |
| `INTERNAL` | `provider_internal_error` | Yes | Retry with bounded backoff |
| `DEADLINE_EXCEEDED` | `provider_timeout` | Yes | Retry within bounded policy |
| `INVALID_ARGUMENT` | `invalid_request` | No | Fail fast; likely prompt, payload, or config issue |
| `UNAUTHENTICATED` | `auth_error` | No | Fail fast; auth configuration issue |
| `PERMISSION_DENIED` | `permission_error` | No | Fail fast; model or project permission issue |
| JSON parse failure | `invalid_model_output` | Maybe | Retry only when policy explicitly allows it |
| Schema validation failure | `schema_validation_failed` | Maybe | Do not blindly retry unless configured |
| Unknown error | `unknown_provider_error` | No by default | Fail safely and record diagnostics |

## Retry Policy v1

Retry policy must be owned by `style_profiler_config.json` under `reference_image_analysis_policy.provider_retry_policy`. Batch CLI flags may override config values for manual runs, but runner/client code must not own local magic-number defaults.

Default config:

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

Policy rules:

- `max_attempts` preserves the existing retry attempt count. This value controls how many total attempts may be made and must not be replaced by delay-specific settings.
- `delay_retry_enabled` defaults to `false`. When false, retry behavior stays immediate / non-sleeping while still recording provider retry metadata.
- `delay_retry_times` defaults to `2`. It limits how many retry waits may happen within the existing `max_attempts` budget and must be capped to `max_attempts - 1`.
- `max_total_delay_seconds` defaults to `120`. A batch run must not sleep longer than this total across retry waits.
- `max_single_delay_seconds` defaults to `60`. A single provider-suggested delay must be capped before adding or after applying policy, as long as total delay remains bounded and deterministic in tests.
- `retry_buffer_seconds` defaults to `2` and is added only when delay retry is enabled.
- Single-image commands do not use automatic retry. They may classify provider errors and report retry metadata, but they should fail fast.

Runtime behavior:

1. Call provider.
2. On success, store raw response, parse/validate downstream output, and write success result.
3. On retryable provider error in a batch flow, classify the error, record the attempt, and retry until `max_attempts`.
4. If `delay_retry_enabled` is true, compute bounded retry delay and sleep through an injectable sleeper; tests must not perform real waits.
5. If `delay_retry_enabled` is false, keep the original immediate retry behavior and record the provider-recommended retry metadata for manual review.
6. On final retry failure, record failed status and continue remaining batch work when the caller supports partial success.
7. On non-retryable error, record failed status and do not retry.

For Gemini messages containing text like `Please retry in 49.272417405s.`, extract:

```json
{
  "retry_after_seconds": 49.272417405
}
```

Then apply:

```text
actual_wait_seconds = min(
  retry_after_seconds + retry_buffer_seconds,
  max_single_delay_seconds,
  remaining_total_delay_seconds
)
```

## Output Contract

Runtime execution metadata must be separated from semantic extraction records.

Recommended wrapper fields:

```json
{
  "runtime": {
    "status": "success | failed",
    "attempts": 2,
    "warnings": [],
    "error": null
  }
}
```

For failed records:

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
    "retry_after_seconds": 49.272417405
  }
}
```

For batch runs, summary metadata should answer:

- How many jobs / batches succeeded, failed, and retried.
- Which failures remain retryable.
- Which records succeeded only after retry.
- Whether the result is safe for downstream projection.

## Acceptance Criteria

- [ ] Gemini `RESOURCE_EXHAUSTED` is detected and classified as `provider_quota_exhausted`.
- [ ] Retry delay is extracted from provider message when present.
- [ ] Single-image commands do not automatically retry provider errors.
- [ ] Batch delay retry is controlled by config and defaults to disabled.
- [ ] Existing retry attempt behavior is preserved through explicit `max_attempts`.
- [ ] Delay retry uses config-owned `delay_retry_times` with default `2`.
- [ ] Delay retry uses config-owned `max_total_delay_seconds` with default `120`.
- [ ] Retry delay includes a configurable buffer only when delay retry is enabled.
- [ ] Non-retryable provider errors are not retried.
- [ ] Failed image/model calls are recorded without crashing the entire batch when partial success is supported.
- [ ] Successful retries include warning / attempt metadata.
- [ ] Failed retries include final machine-readable error metadata.
- [ ] Batch summary includes success, failure, retry, retryable failure, and non-retryable failure counts.
- [ ] CR-001 native semantic artifact remains separate from runtime execution metadata.
- [ ] Tests cover retryable, non-retryable, retry-delay parsing, and max-attempt exhaustion behavior.

## Testing Implications

Unit tests should cover:

- provider error classification for `RESOURCE_EXHAUSTED`, retryable transient statuses, auth/config failures, and unknown errors.
- retry delay parsing from Gemini provider messages.
- config validation for `provider_retry_policy`.
- retry delay disabled default preserving immediate retry behavior.
- retry delay resolution with configured buffer, `delay_retry_times`, max single delay, and max total delay.
- single-image provider failure classification without automatic retry.
- `should_retry` behavior for attempt budget and non-retryable errors.
- runtime failure and retried-success metadata builders.

Integration or fixture tests should cover:

- one `RESOURCE_EXHAUSTED` response followed by success.
- repeated `RESOURCE_EXHAUSTED` until max attempts are reached.
- delay disabled default does not call sleeper.
- delay enabled calls an injected no-op sleeper with bounded seconds.
- non-retryable `INVALID_ARGUMENT` without retry.
- one failed image or batch while other records remain available.
- batch summary counts for succeeded, failed, retried, retryable, and non-retryable cases.

## Notes

This follow-up should remain in EXP/runtime infrastructure unless it changes the CR-001 artifact contract, Phase 0 lifecycle, or broader provider routing architecture.

Reason:

```text
CR-001 defines what extraction results mean.
EXP runtime defines how provider calls are executed, retried, failed, and resumed.
```
