# Five-minute demonstration guide

This sequence is designed for an interview screen-share. It uses deterministic,
credential-free paths so the demonstration does not depend on model quota or
network availability.

## 1. Establish the business problem

Open the [project brief](portfolio_brief.md), then show the workflow graphic in the
[README](../README.md). Explain that LLM nodes organise research reasoning while
data checks, statistics, routing, revision limits, evidence status, and approval are
code-controlled.

## 2. Demonstrate research generalisation

```powershell
.\.venv\Scripts\python.exe -m examples.momentum_factor_demo
```

Open `reports/factor_research/momentum_factor_demo.md`. Point out that this example
does not use IVOL: the same `ModelDesign` routes a momentum signal to entity fixed
effects and a transaction-cost-aware backtest.

## 3. Demonstrate a business deliverable

```powershell
.\.venv\Scripts\python.exe -m examples.business_risk_consulting_demo
```

Open `reports/advisory/byd_risk_advisory_demo.md`, then compare it with the approved
[portfolio report](../reports/showcase/byd_risk_advisory.md). Highlight the Partner
View, risk matrix, action owners, timeline, KPIs, committee challenge, and evidence
appendix.

Then demonstrate the controlled financial-risk path:

```powershell
.\.venv\Scripts\python.exe -m examples.financial_anomaly_risk_demo
```

Open `reports/advisory/financial_anomaly_risk_demo.md`. Show the reason codes,
transparent thresholds, management actions, 8/8 IQR controls, input/output hashes,
and the fact that a passing automated review still leaves human sign-off pending.

For an industry-research alternative, run:

```powershell
.\.venv\Scripts\python.exe -m examples.baijiu_industry_research_demo
```

Open `reports/industry_research/baijiu_industry_research_demo.md` and highlight the
value chain, bounded peer snapshot, scenario triggers, monitoring indicators, and
explicit statement that two companies do not constitute a full industry census.

To demonstrate the bridge from disclosure intelligence to statistical research:

```powershell
.\.venv\Scripts\python.exe -m examples.byd_event_study_demo
```

Open `reports/event_study/byd_event_study_demo.md`. Show the pre-declared windows,
market-model parameters, daily abnormal returns, CAR significance, contamination
check, and the explicit separation between real disclosure evidence and fixture
returns.

To close with the platform's cross-asset strategy capability:

```powershell
.\.venv\Scripts\python.exe -m examples.a_share_market_strategy_demo
```

Open `reports/market_strategy/a_share_market_strategy_demo.md`. Show the bounded
five-signal score, style/sector matrix, three probability-constrained scenarios,
trigger conditions, monitoring list, and distinction between official facts and
offline normalized signals.

## 4. Demonstrate engineering controls

```powershell
.\.venv\Scripts\python.exe -m evals.release_benchmark --baseline evals/baseline.json
.\.venv\Scripts\python.exe scripts\docs_audit.py
.\.venv\Scripts\python.exe -m pytest -q
```

Explain that the release benchmark protects six routing contracts and nine showcase
deliverables, while the documentation audit prevents broken links, version drift,
and inconsistent quality commands.

## 5. Close with the boundary

Open [Capability maturity](capability_status.md). State clearly that quantitative
All six service lines now have end-to-end offline showcases. Clarify that this is
workflow readiness, not a claim that every licensed data source, live refresh path,
or production deployment control is complete.

Live Provider calls and public-data refreshes are optional follow-up demonstrations.
They should only be used when credentials, quota, cutoff dates, and network access
have been checked in advance.
