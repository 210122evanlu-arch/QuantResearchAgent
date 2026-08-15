# Point-in-time financial-risk data

## Live public-data path

The financial-risk workflow can now assemble a listed-company screen without an
LLM or paid API key:

1. BaoStock financial endpoints are queried by year and quarter.
2. Every row is filtered by `pubDate <= as_of_date` before selection.
3. The latest period is compared with the same quarter of the prior year whenever
   available; fallback to another period is disclosed as a warning.
4. CNInfo announcements are paginated through the cutoff and title-classified as
   inquiry-related disclosures, regulatory actions, or explicit audit disclosures.
5. If audit status is not explicit in a title, the latest full annual-report PDF is
   downloaded, hashed, and searched for audit-opinion pages.
6. All metrics and regulatory indicators retain evidence IDs and publication times.

Run a live historical screen:

```powershell
.\.venv\Scripts\python.exe -m examples.public_financial_risk_demo `
  --company-name 贵州茅台酒股份有限公司 `
  --security-code 600519.SH `
  --as-of-date 2025-06-30 `
  --industry-profile consumer
```

Generated live reports and downloaded filings remain Git-ignored. Public endpoints
can be unavailable, rate-limited, revised, or incomplete; source errors are surfaced
rather than replaced with generated data.

## Licensed or complete statement path

`TabularFinancialRiskProvider` accepts a standardized pandas table or CSV-derived
DataFrame. Required columns are:

- `security_code`;
- `period_end`;
- `publication_date`.

Any `FinancialStatementSnapshot` field can be supplied as an additional column,
including statement values, impairment, goodwill, concentration, and R&D
capitalization. The adapter filters by publication date, selects two comparable
periods, creates stable evidence IDs, and rejects fewer than two pre-cutoff periods.

The table source name and data licence remain operator responsibilities. The
repository does not redistribute licensed market or accounting datasets.

## Coverage and missingness

The v2 engine distinguishes three outcomes for each rule:

- `triggered`: data is available and the calibrated threshold is breached;
- `not_triggered`: data is available and the threshold is not breached;
- `not_available`: the necessary field or benchmark was not supplied.

The composite risk score divides triggered rule weight by available rule weight.
It must therefore be read together with `data_coverage`. Coverage below 60% raises
a comparability warning; coverage below 50% fails the IQR data-coverage control and
routes the report for evidence remediation. A low score with low coverage cannot be
presented as evidence of low risk.

## Industry threshold profiles

Thresholds are selected by enum and versioned code, not by free-form LLM output.
Current profiles are:

| Profile | Calibration emphasis |
| --- | --- |
| `general` | Cross-sector baseline |
| `manufacturing` | Inventory, supplier concentration, and operating leverage |
| `consumer` | Cash conversion, inventory efficiency, and margin structure |
| `technology` | Liquidity, goodwill, customer concentration, and R&D capitalization |
| `real_estate` | Cash conversion, inventory cycle, leverage, and debt coverage |

Financial institutions are intentionally excluded from these profiles because bank,
broker, and insurer balance sheets require dedicated regulatory-capital and asset-
quality metrics.

## Current 24-signal catalogue

The engine covers cash conversion, accruals, receivable and inventory growth gaps,
peer gross-margin deviation, non-recurring profit dependence, current ratio, net
debt coverage, debt-to-assets, interest coverage, ROE decline, net-margin decline,
receivable days, inventory days, asset turnover, impairment, goodwill, related-party
transactions, customer concentration, supplier concentration, R&D capitalization,
audit opinion, exchange inquiries, and regulatory penalties.

Title classification does not infer the substance of an inquiry or penalty. Full
legal or audit conclusions require document-level review and a qualified human
approver.
