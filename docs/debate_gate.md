# Debate Gate

The Debate Gate sits after Analysis Execution and before Research Committee review.
It is deterministic and auditable; an LLM does not decide whether it should receive
additional debate calls.

The gate enters debate when one or more of these conditions is present:

- the user explicitly requests debate;
- the task is material corporate advisory or market strategy;
- a finding is below the configured confidence threshold;
- a finding is inferred or has insufficient evidence;
- analysis warnings or evidence conflicts remain.

An explicit user opt-out or disabled platform policy skips debate. The gate writes a
`DebateGateResult` containing the decision, exact triggers, rationale, and configured
hard maximum. The maximum is validated to one through five rounds.

`build_gated_debate_workflow` demonstrates the integration boundary:

```text
Analysis -> Debate Gate -> Debate Subgraph -> Review (future integration)
                       \-> Skip -----------> Review (future integration)
```

The current BYD public-data advisory demo exercises the enter path. Unit tests also
exercise the skip path and prove that no debate node is called when the gate skips.
