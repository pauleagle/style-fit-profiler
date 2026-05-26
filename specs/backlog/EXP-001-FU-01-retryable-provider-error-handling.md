# EXP-001-FU-01: Retryable Provider Error Handling

## Metadata

```yaml
item_id: EXP-001-FU-01
item_type: follow-up
parent_type: EXP
parent_id: EXP-001
status: proposed
drill_down_status: complete
atomic_decomposition_status: da-reviewed
title: Retryable provider error handling
source_path: backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md
parent_spec_path: specs/backlog/EXP-001-gemini-image-analysis-extractor.md
root_spec_path: SPEC.md
related_items:
  - EXP-002
  - CR-001
integration_status: implementation-in-progress
workflow_step: Step 5 - Spec-Based Test Design
next_atomic_item: EXP-001-FU-01B
```

## Parent Trace

- Parent spec: [`EXP-001: Gemini Image Analysis Extractor`](EXP-001-gemini-image-analysis-extractor.md)
- Root index: [`SPEC.md`](../../SPEC.md)
- Source draft: [`backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md`](../../backlog/EXP-001-FU-01-Add-retryable-provider-error-handling.md)
- Related runtime flows: `EXP-002` batch helpers and `CR-001` native batch execution.

This follow-up does not reopen the completed EXP-001 helper work. It blocks only the next reliability step where manual Gemini / batch runtime should tolerate transient provider failures without corrupting partial output or misclassifying provider errors as prompt, parser, schema, or CR-001 semantic failures.

## Drill-down Gate

Gate status: `pass`

Reason: human decisions have resolved the retry layer boundary, single-image coverage, and delay retry policy. Atomic items have been decomposed and DA-reviewed; the next step is Step 5 test design for `EXP-001-FU-01A`.

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

## Atomic Decomposition

Status: `da-reviewed`

Implementation rule:

- Implement items in order unless a later human decision explicitly changes the order.
- Each item must keep `spec_refs` pointing to both `EXP-001-FU-01` and parent `EXP-001`.
- No item may call the real Gemini API in unit tests.
- No item may add real sleeps to tests; delay behavior must use deterministic calculation or an injected sleeper.
- Batch delay retry remains disabled by default until config explicitly enables it.

| ID | Status | Workflow step | Scope | Dependencies | Primary tests |
|---|---|---|---|---|---|
| `EXP-001-FU-01A` | implemented | Step 6 - Implementation Verified | Provider error model, classifier, and Gemini retry-delay parser. No command behavior change. | None | Classification fixtures for `RESOURCE_EXHAUSTED`, transient statuses, auth/config failures, unknown errors, and `Please retry in ...s` parsing. |
| `EXP-001-FU-01B` | accepted | Step 5 - Spec-Based Test Design | Config-owned provider retry policy defaults and validation under `reference_image_analysis_policy.provider_retry_policy`. Preserve existing `max_attempts` semantics. | `EXP-001-FU-01A` only for shared types if needed | Config load/default tests, invalid policy values, delay retry disabled default, `delay_retry_times=2`, `max_total_delay_seconds=120`, and CLI override precedence where a command already exposes retry flags. |
| `EXP-001-FU-01C` | accepted | Step 5 - Spec-Based Test Design | Retry decision and delay resolver, including `should_retry`, bounded delay calculation, delay retry budget, total-delay cap, and injected sleeper contract. No batch command integration yet. | `EXP-001-FU-01A`, `EXP-001-FU-01B` | Attempt budget tests, non-retryable failure tests, `max_attempts - 1` delay cap, `max_single_delay_seconds`, `max_total_delay_seconds`, buffer application only when delay enabled, and no-op injected sleeper calls. |
| `EXP-001-FU-01D` | accepted | Step 5 - Spec-Based Test Design | Single-image command diagnostics for legacy `gemini_image_probe` and CR-001 `cr001_gemini_probe single`: classify provider failures and fail fast without automatic retry. | `EXP-001-FU-01A`, optionally `EXP-001-FU-01B` for display policy | Simulated provider quota/auth errors prove single commands do not retry, return non-zero, and surface machine-readable provider metadata or clear diagnostic output without writing misleading semantic artifacts. |
| `EXP-001-FU-01E` | accepted | Step 5 - Spec-Based Test Design | Legacy EXP / Phase 0 batch integration for `gemini_batch_probe` and related batch report metadata. Delay retry stays off by default. | `EXP-001-FU-01A` through `EXP-001-FU-01C` | Quota error followed by success, exhausted quota error, non-retryable provider error, delay disabled immediate retry, delay enabled injected sleeper, partial output preservation, and summary retry counts. |
| `EXP-001-FU-01F` | accepted | Step 5 - Spec-Based Test Design | CR-001 batch integration for `cr001_gemini_probe batch` / `run_cr001_batch_extraction`, keeping CR-001 native semantic artifact clean while adding provider metadata to runtime report. | `EXP-001-FU-01A` through `EXP-001-FU-01C`; can reuse batch helpers from `EXP-001-FU-01E` | Failed-image scope retry, valid native records preserved, failed provider metadata in CR-001 batch report, no runtime fields inside native records, delay policy read from config, and non-retryable failures excluded from retry scope. |
| `EXP-001-FU-01G` | accepted | Step 5 - Spec-Based Test Design | Manual command docs, README / spec traceability, and final verification notes. No code behavior ownership. | `EXP-001-FU-01A` through `EXP-001-FU-01F` | Documentation readback, traceability search for parent/follow-up IDs, `git diff --check`, and full unit suite if any code changed in the previous items. |

### Item Notes

#### `EXP-001-FU-01A`: Provider Error Classifier

Purpose:

- Create the shared runtime vocabulary for provider failures before any command behavior changes.
- Keep parser/schema output retries separate from provider transport/runtime retries.

Non-goals:

- No config loading.
- No retry loop.
- No command output changes.

Completion signal:

- Provider status, retryability, retry delay, and diagnostic message can be represented as deterministic in-memory data.

#### `EXP-001-FU-01B`: Config-Owned Retry Policy

Purpose:

- Move retry policy defaults into `style_profiler_config.json` under `reference_image_analysis_policy.provider_retry_policy`.
- Preserve existing command-facing `max_attempts` behavior while preventing new delay-related magic numbers in runner code.

Non-goals:

- No sleeping.
- No batch report changes.
- No provider call retry loop.

Completion signal:

- Config defaults and validation can produce a retry policy object with no provider call involved.

#### `EXP-001-FU-01C`: Retry Decision And Delay Resolver

Purpose:

- Centralize retry decisions and delay calculation so legacy EXP batch and CR-001 batch do not reimplement the same policy.
- Provide an injected sleeper contract for later integration tests without real waiting.

Non-goals:

- No direct CLI changes.
- No report serialization ownership.

Completion signal:

- A retryable provider error plus policy can produce deterministic retry/no-retry and optional wait decisions.

#### `EXP-001-FU-01D`: Single-Image Fail-Fast Diagnostics

Purpose:

- Make the human decision "single does not retry" testable and visible.
- Prevent single-image commands from silently inheriting batch retry loops.

Non-goals:

- No automatic retry for single-image commands.
- No batch summary fields.

Completion signal:

- A simulated provider failure in a single-image command is classified, reported, and exits without a second provider call.

#### `EXP-001-FU-01E`: Legacy Batch Integration

Purpose:

- Apply provider retry classification and policy to the existing EXP / Phase 0 batch flow.
- Preserve immediate retry behavior by default while adding structured provider metadata.

Non-goals:

- No CR-001 native artifact changes.
- No global scheduler or resumable batch state.

Completion signal:

- Legacy batch reports distinguish retryable provider failures from invalid model output and non-retryable provider failures.

#### `EXP-001-FU-01F`: CR-001 Batch Integration

Purpose:

- Add provider retry behavior to the CR-001 batch runtime without polluting CR-001 native semantic records.
- Preserve valid native records when a provider-backed batch partially fails.

Non-goals:

- No CR-001 schema redesign.
- No Phase 0 projection policy change.

Completion signal:

- CR-001 batch report carries provider retry metadata, while `phase0/cr001_reference_image_analysis.json` remains semantic-only.

#### `EXP-001-FU-01G`: Docs And Traceability

Purpose:

- Close the follow-up loop across raw backlog, formal spec, parent EXP spec, root `SPEC.md`, README/index files, and tests.

Non-goals:

- No new runtime behavior.
- No real API validation requirement.

Completion signal:

- The follow-up can be traced from root index to parent spec to formal spec to raw backlog and back.

## Devil's Advocate Review Of Atomic Decomposition

Review status: `pass-after-revision`

Conclusion:

- The initial five-item draft was directionally correct, but it hid two high-risk boundaries: config-vs-delay ownership and single-image fail-fast behavior.
- The revised seven-item split is accepted for Step 5 test design because each item has a bounded owner, explicit non-goals, and a test surface that can run without real Gemini calls or real waits.
- Implementation must start with `EXP-001-FU-01A`; batch integrations must not begin before the shared classifier, config policy, and retry resolver are test-covered.

| ID | Severity | Issue | Resolution | Blocks Step 5 |
|---|---|---|---|---|
| `DA-EXP-001-FU-01-001` | High | The original `Retry policy and delay resolver` item mixed config schema, default ownership, retry decision logic, delay calculation, and sleeper behavior. | Split into `EXP-001-FU-01B` for config-owned policy and `EXP-001-FU-01C` for retry decision / delay resolver / injected sleeper. | No |
| `DA-EXP-001-FU-01-002` | High | The original split did not give `single 不 retry` its own implementation/test slice, making it easy for single commands to accidentally inherit batch retry behavior. | Added `EXP-001-FU-01D` as an explicit single-image fail-fast diagnostics item covering legacy and CR-001 single commands. | No |
| `DA-EXP-001-FU-01-003` | Medium | Legacy EXP batch and CR-001 batch integration could duplicate retry classification and drift in report semantics. | Shared behavior is locked into `EXP-001-FU-01A` through `EXP-001-FU-01C`; `EXP-001-FU-01E` and `EXP-001-FU-01F` are adapter/report integration slices only. | No |
| `DA-EXP-001-FU-01-004` | Medium | Delay retry can make tests slow/flaky or unexpectedly sleep during manual runs. | Delay retry remains config-disabled by default; `EXP-001-FU-01C` owns injected sleeper behavior and tests must use no-op sleepers. | No |
| `DA-EXP-001-FU-01-005` | Medium | CR-001 runtime metadata could leak into the CR-001 native semantic artifact. | `EXP-001-FU-01F` explicitly limits provider metadata to the CR-001 batch report and forbids runtime fields inside native records. | No |
| `DA-EXP-001-FU-01-006` | Low | The docs/final traceability item could become a dumping ground for unfinished implementation gaps. | `EXP-001-FU-01G` is documentation and traceability only; any behavior gap found there must reopen the relevant earlier item, not be fixed in docs. | No |

Open questions before implementation:

- None. All DA findings above are resolved by the revised split.

Next workflow step:

- Begin Step 5 test design for `EXP-001-FU-01A`.

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
