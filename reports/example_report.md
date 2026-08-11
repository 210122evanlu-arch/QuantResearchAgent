# Research Report: Does IVOL predict future stock returns?

> Committee status: **APPROVED**

## Executive Summary

Objective: Verify the seven-node workflow with offline fixtures. Committee decision: approved. Experiment conclusion: Statistically significant variables: IVOL

## Research Background

Research gap: This demo deliberately uses an offline literature fixture. Theoretical mechanism: Synthetic mechanism for workflow testing.

## Literature References

| Year | Paper | Authors | Source | DOI / URL |
| ---: | --- | --- | --- | --- |
| 2020 | Offline Fixture Paper - Not a Real Citation | Fixture Author | Local test fixture | https://example.invalid/offline-fixture |

## Hypotheses

- IVOL negatively predicts future stock returns

## Methodology

OLS Regression - Revised Fixture; formula=future_return ~ IVOL + size; standard errors=Newey-West.

| Field | Verified value |
| --- | --- |
| Model | OLS Regression - Revised Fixture |
| Formula | `future_return ~ IVOL + size` |
| Estimator | `ols` |
| Experiment method | OLS with HAC covariance |

## Data

Synthetic two-stock fixture; monthly; 2023-01-31 to 2023-06-30; prepared rows=12; missing rate=0; duplicate rate=0.

| Metric | Verified value |
| --- | ---: |
| Prepared rows | 12 |
| Estimated rows | 12 |
| Data fingerprint | `sha256:ea2267007e3253400b17cb1f1bb64ac5d4df61775d5dc971fd3bd386cbc70ce8` |
| Prepared-data fingerprint | `sha256:ea2267007e3253400b17cb1f1bb64ac5d4df61775d5dc971fd3bd386cbc70ce8` |
| Experiment-data fingerprint | `sha256:ea2267007e3253400b17cb1f1bb64ac5d4df61775d5dc971fd3bd386cbc70ce8` |

## Experiment Results

| Variable | Coefficient | Std. Error | t-stat | p-value | 95% CI | Significant |
| --- | ---: | ---: | ---: | ---: | --- | :---: |
| IVOL | -1.9069493 | 0.1366249 | -13.957553 | 2.1053436e-07 | [-2.2160162, -1.5978823] | Yes |
| size | 0.0082254264 | 0.0048628882 | 1.6914693 | 0.12500281 | [-0.0027751911, 0.019226044] | No |

### Model Metrics

| R-squared | Adjusted R-squared | RMSE | Information Coefficient | Observations |
| ---: | ---: | ---: | ---: | ---: |
| 0.71221459 | 0.64826228 | 0.0058226042 | 0.84392807 | 12 |

## Robustness

Alternative covariance estimator: passed

| Check | Method | Result | Passed |
| --- | --- | --- | :---: |
| Alternative covariance estimator | Compare HAC inference with HC3 | Significance classifications are stable | Yes |

## Risk Disclosures

- This research output is not investment advice and requires human review.
- The literature set contains offline or non-Crossref fixtures.

## Limitations

- Offline synthetic fixture; not investment evidence

## Recommendations

- Maintain out-of-sample monitoring and independent review before use.

## Committee Review

No unresolved committee issues were recorded.

## Conclusion

The research committee approved the reported specification and results, subject to the stated limitations.

## Provenance

- Source digest: `sha256:d86ed4e5abcfc567a93974e425eed01292601bb3ff18fd1d4921891ec6f78916`
- Data fingerprint: `sha256:ea2267007e3253400b17cb1f1bb64ac5d4df61775d5dc971fd3bd386cbc70ce8`
- Numeric tables were rendered directly from ExperimentResult.
- This research output is not investment advice.
