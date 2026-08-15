# Financial anomaly screening and engagement quality review

## Purpose

The corporate-advisory workflow screens explainable financial red flags and turns
them into a management action plan. It does not determine fraud, issue an audit
opinion, assign a credit rating, or replace professional judgement.

## Controlled workflow

```text
Corporate Advisory Intake
        ↓
Financial Risk Analysis (deterministic rules)
        ↓
Draft Report
        ↓
Internal Quality Review
        ↓
Pass ───────────────→ Human Sign-off ─→ Controlled Delivery
        ↘ Remediation Router
          ├─ Evidence Collection
          ├─ Financial Risk Analysis
          └─ Draft Report
```

Critical evidence, cutoff, reproduction, hash, consistency, or assurance-language
failures block delivery. Non-critical report-contract failures are routed back for
remediation, subject to the same revision limit used by other workflows.

## Screening catalogue

The versioned `financial-risk-scorecard-2.0` methodology covers 24 signals across:

- operating cash flow to net profit;
- accruals relative to assets;
- receivables and inventory growth relative to revenue;
- gross-margin deviation from a supplied peer median;
- non-recurring profit dependence;
- current ratio and net debt to operating cash flow;
- audit-opinion status, exchange inquiries, and regulatory penalties.
- ROE and net-margin deterioration, debt-to-assets, and interest coverage;
- receivable and inventory days, asset turnover, impairment, and goodwill;
- related-party exposure, customer/supplier concentration, and R&D capitalization.

Every rule records its value, threshold, trigger, weight, evidence IDs, management
interpretation, owner, timeline, actions, and KPIs. The composite score is the
triggered rule weight divided by the complete rule weight; it is an explainable
screening priority, not an estimated probability of fraud or default.

## Independent quality controls

The IQR layer independently recalculates the scorecard and checks:

1. evidence was available by the engagement cutoff;
2. every signal evidence ID resolves to a unique evidence record;
3. the same structured input reproduces the complete output;
4. weighted indicator coverage meets the minimum delivery threshold;
5. input/output hashes and methodology versions match the audit trail;
6. required report sections are present;
7. report score, level, and reason codes match structured output;
8. every triggered signal has an Owner, Timeline, action, and KPI;
9. prohibited audit-assurance or unsupported fraud conclusions are absent.

Automated IQR passing never creates a human approval. The checked-in showcase
therefore ends with `human_signoff=pending`.

## Data and production boundary

The engine accepts generic structured company inputs. The bundled showcase uses a
licensed synthetic fixture so it can be redistributed and reproduced; the live CLI
also assembles cutoff-controlled BaoStock ratios, CNInfo disclosures, and annual-
report audit wording. Complete statement fields can be injected through the tabular
point-in-time adapter. Production use still requires approved data licences, access
control, an immutable run log, and a qualified human approver.
