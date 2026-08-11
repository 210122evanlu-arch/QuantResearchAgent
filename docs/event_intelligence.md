# Event Intelligence and Research Refresh

The event-intelligence layer converts disclosure and news metadata into an auditable research-maintenance decision. It complements the company-research workflow; it does not replace full-document interpretation.

## Pipeline

```text
CNInfo disclosures ─┐
                    ├─> EvidenceRecord -> deduplicate -> classify -> materiality
RSS / Atom feeds ───┘                                      |
                                                            v
                         no_action / watchlist / refresh_report / escalate_review
```

Each event receives a stable fingerprint, source type, category, impact direction, materiality, evidence ID, and list of affected report sections.

## Evidence policy

| Evidence | Permitted automatic action |
| --- | --- |
| Company disclosure or regulatory source | May trigger report refresh or committee escalation |
| News with no primary-source confirmation | Watchlist only, regardless of headline materiality |
| Duplicate or near-duplicate item | Removed before trigger evaluation |
| Evidence published after `as_of_date` | Excluded to preserve point-in-time integrity |

News ingestion uses configurable RSS/Atom feeds and stores only title, link, publication time, source, and a short metadata summary. Feed licensing and downstream article access remain deployment responsibilities.

## Trigger policy

- Critical verified events escalate to committee review.
- High-materiality verified events refresh affected report sections.
- Medium/low events and unverified news enter the watchlist.
- No event after the prior report date produces `no_action`.

Run the offline fixture:

```powershell
.\.venv\Scripts\python.exe -m examples.event_intelligence_demo
```

The API accepts the same evidence bundle at `POST /v1/events/analyze`.
