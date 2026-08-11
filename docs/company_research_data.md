# Company Research Public-Data Layer

## Scope

The company-research workflow now accepts a point-in-time public-data package instead of relying on narrative fixtures. The data layer currently supports mainland A-share securities with explicit `.SH` or `.SZ` identifiers.

## Sources

- BaoStock: unadjusted daily prices, trading metrics, valuation multiples, and published quarterly financial indicators.
- CNInfo: official company-announcement metadata and public document links.

No API key is required. Source failures are surfaced as warnings or errors; the workflow does not substitute synthetic observations during a public-data run.

## Point-in-time controls

- Market rows after `as_of_date` are removed.
- Financial indicators are selected by `pubDate`, not only by reporting period.
- Announcements published after `as_of_date` are rejected by the schema.
- Every calculated metric points to an `EvidenceRecord`.
- Relative valuation requires supplied peers and synchronized market snapshots.

## Run the BYD public-data demo

```powershell
.\.venv\Scripts\python.exe -m examples.company_research_public_data_demo `
  --company-name "BYD Company Limited" `
  --security-code 002594.SZ `
  --peer "SAIC Motor=600104.SH" `
  --peer "Great Wall Motor=601633.SH" `
  --report reports\company_research\byd_public_data_report.md
```

The current business-diagnosis engine screens announcement titles and explicitly records that full-document interpretation is pending. Filing PDF extraction and LLM-assisted narrative synthesis belong to the next implementation round.
