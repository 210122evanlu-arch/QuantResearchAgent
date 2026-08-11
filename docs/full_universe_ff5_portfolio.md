# Historical Universe, Five-Factor IVOL, and 5x5 Portfolio Sorts

## Historical A-share universe

`BaoStockHistoricalUniverseBuilder` queries the BaoStock trading calendar, selects the final trading day of every month, and downloads that date's complete security snapshot. The filter retains Shanghai `6xxxxx`, Shenzhen `0xxxxx`/`3xxxxx`, and optionally Beijing A-share codes while excluding index codes such as `sh.000001`.

Snapshots preserve security name, trading status, and an ST/PT name flag. Shanghai stock codes are restricted to the 600/601/603/605 and 688/689 families; Shenzhen stock codes are restricted to 000-003 and 300/301, so exchange indices such as `sz.399001` cannot enter the panel. Taking the union over historical month-ends captures securities that later disappear from the current universe. This improves on selecting only currently known codes, but it is not automatically a survivorship-safe research panel: historical industry classification, authoritative IPO dates, delisting reasons, Beijing-exchange provider coverage, and provider completeness still require audit.

```powershell
.\.venv\Scripts\python.exe -m examples.baostock_universe_demo `
  --start 2010-01-01 `
  --end 2025-12-31
```

The result is cached under `data/baostock/universe/`. A full 192-month request is intentionally separate from the LangGraph node because it makes hundreds of network calls and should finish before an atomic Data Revision switches datasets.

## Strict five-factor input

The project does not label the selected-universe market proxy as Fama-French five-factor IVOL. A genuine input file must contain unique daily dates and numeric `MKT`, `SMB`, `HML`, `RMW`, `CMA`, and `RF` columns. Units must be declared with `--factor-percent`; the loader never guesses.

The daily stock file must contain decimal `return`, `turnover`, `size`, and `bm` fields keyed by `stock_id` and `date`. Every stock date must match a factor date. Monthly IVOL is the residual standard deviation from a daily five-factor excess-return regression, with at least 15 valid days by default. The output records the factor-file SHA-256 fingerprint and sets next-month excess return as the target.

```powershell
.\.venv\Scripts\python.exe -m examples.ff5_ivol_data_demo `
  --stocks data\licensed\a_share_daily.parquet `
  --factors data\licensed\csmar_ff5_daily.csv `
  --factor-percent `
  --output data\prepared\a_share_ff5_ivol.parquet
```

No CSMAR data is bundled or redistributed by this repository.

### CSMAR daily export

`load_csmar_five_factor_data` understands the native multi-panel CSMAR export and requires an explicit selection instead of silently mixing market definitions. The thesis working code used `P9709`, portfolio method `1` (2x3), and the `1` suffix (float-market-cap weighting). The checked export contains 3,886 trading dates from 2010-01-04 through 2025-12-31 for that specification.

The CSMAR five-factor export contains the market risk premium but does not contain a standalone daily risk-free rate. Strict mode therefore requires a separate risk-free file. `--reproduce-original-workflow` is an explicit compatibility mode: it sets `RF=0`, regresses raw stock returns as the original working code did, and records `return_basis=raw_return_original_replication` plus `residual_ddof=0`. This differs from the thesis equation, which specifies excess stock returns and a sample-standard-deviation denominator.

```powershell
.\.venv\Scripts\python.exe -m examples.csmar_ff5_data_demo `
  --source data\licensed\csmar\five_factor_daily_123315679\STK_MKT_FIVEFACDAY.csv `
  --output data\licensed\csmar\five_factor_daily_123315679\ff5_p9709_2x3_float.parquet `
  --reproduce-original-workflow
```

All licensed source and derived files remain under Git-ignored `data/`. The generated manifest records source and normalized fingerprints but never embeds the licensed observations.

## Sequential 5x5 portfolio engine

The `portfolio_sort` estimator now executes the thesis order exactly:

1. At each month-end, sort stocks into five turnover groups, T1 through T5.
2. Within each turnover group, sort stocks into five IVOL groups, I1 through I5.
3. Compute equal-weight next-month returns for all 25 cells.
4. Compute I5 minus I1 in each turnover group.
5. Apply HAC/Newey-West inference to each monthly high-minus-low time series.

Periods unable to populate all 25 cells are skipped and disclosed. The result contains 25 structured portfolio cells plus five high-minus-low statistical results. Final Markdown reports render the complete 5x5 table directly from `ExperimentResult`; no LLM rewrites the numbers.

`run_thesis_replication_suite` now includes the portfolio sort alongside locked baseline, centered-interaction, rank-robustness, and microcap Fama-MacBeth models.
