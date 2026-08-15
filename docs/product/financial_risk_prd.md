# PRD: Listed-company financial anomaly warning

## Client problem

Risk, investment, and advisory teams need to prioritise unusual financial patterns
across listed companies without treating a screening flag as a fraud conclusion.
Manual reviews are slow, thresholds are often opaque, and report evidence can be
difficult to trace back to the engagement cutoff.

## MVP users and decisions

| User | Decision supported |
| --- | --- |
| Advisory project manager | Which issues require client interviews or data requests? |
| Risk team | Which financial signals enter the next monitoring cycle? |
| Research team | Which reported performance indicators require deeper validation? |
| Quality reviewer | Is the draft reproducible and safe to send for human sign-off? |

## Functional requirements

1. Accept two comparable reporting periods, peer benchmark, audit opinion, inquiry
   and penalty counts, evidence records, and an explicit `as_of_date`.
2. Calculate versioned financial signals using deterministic code.
3. Return risk score, level, reason codes, interpretations, and actions.
4. Preserve evidence IDs and SHA-256 input/output fingerprints.
5. Generate a management report with Owner, Timeline, KPI, and assurance boundary.
6. Run independent quality controls and route remediable failures to the owning node.
7. Require explicit human sign-off before the output is labelled a final deliverable.

## Non-functional requirements

- The same input and methodology version must reproduce the same scorecard.
- Post-cutoff evidence and unresolved evidence IDs must block delivery.
- Secrets, licensed raw data, and generated client reports must not enter Git.
- Rule thresholds must be visible and replaceable with sector-specific policies.
- LLMs may explain evidence but may not calculate or override financial metrics.

## Out of scope for the MVP

- statutory audit or internal-audit assurance;
- fraud, default, or misconduct determination;
- cross-sector threshold calibration from labelled historical samples;
- automatic ingestion of every listed company and filing format;
- production identity, role-based approval, and immutable external audit storage.

## Success measures

- 100% reason-code traceability to evidence;
- deterministic reproduction of every scorecard;
- zero final-labelled reports without approved human sign-off;
- complete Owner, Timeline, action, and KPI fields for every triggered signal;
- test coverage for pass, remediation, blocked, and pending-sign-off paths.
