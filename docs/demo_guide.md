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

## 4. Demonstrate engineering controls

```powershell
.\.venv\Scripts\python.exe -m evals.release_benchmark --baseline evals/baseline.json
.\.venv\Scripts\python.exe scripts\docs_audit.py
.\.venv\Scripts\python.exe -m pytest -q
```

Explain that the release benchmark protects six routing contracts and five showcase
deliverables, while the documentation audit prevents broken links, version drift,
and inconsistent quality commands.

## 5. Close with the boundary

Open [Capability maturity](capability_status.md). State clearly that quantitative
research, company research, and corporate advisory have end-to-end showcases;
industry research, market strategy, and statistical event study currently have
route/template contracts and remain expansion work.

Live Provider calls and public-data refreshes are optional follow-up demonstrations.
They should only be used when credentials, quota, cutoff dates, and network access
have been checked in advance.
