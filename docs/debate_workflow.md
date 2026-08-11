# Research Debate Subgraph

The optional debate workflow is designed for material or contested research and
advisory conclusions. It is not a replacement for the Research Committee review.

```text
Debate Initialise
  -> Proponent
  -> Challenger
  -> Moderator
  -> Round Control
       -> Proponent (continue)
       -> Debate Synthesis (conclude or hard limit)
```

## Control model

The Moderator may conclude early. Application code owns the hard limit, which is
validated before any model call and must be between one and five rounds. The
default is three. A `continue` decision is schema-valid only when the current round
added new information and identifies at least one unresolved issue.

If the Moderator still requests continuation at the hard limit, the graph produces
a `DebateResult` with `stopped_by_limit=true`. Raw discussion is retained as
structured rounds; downstream reports should render only consensus findings,
disputed findings, unresolved issues, and the final synthesis.

## Evidence boundary

Every Proponent and Challenger argument must cite an evidence ID already present
in the input `AnalysisBundle`. The Challenger may reference only argument IDs from
the current Proponent case. These constraints are checked in code after structured
LLM validation.

The subgraph is currently standalone. Once a task-level Debate Gate is implemented,
it can be inserted between Analysis Execution and Review without changing the
existing quantitative workflow internals.
