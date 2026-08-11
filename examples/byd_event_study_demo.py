"""Offline event-study method demo using a real disclosure and return fixture."""

from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from graph.event_study import build_event_study_workflow
from schemas.enums import TaskType
from schemas.event_study import EventStudyDesign
from schemas.platform import EvidenceRecord, ResearchRequest

AS_OF_DATE = date(2026, 8, 8)
EVENT_DATE = date(2026, 5, 6)


def _evidence() -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id="BYD-ES-E1",
            source_type="official_disclosure",
            title="比亚迪股份有限公司2026年4月产销快报",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-05-06/1225277520.pdf",
            published_at=datetime(2026, 5, 5),
            retrieved_at=datetime(2026, 8, 8),
            summary=(
                "公司披露2026年1—4月新能源汽车累计销量1,021,586辆，同比下降"
                "26.02%；4月出口135,098辆。公告提示产销数据未经审核。"
            ),
        )
    ]


def _returns_fixture() -> pd.DataFrame:
    pre = pd.bdate_range(end=EVENT_DATE, periods=131)
    post = pd.bdate_range(start="2026-05-07", periods=10)
    dates = pre.append(post)
    index = np.arange(len(dates), dtype=float)
    benchmark = 0.0003 + 0.006 * np.sin(index / 7.0)
    residual = 0.004 * np.cos(index / 5.0)
    security = 0.0002 + 1.08 * benchmark + residual
    event_index = len(pre) - 1
    security[event_index - 1 : event_index + 2] += np.array([-0.012, -0.021, -0.009])
    return pd.DataFrame(
        {
            "date": [timestamp.date() for timestamp in dates],
            "security_return": security,
            "benchmark_return": benchmark,
        }
    )


def _design() -> EventStudyDesign:
    return EventStudyDesign(
        company_name="比亚迪股份有限公司",
        security_code="002594.SZ",
        event_title="2026年4月产销快报",
        event_date=EVENT_DATE,
        benchmark_name="示例市场基准",
        estimation_window=(-120, -21),
        event_windows=[(-1, 1), (-2, 2)],
        significance_level=0.05,
    )


def run_byd_event_study_demo(report_path: str | Path | None = None):
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "event_study"
            / "byd_event_study_demo.md"
        )
    )
    workflow = build_event_study_workflow(report_path=target)
    request = ResearchRequest(
        task_type=TaskType.EVENT_STUDY,
        question="比亚迪2026年4月产销快报发布前后是否存在异常收益？",
        objective="验证公告识别、市场模型、CAR 检验和委员会评审闭环。",
        companies=["比亚迪股份有限公司"],
        securities=["002594.SZ"],
        topics=["sales_announcement", "abnormal_return", "car"],
        as_of_date=AS_OF_DATE,
        public_data_only=True,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": {
                "event_study_design": _design(),
                "returns": _returns_fixture(),
                "evidence": _evidence(),
                "return_data_provenance": (
                    "确定性离线方法夹具；不代表002594.SZ真实历史收益，"
                    "仅用于复现市场模型和CAR计算"
                ),
                "contaminated": False,
            },
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_byd_event_study_demo()
    print("Event: 比亚迪2026年4月产销快报")
    print("Review:", result["event_study_review"].decision.value)
    print("Report:", result["report_markdown_path"])
