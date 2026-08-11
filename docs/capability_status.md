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
| Event intelligence | Implemented supporting capability | Announcement/news deduplication, materiality assessment, watchlist and report-refresh decision; this is separate from a statistical event-study executor |
| Industry research | Route contract and template | Standardised intake, method selection and report template; dedicated data/execution workflow remains planned |
| Market strategy | Route contract and template | Standardised intake, regime/scenario method selection and report template; dedicated data/execution workflow remains planned |
| Event study | Route contract and template | Standardised intake and method selection; abnormal-return estimation and an approved end-to-end report remain planned |

The bundled HTTP executor currently enables the Moutai company-research and BYD
corporate-advisory showcases. Other workflows can be injected behind the same API
contract as their data licences and execution policies are approved.

“Offline showcase” means deterministic fixtures or frozen public-evidence snapshots
can reproduce the workflow without a paid model call. It does not mean that the
result is a current investment recommendation or a substitute for qualified review.
