# CR-001-FU-01 Deprecate legacy Phase 0 default paths

## Metadata

```yaml
item_id: CR-001-FU-01
item_type: follow-up
parent_cr: CR-001
title: Deprecate legacy Phase 0 default paths
status: in-progress
drill_down_status: complete
devils_advocate_status: complete
atomic_decomposition_status: da-reviewed
compatibility_policy: compatibility-layer
primary_baseline: cr001-native-artifact
legacy_policy: deprecated-explicit-projection
formal_spec_path: specs/backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md
parent_spec_path: specs/backlog/CR-001-appeal-point-and-art-style-extraction.md
root_spec_path: SPEC.md
workflow_step: Step 4 - Atomic Decomposition
next_workflow_step: Start CR-001-FU-01C Root Phase 0 contract wording cleanup
```

## Drill-down Status

Formal spec：[`specs/backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md`](../specs/backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md)

Current status：Devil's Advocate review complete；atomic cleanup in progress.
`CR-001-FU-01B` README manual command docs cleanup is complete；next remaining
slice：`CR-001-FU-01C`.

## Summary

CR-001 native artifact is now the Phase 0 primary baseline.

This follow-up exists because some legacy Phase 0 default paths remained active after CR-001 native baseline work was completed. In particular, existing single-image and batch entrypoints could still emit the old three-aspect Phase 0 output, which conflicts with the expected replacement semantics of CR-001.

The goal of this follow-up is to demote legacy Phase 0 behavior into an explicit deprecated compatibility projection, while ensuring all default Phase 0 entrypoints produce CR-001 native output.

## Background

Human / agent踩坑紀錄：

- 使用者原本的 mental model 是：CR-001 完成後，Phase 0 就應該是 CR 後的新樣子，不需要保留舊 Phase 0 作為預設。
- Agent 一開始的 mental model 偏向保守相容：先新增 CR-001 native artifact 與 CR-001 manual probe，讓舊 Phase 0 / EXP 入口平行保留。
- 第一個坑：完成 CR-001 native baseline 後，舊 `gemini_batch_probe` 仍是三面向 Phase 0 輸出；這違反 human 對「CR 取代 Phase 0」的預期。
- 第二個坑：修 batch 後，human 手動跑 `gemini_image_probe reference_images/ref-001.png`，發現 single 入口仍是舊 prompt / 舊三面向輸出。這顯示 replacement 決策必須覆蓋所有既有入口，而不是只修剛被看見的一條路。
- 第三個坑：`python -m style_fit_profiler.gemini_image_probe` 出現 `RuntimeWarning`，原因是 import graph 讓目標模組在 `-m` 執行前已進入 `sys.modules`。已用 lazy import 修正。
- Playbook 修正方向：CR drill-down 必須把「是否向下相容 / 是否替換既有行為」當成必答題，不能靠 agent 自行假定保守相容，也不能靠 human 隱含期待 replacement。

## Decision

Use the following policy:

```yaml
compatibility_policy: compatibility-layer
primary_baseline: cr001-native-artifact
legacy_phase0_schema: deprecated-explicit-projection
default_behavior: cr001-native
```

Meaning:

- CR-001 native artifact is the new Phase 0 primary baseline.
- Legacy Phase 0 three-aspect schema is deprecated as a default output.
- Legacy output may remain only as an explicit compatibility projection.
- Default entrypoints must not silently emit legacy Phase 0 output.
- Compatibility behavior must be named, documented, and explicitly invoked.

## Scope

This follow-up should review and update all default Phase 0 paths, including but not limited to:

- `gemini_image_probe`
- `gemini_batch_probe`
- CR-001 native artifact builder / writer
- any manual probe scripts
- any Phase 0 / EXP command examples
- tests and fixtures
- README / SPEC / backlog references
- any remaining old prompt files
- any output paths that still imply the legacy schema is primary

## Required behavior

### Default behavior

The following should produce CR-001 native output by default:

```bash
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png
python -m style_fit_profiler.gemini_batch_probe
```

Default output should target the CR-001 native artifact structure, such as:

```text
phase0/cr001_reference_image_analysis.json
```

### Legacy behavior

Legacy Phase 0 output may remain only if it is explicit.

Acceptable examples:

```bash
python -m style_fit_profiler.project_cr001_to_legacy_phase0
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png --legacy-phase0
python -m style_fit_profiler.gemini_batch_probe --output-format legacy-phase0
```

Legacy output must be documented as deprecated / compatibility-only.

## Deprecated legacy behavior

The old Phase 0 three-aspect schema should be treated as deprecated.

It may be retained only for:

- migration comparison
- regression reference
- older tooling compatibility
- temporary transition support

It must not be used as:

- the default Phase 0 output
- the primary artifact
- the canonical CR-001 result
- the expected schema for new tests
- the default prompt path for new development

## Naming guidance

Recommended naming for legacy compatibility pieces:

```text
legacy_phase0_projection.py
legacy_phase0_prompt.py
project_cr001_to_legacy_phase0.py
deprecated_legacy_phase0_schema
```

Recommended wording:

```text
Deprecated after CR-001 native baseline replacement.
Kept only for compatibility projection, migration checks, or regression comparison.
Do not use as the default Phase 0 extraction path.
```

## Acceptance criteria

- `python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png` produces CR-001 native output by default.
- `python -m style_fit_profiler.gemini_batch_probe` produces CR-001 native batch output by default.
- No default Phase 0 entrypoint emits the old three-aspect Phase 0 schema.
- Any legacy `style_gene_candidates.json` generation is moved behind an explicit projection command, function, or flag.
- Old Phase 0 prompt files are either removed from default import paths or moved under a clearly named `legacy` / `deprecated` path.
- Tests assert CR-001 native schema as the default baseline.
- Legacy schema tests, if retained, are clearly marked as compatibility / deprecated tests.
- README / SPEC / backlog notes no longer describe old Phase 0 output as the primary artifact.
- Running modules with `python -m ...` does not emit import-order `RuntimeWarning`.
- CR-001 contains a backlink to this follow-up item.

## Suggested implementation checklist

- [ ] Identify all Phase 0 / EXP entrypoints.
- [ ] Identify all old three-aspect schema emitters.
- [ ] Identify all old prompt references.
- [ ] Change default single-image probe to CR-001 native output.
- [ ] Change default batch probe to CR-001 native output.
- [ ] Move old schema generation behind explicit projection.
- [ ] Rename or relocate legacy prompt / schema files.
- [ ] Add deprecation comments or warnings for legacy paths.
- [ ] Update tests to protect CR-001 native default behavior.
- [ ] Add compatibility tests only where needed.
- [ ] Update README / SPEC / backlog references.
- [ ] Add backlink in CR-001.

## Backlink to CR-001

Add the following section to CR-001:

```md
## Follow-ups

- `CR-001-FU-01`: Deprecate legacy Phase 0 default paths and promote CR-001 native artifact as the Phase 0 primary baseline.

Reason: CR-001 replacement semantics were accepted, but legacy Phase 0 default paths remained active in some entrypoints.
```

## Playbook lesson

For future CR work, the CR drill-down must always answer:

```md
For every CR:
- Is this an additive extension, a replacement, or a compatibility layer?
- If replacement or compatibility-layer, which existing entrypoints must change default behavior?
- Which legacy artifacts remain?
- Are legacy artifacts default, deprecated, explicit opt-in, or scheduled for removal?
- Which tests protect the new default?
- Which docs must change to avoid old behavior being treated as primary?
```

Key rule:

> If compatibility is retained, it must be explicit opt-in, not the default path.

## Notes

This follow-up is not a new independent EXP.

It is a CR-001 follow-up cleanup item that resolves incomplete migration from legacy Phase 0 behavior to CR-001 native Phase 0 baseline.
