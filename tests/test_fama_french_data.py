from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data_sources.fama_french import (
    CsmarFactorDataConfig,
    FactorDataConfig,
    FactorDataError,
    load_csmar_five_factor_data,
    load_five_factor_data,
    prepare_five_factor_ivol_panel,
)


def _csmar_file(path: Path) -> pd.DataFrame:
    rows = []
    for market_type in ("P9709", "P9714"):
        for portfolios in (1, 2):
            for index, date_value in enumerate(("2024-01-02", "2024-01-03")):
                rows.append(
                    {
                        "MarkettypeID": market_type,
                        "TradingDate": date_value,
                        "Portfolios": portfolios,
                        "RiskPremium1": 0.01 + index,
                        "RiskPremium2": 0.02 + index,
                        "SMB1": 0.001,
                        "SMB2": 0.002,
                        "HML1": 0.003,
                        "HML2": 0.004,
                        "RMW1": 0.005,
                        "RMW2": 0.006,
                        "CMA1": 0.007,
                        "CMA2": 0.008,
                    }
                )
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)
    return frame


def _factor_file(path: Path) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", "2024-02-29")
    sequence = np.arange(len(dates), dtype=float)
    frame = pd.DataFrame(
        {
            "date": dates,
            "MKT": np.sin(sequence / 3) / 100,
            "SMB": np.cos(sequence / 4) / 100,
            "HML": np.sin(sequence / 5 + 0.3) / 100,
            "RMW": np.cos(sequence / 7 + 0.2) / 100,
            "CMA": np.sin(sequence / 11 + 0.7) / 100,
            "RF": 0.0001,
        }
    )
    frame.to_csv(path, index=False)
    return frame


def _stock_daily(factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stock_number, stock_id in enumerate(("A", "B"), start=1):
        for index, row in factors.iterrows():
            factor_return = sum(
                float(row[column]) * (0.2 + stock_number / 10)
                for column in ("MKT", "SMB", "HML", "RMW", "CMA")
            )
            rows.append(
                {
                    "stock_id": stock_id,
                    "date": row["date"],
                    "return": 0.0001
                    + factor_return
                    + np.sin(index * 1.7 + stock_number) / 1000,
                    "turnover": 1.0 + stock_number / 10,
                    "size": 15.0 + stock_number,
                    "bm": 0.4 + stock_number / 10,
                }
            )
    return pd.DataFrame(rows)


def test_five_factor_loader_and_ivol_panel(tmp_path) -> None:
    path = tmp_path / "ff5.csv"
    factors = _factor_file(path)
    dataset = load_five_factor_data(FactorDataConfig(path=path))

    panel = prepare_five_factor_ivol_panel(_stock_daily(factors), dataset)

    assert len(panel) == 2
    assert panel["IVOL"].gt(0).all()
    assert panel["ivol_model"].eq("fama_french_five_factor").all()
    assert panel["factor_fingerprint"].eq(dataset.fingerprint).all()
    assert (panel["target_date"] > panel["date"]).all()


def test_five_factor_merge_fails_closed_on_missing_date(tmp_path) -> None:
    path = tmp_path / "ff5.csv"
    factors = _factor_file(path)
    dataset = load_five_factor_data(FactorDataConfig(path=path))
    daily = _stock_daily(factors)
    daily.loc[0, "date"] = pd.Timestamp("2023-12-29")

    with pytest.raises(FactorDataError, match="does not cover"):
        prepare_five_factor_ivol_panel(daily, dataset)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.drop(columns="RMW"), "missing"),
        (lambda frame: pd.concat([frame, frame.iloc[[0]]]), "duplicate dates"),
        (lambda frame: frame.assign(date="not-a-date"), "invalid dates"),
        (lambda frame: frame.assign(CMA="not-a-number"), "nonnumeric"),
    ],
)
def test_five_factor_loader_rejects_invalid_inputs(tmp_path, mutation, message) -> None:
    path = tmp_path / "invalid.csv"
    mutation(_factor_file(tmp_path / "source.csv")).to_csv(path, index=False)

    with pytest.raises(FactorDataError, match=message):
        load_five_factor_data(FactorDataConfig(path=path))


def test_five_factor_percent_conversion_is_explicit(tmp_path) -> None:
    path = tmp_path / "ff5-percent.csv"
    frame = _factor_file(path)
    frame[["MKT", "SMB", "HML", "RMW", "CMA", "RF"]] *= 100
    frame.to_csv(path, index=False)

    dataset = load_five_factor_data(FactorDataConfig(path=path, values_in_percent=True))

    assert dataset.frame.iloc[0]["RF"] == pytest.approx(0.0001)


def test_ivol_builder_validates_stock_schema_dates_and_minimum(tmp_path) -> None:
    path = tmp_path / "ff5.csv"
    factors = _factor_file(path)
    dataset = load_five_factor_data(FactorDataConfig(path=path))
    daily = _stock_daily(factors)

    with pytest.raises(ValueError, match="at least 8"):
        prepare_five_factor_ivol_panel(daily, dataset, minimum_daily_observations=7)
    with pytest.raises(FactorDataError, match="Daily stock data is missing"):
        prepare_five_factor_ivol_panel(daily.drop(columns="bm"), dataset)
    with pytest.raises(FactorDataError, match="invalid dates"):
        prepare_five_factor_ivol_panel(daily.assign(date="bad"), dataset)
    with pytest.raises(FactorDataError, match="No stock-month"):
        prepare_five_factor_ivol_panel(
            daily.iloc[:4], dataset, minimum_daily_observations=8
        )


def test_csmar_loader_reproduces_original_selection_explicitly(tmp_path) -> None:
    path = tmp_path / "csmar.csv"
    _csmar_file(path)

    dataset = load_csmar_five_factor_data(
        CsmarFactorDataConfig(path=path, reproduce_original_workflow=True)
    )

    assert len(dataset.frame) == 2
    assert dataset.frame["MKT"].tolist() == [0.01, 1.01]
    assert dataset.frame["SMB"].eq(0.001).all()
    assert dataset.frame["RF"].eq(0).all()
    assert dataset.metadata == {
        "provider": "CSMAR",
        "market_type": "P9709",
        "portfolios": 1,
        "weighting": "float_market_cap",
        "return_basis": "raw_return_original_replication",
        "residual_ddof": 0,
    }


def test_csmar_loader_requires_explicit_risk_free_treatment(tmp_path) -> None:
    path = tmp_path / "csmar.csv"
    _csmar_file(path)

    with pytest.raises(FactorDataError, match="has no RF column"):
        load_csmar_five_factor_data(CsmarFactorDataConfig(path=path))


def test_csmar_loader_merges_strict_risk_free_series(tmp_path) -> None:
    path = tmp_path / "csmar.csv"
    risk_free_path = tmp_path / "rf.csv"
    _csmar_file(path)
    pd.DataFrame({"date": ["2024-01-02", "2024-01-03"], "RF": [0.01, 0.02]}).to_csv(
        risk_free_path, index=False
    )

    dataset = load_csmar_five_factor_data(
        CsmarFactorDataConfig(
            path=path,
            weighting="total_market_cap",
            risk_free_path=risk_free_path,
            risk_free_values_in_percent=True,
        )
    )

    assert dataset.frame["SMB"].eq(0.002).all()
    assert dataset.frame["RF"].tolist() == pytest.approx([0.0001, 0.0002])
    assert dataset.metadata["return_basis"] == "excess_return"
    assert dataset.metadata["residual_ddof"] == 1


def test_csmar_loader_rejects_unknown_selection(tmp_path) -> None:
    path = tmp_path / "csmar.csv"
    _csmar_file(path)

    with pytest.raises(FactorDataError, match="No CSMAR rows match"):
        load_csmar_five_factor_data(
            CsmarFactorDataConfig(
                path=path,
                market_type="P9999",
                reproduce_original_workflow=True,
            )
        )


def test_csmar_loader_rejects_missing_factor_column(tmp_path) -> None:
    path = tmp_path / "csmar.csv"
    _csmar_file(path).drop(columns="CMA1").to_csv(path, index=False)

    with pytest.raises(
        FactorDataError, match="CSMAR five-factor data is missing: CMA1"
    ):
        load_csmar_five_factor_data(
            CsmarFactorDataConfig(path=path, reproduce_original_workflow=True)
        )
