# BaoStock Free Data Adapter

BaoStock is the default real-market-data source for the MVP and requires no API key. The adapter downloads selected A-share daily histories plus quarterly profit records and stores raw and prepared Parquet files under the Git-ignored `data/baostock/` directory.

The panel contains `stock_id`, `date`, `target_date`, `future_return`, `IVOL`, `size`, `bm`, and `momentum`. Quarterly `totalShare` is merged only after its published `pubDate`; `size` is `log(close * totalShare)`. This avoids silently substituting turnover or trading amount for market capitalization. `bm` is inverse `pbMRQ`, and momentum compounds months t-12 through t-2.

Run a small selected-code sample:

```powershell
.\.venv\Scripts\python.exe -m examples.baostock_ivol_data_demo `
  --codes sz.000001,sh.600000,sz.000858,sh.600519,sz.000333 `
  --start 2023-01-01 `
  --end 2025-12-31
```

The date range should cover at least 13 months because momentum needs months t-12 through t-2. The output panel can be passed to `main.py --live --data ...`.

Research limitations remain material:

- A hand-selected current universe does not eliminate survivorship bias.
- Single-index IVOL is not a Fama-French residual-volatility estimate.
- ST and suspended observations remain visible in raw data and need a declared sample policy.
- Adjustment conventions, share units, corporate actions, delistings, and fundamentals should be independently reconciled before institutional use.
- BaoStock data must be used and redistributed only under its current provider terms.

The manifest records the provider, request, adjustment mode, point-in-time join policy, methodology, and limitations. BaoStock credentials are not needed. Tushare remains an optional adapter for teams that later obtain suitable access.
