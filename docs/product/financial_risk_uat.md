# UAT: Financial anomaly warning

| ID | Scenario | Expected result |
| --- | --- | --- |
| UAT-01 | Valid two-period data and complete evidence | Scorecard is reproduced and IQR passes |
| UAT-02 | Receivables grow over 15 points faster than revenue | `FR-AR-GAP` triggers with Owner, Timeline, and KPI |
| UAT-03 | Evidence publication date is after `as_of_date` | IQR decision is `blocked` |
| UAT-04 | Signal references an unknown evidence ID | IQR decision is `blocked` |
| UAT-05 | Draft omits a required report section | Decision is `remediation_required` and target is `draft_report` |
| UAT-06 | Stored output differs from independent recalculation | IQR decision is `blocked` |
| UAT-07 | Report contains unsupported fraud-assurance language | IQR decision is `blocked` |
| UAT-08 | IQR passes without a named reviewer | Report remains `human_signoff=pending` |
| UAT-09 | Human approval is supplied while IQR failed | Controlled delivery rejects the override |
| UAT-10 | Same input is rerun under the same methodology | Score and reason codes remain identical |
| UAT-11 | A financial row is published after `as_of_date` | Row is excluded before period selection |
| UAT-12 | Consumer and manufacturing profiles receive the same inventory gap | Each uses its own versioned threshold |
| UAT-13 | A field required by one rule is absent | Rule is `not_available`, not `not_triggered` |
| UAT-14 | Weighted data coverage is below 50% | IQR requires evidence remediation |
| UAT-15 | Annual-report page states standard unqualified opinion | Status is standard; “unqualified” is not misread as a reservation |

The automated test suite implements the core pass, remediation, blocking,
reproduction, and pending-sign-off scenarios. Production UAT must additionally
cover access roles, licensed data lineage, concurrency, retention, and client-level
approval policies.
