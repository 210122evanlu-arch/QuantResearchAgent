# Thesis-Guided IVOL Replication Profile

This profile translates the author's finalized undergraduate thesis into executable research requirements. It is a specification guide, not a claim that the free BaoStock MVP reproduces the thesis.

## Original empirical design

- Universe: Chinese A-share listed companies from January 2010 through December 2025.
- Final coverage: 5,568 companies, 192 monthly cross-sections, and 597,246 stock-month observations.
- Source: CSMAR daily/monthly trading data, financial indicators, and Fama-French five-factor data.
- Filters: exclude financial and real-estate firms; ST, `*ST`, and PT observations; listings younger than one year; missing key variables; and stock-months with fewer than 15 valid trading days.
- Outliers: two-sided winsorization of continuous variables at the 1st and 99th percentiles.
- IVOL: within-month residual standard deviation from daily Fama-French five-factor regressions.
- Belief-disagreement proxy: turnover.
- Main estimator: monthly Fama-MacBeth cross-sectional regressions with Newey-West inference.
- Mechanism variable: centered `IVOL × turnover` interaction.
- Additional tests: sequential 5-by-5 turnover/IVOL portfolio sorts, cross-sectional rank regression, and a bottom-30%-by-float-market-cap microcap subsample.

## Original reported results

- Baseline IVOL coefficient: -0.2296, Newey-West t-statistic -3.46.
- Raw IVOL-turnover interaction: -0.0303, t-statistic -3.30.
- Centered IVOL-turnover interaction: -0.0303, t-statistic -3.30.
- High-minus-low IVOL return in the lowest-turnover group: -0.0637% per month.
- High-minus-low IVOL return in the highest-turnover group: -1.5667% per month.
- Rank-interaction robustness coefficient: -0.0353, t-statistic -6.23.
- Microcap centered interaction: -0.0390, t-statistic -2.33, versus -0.0303 for the full sample.

## What the current free pipeline implements

`tools.thesis_ivol.prepare_thesis_ivol_features` adds auditable 1%/99% winsorization, turnover, centered interactions, cross-sectional rank interactions, and a monthly bottom-30% microcap flag. Raw pre-winsorization values are retained with `_raw` suffixes.

The BaoStock adapter now retains monthly turnover and records a new pipeline version in its cache key. A Data Revision can move through staged, larger compatible datasets supplied with repeated `--revision-data` command-line options. The Data and Experiment nodes share the selected revision index, so an expanded profile and the subsequent regression always use the same file and fingerprint.

## Remaining gap before a genuine replication

The free BaoStock pipeline currently estimates IVOL with a selected-universe single-index model. It does not supply CSMAR's point-in-time Fama-French five factors, full historical/deleted A-share universe, industry classifications, PT history, or a licensed all-market survivorship-safe panel. Its `future_return` is not yet a risk-free-adjusted excess return. Results from this path must therefore be labelled a free-data approximation.

A genuine thesis replication should ingest a licensed or otherwise verified dataset containing daily excess returns, `MKT`, `SMB`, `HML`, `RMW`, `CMA`, listing dates, historical security status, industry, float market capitalization, monthly turnover, and point-in-time book equity. Locked baseline, centered-interaction, rank-robustness, microcap Fama-MacBeth, and sequential 5-by-5 portfolio-sort specifications are implemented. A licensed point-in-time input is still required before these estimators can constitute a genuine replication.

## Corrected local v2 reconstruction

`data_sources.thesis_v2` now builds a separate, auditable local reconstruction from the files supplied by the thesis author:

- monthly stock return is compounded from validated daily price changes and is never derived from market capitalization;
- IVOL is the within-month residual standard deviation from the supplied CSMAR P9709 five-factor series, requiring at least 15 valid days and using `ddof=1`;
- Size is the natural log of month-end CSMAR `Dsmvtll`, BM is `1/PB` for positive PB, and turnover is monthly CSMAR `ToverOsM`;
- features at month `t` are retained only when the target is the immediately following calendar month;
- the P9709 stock-code scope, historical BaoStock ST/month-end-trading state, and an observable one-year listing-age proxy are enforced;
- qfq price histories that contain nonpositive prices or price changes outside exchange-limit buffers cause the entire affected stock-month to be excluded rather than clipped;
- every merge and exclusion count is written to an adjacent JSON audit manifest.

The current local output contains 440,107 stock-months for 4,471 securities from 2010-01 through 2025-11, with no duplicate stock-months, missing required model values, or target-date look-ahead violations. The locked v2 estimates support a negative IVOL slope and a negative IVOL-turnover interaction, but the result remains provisional because the local AKShare directory may omit delisted firms, the factor export has no RF column, and historical industry exclusions are unavailable.

### BaoStock target-return verification (v3)

The resumable BaoStock adapter downloaded unadjusted monthly `pctChg` for all 4,832 P9709-compatible securities in the historical universe: 640,301 security-month records with no failed codes. Replacing only the dependent variable and rebuilding from the IVOL intermediate cache produces 455,447 final stock-months for 4,472 securities.

Across 550,979 comparable intermediate records, AKShare and BaoStock monthly returns have correlation 0.995558 and median absolute difference 0.1356 percentage points. All five key specifications preserve their sign and significance under the BaoStock target:

- baseline IVOL: -0.515516, t=-6.390;
- centered IVOL-turnover interaction: -0.002803, t=-3.587;
- rank interaction: -0.031977, t=-5.922;
- highest-turnover high-minus-low IVOL return: -1.8442% per month, t=-6.177;
- microcap interaction: -0.003578, t=-2.925.

This resolves independent verification of the dependent variable. Daily IVOL was then checked on a reproducible stratified sample: three long-history securities from each of ten size deciles, with both Shanghai and Shenzhen represented in every decile. Re-estimating the same P9709 five-factor residual volatility from 116,477 BaoStock daily observations yields 5,657 comparable stock-months, an IVOL correlation of 0.991899, median absolute difference of 0.000297, and monthly-return correlation of 0.997988.

The daily check is strong evidence that the retained AKShare IVOL observations are broadly consistent with an independent return source, but it is not a full-market replacement.

### Risk-free and historical-industry corrections (v4/v5)

The thesis equation explicitly uses daily stock excess return and next-month excess return. Because the supplied CSMAR factor export contains the market risk premium but no standalone RF column, v4 uses the public ChinaBond three-month government yield curve as an explicit proxy. Annual percentage yields are converted to effective per-trading-day returns with 252-day annualization, backward-aligned to CSMAR factor dates with a maximum seven-day tolerance, and compounded by month. The original BaoStock target is retained as `future_return_raw`; `future_rf` is deducted to produce the model target.

Across 455,447 comparable stock-months, v3/v4 IVOL correlation is 0.999999996 with median absolute difference 0.000000330. Raw and excess next-month returns correlate at 0.999991776. As expected in regressions with monthly intercepts, RF correction has negligible impact on the locked slopes but makes the variable contract consistent with the thesis formula. The proxy is not represented as the unavailable original CSMAR RF series.

BaoStock's date-specific CSRC industry endpoint was cached at January and July 28 for 2010-2025 and backward-aligned without future classification use. v5 removes 12,067 financial and 14,560 real-estate stock-months, leaving 428,820 observations for 4,296 securities; 120 observations with blank industry labels are retained and disclosed. The baseline IVOL coefficient is -0.508487 (t=-6.195), centered IVOL-turnover interaction is -0.002961 (t=-3.716), rank interaction is -0.033287 (t=-6.285), highest-turnover high-minus-low IVOL return is -1.8805% (t=-6.241), and microcap interaction is -0.003380 (t=-2.730).

All five locked specifications remain negative and statistically significant. The remaining publication-grade gaps are a survivorship-safe full-market daily stock-return source, the original CSMAR RF series, and a higher-frequency authoritative historical industry classification.

## Staged revision example

```powershell
.\.venv\Scripts\python.exe main.py --live `
  --question "Test whether investor trading-belief disagreement amplifies the A-share IVOL discount" `
  --data data\baostock\ivol_thesis_10.parquet `
  --revision-data data\baostock\ivol_thesis_30.parquet `
  --revision-data data\baostock\ivol_thesis_50.parquet `
  --outlier-handling "1%/99% winsorization; raw values retained" `
  --survivorship-policy "Selected-code free-data approximation; survivorship bias remains" `
  --report reports\ivol_thesis_approximation.md
```
