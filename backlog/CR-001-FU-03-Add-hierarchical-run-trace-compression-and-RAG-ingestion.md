# CR-001-FU-03 Add hierarchical run trace compression and RAG ingestion

## Status

Proposed

## Parent

- CR-001: Appeal point and art style extraction
- Follow-up of: CR-001-FU-02 Refine extraction semantics and prompt contract

## Summary

Add a governed runtime-memory path for CR-001 experiment runs by converting run artifacts into hierarchical semantic summaries that can later be ingested into RAG.

This follow-up introduces a lightweight version of a **run trace → semantic compression → evaluation summary → curated RAG knowledge** loop. The goal is not to immediately automate all learning, but to make each run observable, comparable, compressible, and reusable.

## Motivation

CR-001-FU-02 is expected to produce multiple trial runs while refining extraction semantics and prompt contracts. These runs may reveal useful patterns such as:

- prompt wording that causes semantic drift
- model-specific extraction bias
- single-image vs batch extraction differences
- unstable fields in the CR-001 native artifact
- recurring DA review objections
- reusable correction patterns
- cases where output structure looks valid but semantic quality is weak

If these observations only remain in chat logs or ad hoc notes, the workflow loses reusable experience. This follow-up captures that experience as structured runtime memory.

## Design Intent

This item explores a controlled version of **experience auto-distillation**.

The intended loop is:

```text
run execution
→ raw trace capture
→ sliding semantic compression
→ run-level summary
→ evaluation / DA review summary
→ curated RAG-ready knowledge
→ future playbook / skill refinement
```

This is inspired by the idea that not every run should become permanent knowledge, but every meaningful run should leave enough trace evidence to support later review, replay, comparison, and distillation.

## Scope

### In Scope

- Define a minimal run metadata schema.
- Define compression levels for run artifacts.
- Produce RAG-ready markdown summaries for selected runs.
- Preserve traceability from compressed summaries back to raw run artifacts.
- Add trust and review metadata to prevent failed or noisy runs from polluting RAG.
- Support future drill-down and Devil's Advocate review.
- Keep the first implementation file-based and local-first.

### Out of Scope

- Full automatic model fine-tuning.
- Full automatic curator approval.
- Production telemetry capture.
- Vector database integration beyond file-based RAG preparation.
- Mandatory ingestion of every raw trace into RAG.
- Replacing existing CR-001 native artifact outputs.

## Proposed Directory Layout

```text
phase0/
  runs/
    CR-001-FU-02/
      run-YYYYMMDD-NNN/
        run-metadata.json
        input-manifest.json
        prompt-snapshot.md
        raw-output.json
        normalized-output.json
        errors.json
        trace.jsonl
        eval-summary.json
        run-summary.md
        da-review.md
        rag-card.md

  runtime-knowledge/
    cr001/
      run-summaries/
        run-YYYYMMDD-NNN.md
      evaluation-summaries/
        run-YYYYMMDD-NNN.eval.md
      distilled-lessons/
        extraction-semantics.md
        prompt-contract-lessons.md
        model-behavior-notes.md
```

The exact paths may be adjusted during drill-down if they conflict with the current project structure.

## Compression Levels

Use hierarchical compression levels to avoid putting noisy raw traces directly into RAG.

| Level | Name | Description | Default RAG Use |
|---|---|---|---|
| L0 | Raw trace | Full prompt, tool calls, raw model output, errors, timing, environment notes | No, only for audit / replay |
| L1 | Sliding window summary | Local summaries over trace segments or execution phases | Optional, only for debugging |
| L2 | Run summary | One run's goal, setup, result, issues, observations, and decision | Yes |
| L3 | Experiment summary | Cross-run patterns for a CR/FU item | Yes |
| L4 | Distilled lesson | Stable reusable rule, playbook candidate, or skill candidate | Yes, after review |

## Minimal Run Metadata

```json
{
  "schema_version": "cr001.run.v1",
  "run_id": "run-YYYYMMDD-NNN",
  "parent_cr": "CR-001",
  "parent_fu": "CR-001-FU-02",
  "scenario": "refine extraction semantics and prompt contract",
  "input_mode": "single | batch",
  "input_refs": [],
  "model_provider": "",
  "model_name": "",
  "prompt_version": "",
  "artifact_schema_version": "cr001.v1",
  "status": "success | failed | partial",
  "compression_level": "L0",
  "trust_level": "raw | reviewed | accepted | deprecated",
  "review_state": "unreviewed | da_reviewed | human_accepted | rejected",
  "known_issues": [],
  "output_artifacts": [],
  "source_trace_refs": []
}
```

## RAG Card Format

Each selected run may produce a compact `rag-card.md`.

Recommended sections:

```markdown
# Run Card: run-YYYYMMDD-NNN

## Metadata

- Parent: CR-001-FU-02
- Scenario:
- Input mode:
- Model:
- Prompt version:
- Artifact schema version:
- Status:
- Trust level:
- Review state:
- Compression level: L2

## Run Goal

## Key Observations

## Extraction Drift / Semantic Issues

## DA Review Findings

## Reusable Lessons

## Decision

- keep | ignore | investigate | promote_to_playbook | promote_to_skill

## Source Trace References
```

## Devil's Advocate Review Hook

The DA review should challenge whether a run summary is actually reusable knowledge.

Suggested DA questions:

1. Is this observation based on one run only, or repeated evidence?
2. Could this be model-specific noise rather than a general workflow pattern?
3. Is the issue caused by prompt wording, schema ambiguity, input image ambiguity, or model limitation?
4. Would adding this lesson to RAG increase future accuracy, or pollute retrieval?
5. Should this be marked as accepted knowledge, investigation note, or deprecated finding?
6. Does this finding belong in CR-001 only, or should it be promoted into a general playbook/skill?

## Drill-down Prompts

During workflow drill-down, use questions like:

```text
Please drill down CR-001-FU-03 into atomic implementation steps.
Focus on the smallest file-based MVP that can capture one CR-001-FU-02 run, produce a run-summary.md, and generate a RAG-ready card without changing existing CR-001 outputs.
```

```text
Please perform Devil's Advocate review on the proposed CR-001-FU-03 design.
Challenge whether run trace compression could pollute RAG, overfit to noisy model behavior, or create misleading reusable lessons.
Suggest guardrails before implementation.
```

```text
Please compare L0/L1/L2/L3/L4 compression boundaries.
Identify which levels should be ingested into RAG by default, which should remain audit-only, and which require human approval.
```

## Acceptance Criteria

- A minimal run metadata format is defined.
- Compression levels L0-L4 are documented.
- RAG ingestion rules distinguish raw, reviewed, accepted, and deprecated knowledge.
- The first implementation can generate a run summary from one selected CR-001-FU-02 run.
- The generated summary preserves source trace references.
- Raw traces are not ingested into RAG by default.
- Failed or partial runs can be retained without being treated as accepted knowledge.
- DA review questions are available for future refinement.
- Existing CR-001 native artifact outputs remain compatible.

## Risks

### RAG Pollution

If raw or low-quality summaries are ingested without review, future retrieval may amplify failed experiments or temporary workaround logic.

Mitigation:

- Require `trust_level` and `review_state` metadata.
- Default raw traces to audit-only.
- Promote only reviewed L2-L4 summaries into RAG.

### Overfitting to Provider or Model Quirks

A behavior observed in one model may not represent a general extraction principle.

Mitigation:

- Mark model-specific observations clearly.
- Prefer cross-run and cross-model evidence before promoting to L4 distilled lessons.

### Semantic Loss During Compression

Important details may be lost when compressing raw traces into summaries.

Mitigation:

- Preserve `source_trace_refs`.
- Keep L0 raw artifacts available for audit.
- Add `semantic_loss_risk` when needed.

### Premature Automation

Trying to automate curator decisions too early may reduce trust in the workflow.

Mitigation:

- Start with file-based summaries.
- Keep human acceptance as the first knowledge admission gate.
- Add automation only after repeated stable patterns emerge.

## Open Questions

- Should run IDs be global across the whole project or scoped under each CR/FU?
- Should `rag-card.md` be generated for every run or only selected runs?
- Should DA review be a required step before any L3/L4 artifact is created?
- Should `trust_level` and `review_state` be shared across other future CR items?
- Should this become a general runtime-memory playbook after CR-001 validation?

## Expected Future Extensions

- Cross-run comparison report.
- Extraction stability scoring.
- Model-specific behavior registry.
- Prompt contract change history.
- RAG ingestion manifest.
- Curator / knowledge admission playbook.
- Promotion path from run finding to playbook item.
- Promotion path from playbook item to skill rule.

## Relationship to Personal AI Runtime Direction

This item may become a bridge between `style-fit-profiler` and the broader `personal-ai-runtime` direction.

Potential future mapping:

```text
style-fit-profiler run traces
→ runtime knowledge cards
→ RAG retrieval
→ playbook refinement
→ skill extraction
→ governed agent workflow improvement
```

This aligns with the broader goal of turning AI-assisted development runs into reusable, reviewable, and governed operational knowledge.
