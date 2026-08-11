# Tushare Pro Data Adapter

The MVP adapter downloads selected A-share histories from the `daily` and `daily_basic` endpoints and stores raw and prepared Parquet files under the ignored `data/tushare/` directory. A configuration hash prevents one request range from being mistaken for another, while `--refresh` explicitly replaces the matching cache.

The prepared monthly panel contains `stock_id`, `date`, `target_date`, `future_return`, `IVOL`, `size`, `bm`, and `momentum`. IVOL is the monthly standard deviation of residuals from a daily single-index regression against the equal-weight return of the selected stocks. Size is the logarithm of Tushare `total_mv`; `bm` is inverse price-to-book; momentum compounds months t-12 through t-2.

This is an executable research fixture, not the final institutional definition. In particular:

- Selecting currently known codes does not eliminate survivorship bias.
- Equal-weight single-index IVOL is not Fama–French residual volatility.
- `daily_basic` and some other endpoints require sufficient Tushare points.
- Downloaded data must not be committed or redistributed without checking the provider agreement.
- A credible A-share study still needs delisted securities, listing-age filters, suspension/ST treatment, industry classifications, publication-date-safe fundamentals, and independent data reconciliation.

No Token is written to manifests, logs, cache names, or generated panels.
