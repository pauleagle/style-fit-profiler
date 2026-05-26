# CR-001-FU-01: Deprecate Legacy Phase 0 Default Paths

## Metadata

```yaml
item_id: CR-001-FU-01
item_type: follow-up
parent_type: CR
parent_id: CR-001
title: Deprecate legacy Phase 0 default paths
status: implemented
drill_down_status: complete
devils_advocate_status: complete
atomic_decomposition_status: da-reviewed
compatibility_policy: compatibility-layer
primary_baseline: cr001-native-artifact
legacy_policy: deprecated-explicit-projection
source_path: backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md
parent_spec_path: specs/backlog/CR-001-appeal-point-and-art-style-extraction.md
root_spec_path: SPEC.md
related_items:
  - CR-001
  - CR-001-08
  - EXP-001
  - EXP-002
workflow_step: Step 6 - Implementation Verified
next_workflow_step: none
```

## Parent Trace

- Parent spec: [`CR-001: Appeal Point and Art Style Extraction`](CR-001-appeal-point-and-art-style-extraction.md)
- Root index: [`SPEC.md`](../../SPEC.md)
- Source draft: [`backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md`](../../backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md)

This follow-up cleans up replacement semantics after CR-001 v1 native baseline
was accepted. It does not reopen CR-001 schema design. Its job is to ensure that
default Phase 0 manual entrypoints no longer silently emit the old three-aspect
legacy schema, while any compatibility projection remains explicit and
deprecated.

## Drill-down Gate

Gate status: `pass-for-da-review`.

Reason: the replacement-vs-compatibility decision is clear, current code already
aligns the most visible single-image and batch manual entrypoints to CR-001
native defaults, and the remaining work can be reviewed as bounded cleanup
slices instead of an open-ended schema redesign.

Current evidence:

- `gemini_image_probe` defaults to the CR-001 backend and requires
  `--backend legacy` for the old EXP Phase 0 trait JSON path.
- `gemini_batch_probe` defaults to the CR-001 backend and requires
  `--backend legacy` for the old `style_gene_candidates.json` batch projection.
- `cr001_gemini_probe single` and `cr001_gemini_probe batch` write CR-001 native
  artifacts and do not write `style_gene_candidates.json`.
- Tests already assert the manual single and batch defaults produce
  `phase0/cr001_reference_image_analysis.json` and reject legacy-only flags on
  CR-001 defaults.
- Root `SPEC.md`, README, older EXP specs, notebook helpers, and Phase 0 config
  still contain legacy Phase 0 wording or APIs. These are not automatically
  wrong, but they must be labeled as baseline legacy / compatibility behavior
  rather than the CR-001 primary path.

## Drill-down Decisions

| ID | Status | Question | Decision | Blocks DA |
|---|---|---|---|---|
| `DD-CR-001-FU-01-001` | `resolved` | Is this additive, replacement, or compatibility-layer work? | It is replacement cleanup with an explicit compatibility layer. CR-001 native artifact is the default Phase 0 manual Gemini baseline; legacy Phase 0 output may remain only when explicitly requested. | No |
| `DD-CR-001-FU-01-002` | `resolved` | Which artifact is primary? | `phase0/cr001_reference_image_analysis.json` is primary for CR-001 native analysis. `phase0/cr001_batch_run_report.json` is runtime/report metadata. `style_gene_candidates.json` is legacy Phase 0 or optional projection, not the CR-001 primary artifact. | No |
| `DD-CR-001-FU-01-003` | `resolved` | Which default entrypoints must use CR-001 native output? | `python -m style_fit_profiler.gemini_image_probe <image>` and `python -m style_fit_profiler.gemini_batch_probe` must default to CR-001 native output. The dedicated `cr001_gemini_probe` entrypoints are already native-only. | No |
| `DD-CR-001-FU-01-004` | `resolved` | How can legacy output remain available? | Legacy three-aspect output can remain behind explicit controls such as `--backend legacy` or a future named projection command. It must not be selected by default and must be documented as deprecated compatibility behavior. | No |
| `DD-CR-001-FU-01-005` | `resolved` | Should `CR-001-08` be implemented here? | No. `CR-001-08` remains deferred until projection policy is decided. This follow-up may name projection work, but it must not silently implement a lossy CR-001-to-legacy mapping. | No |
| `DD-CR-001-FU-01-006` | `resolved-by-da-review` | Which legacy APIs are allowed to stay as baseline Phase 0 support? | Keep deterministic Phase 0 baseline APIs and tests for `v0.1.0`; this follow-up targets manual Gemini default paths and docs, not removal of the deterministic Phase 0 candidate schema. | No |
| `DD-CR-001-FU-01-007` | `resolved-by-da-review` | Which docs are stale enough to require cleanup? | README manual Gemini examples, root `SPEC.md` Phase 0 wording, older EXP notes, notebook helper wording, and raw backlog future-flag examples must be reviewed so they do not present legacy Gemini output as the CR-001 primary path. | No |
| `DD-CR-001-FU-01-008` | `resolved` | What tests protect the new default? | Existing command tests cover CR-001 default backend for single and batch, no default `style_gene_candidates.json`, and rejection of legacy-only flags without `--backend legacy`. Atomic cleanup should keep or strengthen these tests. | No |
| `DD-CR-001-FU-01-009` | `resolved` | How should `python -m` import-order warnings be handled? | Keep lazy-import boundaries for CR-001 adapters so module execution does not preload the target module. Add or preserve smoke coverage if future refactors touch import graph behavior. | No |

## Devil's Advocate Review

Gate status: `ready-for-atomic-decomposition`.

Conclusion: no DA finding blocks atomic decomposition. The main risk is not
runtime behavior; current code and tests already protect the most visible
single-image and batch defaults. The risk is documentation and compatibility
language drifting into promises that the CLI does not actually expose, or
accidentally treating the deterministic v0.1.0 Phase 0 baseline as something to
remove.

| ID | Severity | Objection | Decision | Blocks atomic decomposition |
|---|---|---|---|---|
| `DA-CR-001-FU-01-001` | High | Raw backlog examples mention future-style controls such as `--legacy-phase0`, `--output-format legacy-phase0`, and `project_cr001_to_legacy_phase0`, but the current implemented opt-in is `--backend legacy`. If copied into README or tests as-is, the spec would promise non-existent CLI contracts. | Treat those raw examples as source brainstorming only. Formal implementation and user docs must describe the current explicit opt-in as `--backend legacy` unless a later accepted item intentionally adds a new projection command or alias. | No |
| `DA-CR-001-FU-01-002` | High | "Deprecate legacy Phase 0" can be over-read as deleting the deterministic v0.1.0 Phase 0 candidate schema, `phase0.py` helpers, notebook preview, or legacy regression tests. That would break the accepted baseline. | Preserve deterministic Phase 0 baseline and legacy candidate-schema tests. This follow-up only demotes legacy Gemini/manual default paths from primary CR-001 behavior and labels retained compatibility paths clearly. | No |
| `DA-CR-001-FU-01-003` | High | README still shows manual Gemini examples where default `gemini_image_probe` / `gemini_batch_probe` commands are adjacent to `--raw` and `--prompt-file` examples without `--backend legacy`, which now conflicts with CR-001 default behavior. | First implementation cleanup should update README examples so default commands produce CR-001 native artifacts, and legacy-only `--raw` / `--prompt-file` examples include `--backend legacy`. | No |
| `DA-CR-001-FU-01-004` | Medium | Root `SPEC.md` still describes Phase 0 as producing `style_gene_candidates.json`. Some of that is still correct for the deterministic baseline, so a blanket rewrite to CR-001 native output would be wrong. | Update root wording narrowly: deterministic v0.1.0 Phase 0 keeps `style_gene_candidates.json`; CR-001 manual Gemini Phase 0 defaults use `phase0/cr001_reference_image_analysis.json`; projection to `style_gene_candidates.json` remains explicit / compatibility / deferred by `CR-001-08` policy. | No |
| `DA-CR-001-FU-01-005` | Medium | EXP-001 / EXP-002 / EXP-003 and notebook docs can remain valuable historical planning notes, but if they describe old Gemini output as current primary behavior, they will keep reintroducing the same confusion. | Review and relabel only active-looking command examples and helper descriptions. Do not rewrite historical context unless it directly misroutes current use. | No |
| `DA-CR-001-FU-01-006` | Medium | The code path is already mostly compliant, so an implementation round could waste effort by changing behavior instead of tightening docs and verification. | Treat code changes as non-primary for this follow-up. Start with docs/status cleanup, then run focused tests/readback to confirm defaults still hold. Only change code if DA/readback finds a real mismatch. | No |
| `DA-CR-001-FU-01-007` | Low | Import-order `RuntimeWarning` was fixed through lazy imports, but future import graph edits could regress it. | Keep import-order coverage conditional. Add or run smoke coverage only if a future atomic item touches module imports or warning behavior reappears. | No |

DA resolution notes:

- `CR-001-FU-01A` traceability/status sync is already completed by the drill-down
  setup and does not need a separate implementation slice unless links drift.
- `CR-001-FU-01B` README manual command docs cleanup is complete.
- `CR-001-FU-01C` root `SPEC.md` contract wording cleanup is complete; it
  separates deterministic v0.1.0 `style_gene_candidates.json` baseline from
  CR-001 manual Gemini native defaults without rewriting accepted Phase 0
  behavior.
- `CR-001-FU-01D` legacy prompt/schema and planning-doc wording cleanup is
  complete; older EXP / notebook / raw backlog wording is now labeled as
  deterministic baseline, legacy compatibility, or brainstorming-only where
  appropriate.
- `CR-001-FU-01E` default behavior regression verification is complete.
- `CR-001-FU-01F` import-order smoke coverage is complete. The compatibility
  help text was also tightened so legacy-only flags are visibly documented as
  requiring `--backend legacy`.

## Required Behavior

Default behavior:

- `python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png`
  writes CR-001 native output by default.
- `python -m style_fit_profiler.gemini_batch_probe` writes CR-001 native batch
  output by default.
- Default CR-001 paths must not write `phase0/style_gene_candidates.json`.
- Legacy-only flags such as `--prompt-file` and `--raw` must require
  `--backend legacy` on `gemini_image_probe`.
- Legacy batch prompt files must require `--backend legacy` on
  `gemini_batch_probe`.

Legacy behavior:

- Legacy Phase 0 three-aspect output may remain for regression, compatibility,
  notebook preview, migration comparison, or older tooling.
- Any retained legacy behavior must be named as legacy / deprecated /
  compatibility-only.
- Any future projection from CR-001 native artifacts to legacy
  `style_gene_candidates.json` must be explicit and must respect the deferred
  `CR-001-08` projection-policy decision.

## Acceptance Criteria

- [x] Raw backlog, formal follow-up spec, parent CR-001 spec, root `SPEC.md`,
  and backlog index can trace to one another.
- [x] CR-001 parent spec contains a backlink to `CR-001-FU-01`.
- [x] `gemini_image_probe` default remains CR-001 native and legacy output
  requires explicit opt-in.
- [x] `gemini_batch_probe` default remains CR-001 native and legacy output
  requires explicit opt-in.
- [x] CR-001 native default paths do not write `style_gene_candidates.json`.
- [x] Legacy Phase 0 docs and commands are labeled as deprecated,
  compatibility, or non-primary where they remain.
- [x] Root `SPEC.md` no longer presents the legacy three-aspect Gemini output as
  the CR-001 primary artifact.
- [x] Existing deterministic Phase 0 baseline behavior remains intact unless a
  later accepted spec explicitly changes it.
- [x] `python -m` entrypoints do not emit import-order `RuntimeWarning`.
- [x] Tests cover CR-001 native defaults and explicit legacy opt-in behavior.

## DA-reviewed Atomic Items

These items are accepted as the post-DA decomposition surface. They should still
be executed one at a time and checkpointed before moving to the next item.

| Item | Status | Scope | DA decision |
|---|---|---|---|
| `CR-001-FU-01A` | completed-by-drill-down-setup | Traceability and status sync | Raw backlog, formal follow-up spec, parent CR-001 spec, root index, and backlog index now trace to one another. Reopen only if links drift. |
| `CR-001-FU-01B` | completed | README manual command docs cleanup | README examples now state that default single/batch commands produce CR-001 native artifacts, and legacy-only `--raw` / `--prompt-file` examples include `--backend legacy`. |
| `CR-001-FU-01C` | completed | Root Phase 0 contract wording | Root `SPEC.md` now separates deterministic v0.1.0 `style_gene_candidates.json` baseline from CR-001 native manual Gemini defaults without rewriting accepted deterministic Phase 0 behavior. |
| `CR-001-FU-01D` | completed | Legacy prompt/schema and planning-doc wording | EXP-001 / EXP-002 / EXP-003 and raw backlog wording now labels deterministic baseline, legacy compatibility, and brainstorming-only examples without promising non-existent flags. |
| `CR-001-FU-01E` | completed | Default behavior regression verification | Focused regression and full unittest pass; existing tests preserve CR-001 default single/batch commands, no default legacy output, and explicit `--backend legacy` opt-in. |
| `CR-001-FU-01F` | completed | Import-order smoke coverage | `python -W error::RuntimeWarning -m ... --help` smoke checks pass for `gemini_image_probe`, `gemini_batch_probe`, and `cr001_gemini_probe`. |

## Non-goals

- Do not redesign the CR-001 native schema.
- Do not implement `CR-001-08` projection until projection policy is accepted.
- Do not remove deterministic Phase 0 baseline support from `v0.1.0`.
- Do not make real Gemini API calls in unit tests.
- Do not write or commit generated `runs/` artifacts as part of this follow-up.

## Testing Implications

Focused tests should cover:

- Default single-image manual Gemini command writes
  `phase0/cr001_reference_image_analysis.json`.
- Default batch manual Gemini command writes
  `phase0/cr001_reference_image_analysis.json` and
  `phase0/cr001_batch_run_report.json`.
- Default CR-001 manual paths do not write `phase0/style_gene_candidates.json`.
- Legacy single-image and batch paths require explicit `--backend legacy`.
- Legacy-only prompt/raw flags are rejected when the backend is CR-001.
- Import-order smoke coverage for `python -m` entrypoints if import graph changes.

Minimum validation for spec-only edits:

- `rg -n "CR-001-FU-01|legacy|--backend legacy|cr001_reference_image_analysis" SPEC.md specs README.md backlog src tests`
- `git diff --check`

## Verification Summary

Completed validation:

- `python -m unittest tests.test_gemini_image_probe tests.test_gemini_batch_probe tests.test_cr001_gemini_probe tests.test_cr001_batch_integration`
- `python -m unittest discover -s tests`
- `python -W error::RuntimeWarning -m style_fit_profiler.gemini_image_probe --help`
- `python -W error::RuntimeWarning -m style_fit_profiler.gemini_batch_probe --help`
- `python -W error::RuntimeWarning -m style_fit_profiler.cr001_gemini_probe --help`
- `git diff --check`

## Handoff

`CR-001-FU-01` is implemented. Do not start projection work or add new legacy
CLI aliases as part of this follow-up unless a later accepted spec explicitly
changes the projection policy.
