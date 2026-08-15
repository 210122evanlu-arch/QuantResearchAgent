# Financial Research & Advisory Platform

The repository now treats IVOL as one quantitative research demo rather than the
product boundary. A validated `ResearchRequest` enters a deterministic intent
router and is assigned to one of six specialised workflows:

- company research;
- industry research;
- quantitative research;
- market strategy;
- event study;
- corporate advisory.

## Compatibility boundary

The original seven-node quantitative graph remains the production implementation
for `quant_research`. Its Experiment node, data fingerprints, revision loop, and
traceable report are unchanged. The platform layer sits above it, so new domain
workflows can be added without weakening the verified quant path.

## Shared contracts

`schemas/platform.py` defines channel-neutral intake, evidence, findings, generic
analysis artifacts, and workflow selection. A finding marked `verified` must cite
at least one `EvidenceRecord`, and an `AnalysisBundle` rejects dangling evidence
identifiers.

`AnalysisEngineRegistry` is the execution boundary for reusable capabilities.
It never falls back silently: requesting an unavailable analysis method raises an
explicit error. `AnalysisExecutionNode` is the method-neutral node for future
company, industry, market, event, and advisory workflows. The existing Experiment
node remains its specialised quantitative counterpart.

Corporate advisory can select the deterministic financial-anomaly engine through
the `financial_anomaly` topic. That workflow adds a post-draft Internal Quality
Review: the scorecard is independently recalculated, evidence and cutoff controls
are checked, report values are reconciled to structured output, and failed controls
are either routed for remediation or blocked. Passing automated controls still
leaves human sign-off pending.

## Extension sequence

1. Register the current quant graph as the `quant_research` workflow handler.
2. Implement company disclosure and financial-analysis engines.
3. Add company and industry workflows using shared evidence contracts.
4. Add market, event-study, and corporate-advisory workflows.
5. Run engagement-quality controls and preserve explicit human sign-off state.
6. Render each controlled result with the template selected by the router.

No task is routed by free-form LLM output alone. The LLM may recommend a task type,
but application code must validate it through `ResearchRequest` and the enum-based
router before execution.
