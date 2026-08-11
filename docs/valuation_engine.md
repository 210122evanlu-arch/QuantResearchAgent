# DCF and Sensitivity Engine

The deterministic valuation engine separates numerical calculation from forecast authorship. It never invents cash-flow forecasts: callers must supply explicit annual free cash flow, discount rate, terminal growth, net debt, shares outstanding, and currency.

## Outputs

- Present value of the explicit forecast period;
- present value of terminal value;
- enterprise value, equity value, and value per share;
- terminal-value share of enterprise value;
- configurable WACC × terminal-growth sensitivity cells;
- warnings for terminal-value concentration, non-positive equity value, or invalid scenarios.

`DCFInput` enforces increasing unique forecast years and `discount_rate > terminal_growth_rate`. The company-analysis registry exposes the engine as `AnalysisMethod.DCF_VALUATION`; the company router adds it only when the request explicitly includes the `dcf` topic.

DCF findings are marked `inferred`, even when historical inputs are evidence-backed, because forecast assumptions remain analytical judgments. The output is a scenario framework rather than a target-price recommendation.

Run the illustrative fixture:

```powershell
.\.venv\Scripts\python.exe -m examples.dcf_valuation_demo
```
