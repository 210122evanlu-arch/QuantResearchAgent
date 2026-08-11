# Capability maturity

QuantResearchAgent separates platform routing coverage from end-to-end delivery
readiness. A registered route means the intake contract, default analysis methods,
and report template are defined; it does not by itself imply that every data source
and executor is production-ready.

| Service line | Current maturity | Verified implementation |
| --- | --- | --- |
| Quantitative research | End-to-end offline showcase | Seven-node research/revision workflow, OLS, Fama–MacBeth, fixed effects, portfolio analysis, transaction-cost-aware backtesting, IVOL and momentum cases |
| Listed-company research | End-to-end offline showcase | Public-data package, filing evidence, company analysis engines, committee review, DCF/relative valuation, Moutai report, injectable API runner |
| Corporate advisory | End-to-end offline showcase | Risk register, Debate Gate, committee challenge, priority matrix, Owner/Timeline/KPI roadmap, BYD report, injectable API runner |
| Event intelligence | Implemented supporting capability | Announcement/news deduplication, materiality assessment, watchlist and report-refresh decision feeding research maintenance |
| Industry research | End-to-end offline showcase | Industry, peer, and scenario engines; committee revision loop; three-scenario matrix; bounded high-end baijiu report; injectable API runner |
| Market strategy | End-to-end offline showcase | Deterministic five-signal regime score, style/sector views, probability-constrained scenarios, committee loop, A-share strategy report, injectable API runner |
| Event study | End-to-end offline showcase | Market-model estimation, daily AR, multi-window CAR, significance testing, contamination review, committee loop, BYD method report, injectable API runner |

The bundled HTTP executor has a representative offline showcase for all six service
lines. Other workflows and live data providers can be injected behind the same API
contract as their data licences and execution policies are approved.

“Offline showcase” means deterministic fixtures or frozen public-evidence snapshots
can reproduce the workflow without a paid model call. It does not mean that the
result is a current investment recommendation or a substitute for qualified review.
