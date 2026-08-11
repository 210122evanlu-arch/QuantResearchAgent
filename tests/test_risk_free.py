from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import requests

import data_sources.risk_free as risk_free_module
from data_sources.risk_free import (
    ChinaBondRiskFreeConfig,
    RiskFreeDataError,
    _date_chunks,
    _fetch_chunk,
    _normalize_download,
    _parse_history_html,
    align_risk_free_to_dates,
    download_chinabond_risk_free,
    load_risk_free_proxy,
)


def _config(tmp_path: Path, **overrides) -> ChinaBondRiskFreeConfig:
    values = {
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 12, 31),
        "output_path": tmp_path / "rf.parquet",
        "pause_seconds": 0,
        **overrides,
    }
    return ChinaBondRiskFreeConfig(**values)


def _html() -> str:
    frame = pd.DataFrame(
        {
            "曲线名称": ["中债国债收益率曲线", "其他曲线"],
            "日期": ["2020-01-02", "2020-01-02"],
            "3月": [2.52, 4.0],
        }
    )
    return (
        "<html><body><table><tr><td>x</td></tr></table>"
        + frame.to_html(index=False)
        + "</body></html>"
    )


class FakeResponse:
    text = _html()

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def get(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"end_date": date(2020, 1, 1)}, "earlier"),
        ({"maturity": "10年"}, "maturity"),
        ({"annualization_days": 0}, "positive"),
        ({"timeout_seconds": 0}, "positive"),
        ({"pause_seconds": -1}, "nonnegative"),
    ],
)
def test_config_validation(tmp_path: Path, overrides: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _config(tmp_path, **overrides)


def test_date_chunks_never_exceed_one_year() -> None:
    chunks = _date_chunks(date(2020, 1, 1), date(2021, 6, 1))
    assert chunks[0] == (date(2020, 1, 1), date(2020, 12, 30))
    assert chunks[-1][1] == date(2021, 6, 1)


def test_parse_and_normalize_history(tmp_path: Path) -> None:
    parsed = _parse_history_html(
        _html(), curve_name="中债国债收益率曲线", maturity="3月"
    )
    normalized = _normalize_download([parsed], _config(tmp_path))
    assert normalized["annual_yield_percent"].item() == 2.52
    assert normalized["RF"].item() == pytest.approx((1.0252 ** (1 / 252)) - 1)


def test_parse_rejects_bad_tables_and_values() -> None:
    with pytest.raises(RiskFreeDataError, match="required"):
        _parse_history_html(
            pd.DataFrame({"x": [1]}).to_html(), curve_name="x", maturity="3月"
        )
    bad = pd.DataFrame(
        {"曲线名称": ["中债国债收益率曲线"], "日期": ["2020-01-01"], "3月": [99]}
    )
    with pytest.raises(RiskFreeDataError, match="safety"):
        _parse_history_html(
            bad.to_html(), curve_name="中债国债收益率曲线", maturity="3月"
        )


def test_download_writes_cache_and_manifest(tmp_path: Path) -> None:
    config = _config(tmp_path)
    result = download_chinabond_risk_free(config, session=FakeSession())
    assert result.rows == 1
    assert not result.cache_hit
    assert result.manifest_path.exists()
    cached = download_chinabond_risk_free(config, session=FakeSession())
    assert cached.cache_hit


def test_fetch_retries_then_raises(tmp_path: Path, monkeypatch) -> None:
    class FailedSession:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("offline")

    monkeypatch.setattr(risk_free_module.time, "sleep", lambda _seconds: None)
    with pytest.raises(RiskFreeDataError, match="download failed"):
        _fetch_chunk(
            FailedSession(), date(2020, 1, 1), date(2020, 2, 1), _config(tmp_path)
        )


def test_load_and_align_without_lookahead(tmp_path: Path) -> None:
    path = tmp_path / "rf.parquet"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-03", "2020-01-06"]),
            "RF": [0.001, 0.002],
        }
    ).to_parquet(path, index=False)
    loaded = load_risk_free_proxy(path)
    aligned = align_risk_free_to_dates(
        pd.Series(pd.to_datetime(["2020-01-04", "2020-01-06"])), loaded
    )
    assert aligned["RF"].tolist() == [0.001, 0.002]
    assert aligned["risk_free_staleness_days"].tolist() == [1, 0]


def test_load_and_align_reject_invalid_inputs(tmp_path: Path) -> None:
    with pytest.raises(RiskFreeDataError, match="does not exist"):
        load_risk_free_proxy(tmp_path / "missing.parquet")
    path = tmp_path / "bad.parquet"
    pd.DataFrame({"date": ["bad"], "RF": [0.0]}).to_parquet(path, index=False)
    with pytest.raises(RiskFreeDataError, match="invalid"):
        load_risk_free_proxy(path)
    source = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "RF": [0.0]})
    with pytest.raises(RiskFreeDataError, match="fails to cover"):
        align_risk_free_to_dates(pd.Series(pd.to_datetime(["2020-01-10"])), source)
    with pytest.raises(ValueError, match="nonnegative"):
        align_risk_free_to_dates(
            pd.Series(pd.to_datetime(["2020-01-01"])),
            source,
            max_staleness_days=-1,
        )
