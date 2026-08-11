"""Use DeepSeek once to write a full BYD consulting narrative from verified inputs."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import baostock as bs
import pandas as pd

from config import DeepSeekSettings
from examples.byd_risk_advisory_demo import (
    AS_OF_DATE,
    _analysis_node,
    run_byd_risk_advisory_demo,
)
from llm.deepseek_provider import DeepSeekStructuredLLM
from schemas.consulting_report import ConsultingReportNarrative

_SYSTEM_PROMPT = """你是一家顶级管理咨询公司负责上市公司风险与战略项目的项目经理。
请基于提供的结构化证据、风险诊断、研究辩论和行情统计，撰写中文正式咨询报告内容。

写作要求：
1. 使用咨询式表达：结论先行、事实与判断分离、说明管理含义和可执行行动。
2. 内容应足以支持一份约15至20页的Word报告，但避免空话和重复。
3. 只能使用输入中出现的事实和数字；不得补造市场份额、估值、利润率、评级或新闻。
4. 每个事实判断必须引用输入中存在的evidence_id。行情统计统一引用MARKET-E1。
5. 明确区分担保授权上限与实际担保余额，禁止将授权额度写成实际债务。
6. 明确区分美国国防部名单与制裁，禁止写成公司已经受到全面制裁。
7. 情景分析是条件推演，不是预测；不得虚构概率。
8. 建议面向公司管理层/风险委员会，不能给出证券买卖建议。
9. 语言专业、克制、具体，避免“赋能、抓手、闭环”等空泛套话。
"""


def _query_history(code: str) -> pd.DataFrame:
    result = bs.query_history_k_data_plus(
        code,
        "date,code,close,pctChg,turn",
        start_date="2025-01-01",
        end_date=AS_OF_DATE.isoformat(),
        frequency="d",
        adjustflag="2",
    )
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock query failed for {code}: {result.error_msg}")
    rows = []
    while result.error_code == "0" and result.next():
        rows.append(result.get_row_data())
    frame = pd.DataFrame(rows, columns=result.fields)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"])
    frame["pctChg"] = pd.to_numeric(frame["pctChg"]) / 100
    return frame


def _market_context() -> dict:
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_msg}")
    try:
        stock = _query_history("sz.002594")
        benchmark = _query_history("sh.000300")
    finally:
        bs.logout()
    if stock.empty or benchmark.empty:
        raise RuntimeError("BaoStock returned no market history")

    def stats(frame: pd.DataFrame) -> dict:
        close = frame.set_index("date")["close"].sort_index()
        daily = frame.set_index("date")["pctChg"].sort_index()
        ytd = close.loc[close.index >= pd.Timestamp("2026-01-01")]
        one_year = close.loc[close.index >= close.index.max() - pd.Timedelta(days=365)]
        drawdown = close / close.cummax() - 1
        return {
            "start_date": close.index.min().date().isoformat(),
            "end_date": close.index.max().date().isoformat(),
            "start_close": round(float(close.iloc[0]), 4),
            "end_close": round(float(close.iloc[-1]), 4),
            "period_return_pct": round(
                float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2
            ),
            "ytd_return_pct": round(float((ytd.iloc[-1] / ytd.iloc[0] - 1) * 100), 2),
            "annualized_volatility_pct": round(
                float(daily.std() * (252**0.5) * 100), 2
            ),
            "maximum_drawdown_pct": round(float(drawdown.min() * 100), 2),
            "one_year_high": round(float(one_year.max()), 4),
            "one_year_low": round(float(one_year.min()), 4),
        }

    merged = stock[["date", "close"]].merge(
        benchmark[["date", "close"]], on="date", suffixes=("_byd", "_csi300")
    )
    merged["byd_rebased"] = merged["close_byd"] / merged["close_byd"].iloc[0] * 100
    merged["csi300_rebased"] = (
        merged["close_csi300"] / merged["close_csi300"].iloc[0] * 100
    )
    series = [
        {
            "date": pd.Timestamp(row["date"]).date().isoformat(),
            "byd_rebased": round(float(row["byd_rebased"]), 4),
            "csi300_rebased": round(float(row["csi300_rebased"]), 4),
        }
        for row in merged.to_dict("records")
    ]
    return {
        "source": "BaoStock forward-adjusted daily prices (adjustflag=2)",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "byd": stats(stock),
        "csi300": stats(benchmark),
        "rebased_series": series,
    }


def _validate_evidence_ids(report: ConsultingReportNarrative, known: set[str]) -> None:
    referenced = {
        evidence_id
        for item in report.headline_findings
        for evidence_id in item.evidence_ids
    }
    referenced.update(
        evidence_id
        for item in report.risk_chapters
        for evidence_id in item.evidence_ids
    )
    referenced.update(
        evidence_id
        for item in report.priority_actions
        for evidence_id in item.evidence_ids
    )
    unknown = referenced - known
    if unknown:
        raise ValueError(
            "Live report invented evidence IDs: " + ", ".join(sorted(unknown))
        )


def run_live_consulting_report(output_path: str | Path):
    debate_state, _ = run_byd_risk_advisory_demo()
    analysis_state = _analysis_node({})
    market = _market_context()
    prompt_payload = {
        "company_risk_profile": analysis_state["risk_profile"].model_dump(mode="json"),
        "analysis_bundle": analysis_state["analysis_bundle"].model_dump(mode="json"),
        "debate_gate": debate_state["debate_gate_result"].model_dump(mode="json"),
        "debate_result": debate_state["debate_result"].model_dump(mode="json"),
        "market_evidence": {
            "evidence_id": "MARKET-E1",
            "summary_statistics": {"byd": market["byd"], "csi300": market["csi300"]},
            "scope_note": "行情用于风险语境，不用于估值或投资评级。",
        },
    }
    settings = replace(
        DeepSeekSettings.from_env(".env"),
        timeout_seconds=420,
        max_retries=0,
        max_output_tokens=16000,
        thinking=False,
    )
    llm = DeepSeekStructuredLLM(settings)
    report = llm.generate(
        schema=ConsultingReportNarrative,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=(
            "请生成完整咨询报告结构化正文。以下是唯一允许使用的事实输入：\n\n"
            + json.dumps(prompt_payload, ensure_ascii=False, indent=2)
        ),
        node_name="consulting_report_writer",
    )
    known = {
        item.evidence_id for item in analysis_state["analysis_bundle"].evidence
    } | {"MARKET-E1"}
    _validate_evidence_ids(report, known)
    artifact = {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": "deepseek",
        "model": settings.model,
        "as_of_date": AS_OF_DATE.isoformat(),
        "report": report.model_dump(mode="json"),
        "source_context": {
            "risk_profile": analysis_state["risk_profile"].model_dump(mode="json"),
            "analysis_bundle": analysis_state["analysis_bundle"].model_dump(
                mode="json"
            ),
            "debate_result": debate_state["debate_result"].model_dump(mode="json"),
            "market": market,
        },
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target.resolve(), report


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    output, narrative = run_live_consulting_report(
        project_root / "reports" / "advisory" / "byd_live_consulting_report.json"
    )
    print("DeepSeek consulting narrative generated")
    print("Title:", narrative.title)
    print("Artifact:", output)
