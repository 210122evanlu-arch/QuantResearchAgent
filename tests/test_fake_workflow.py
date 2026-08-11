from examples.ivol_research_demo import run_ivol_fake_demo
from schemas.enums import ReviewDecision


def test_real_seven_node_workflow_runs_with_fake_llm() -> None:
    result, fake_llm = run_ivol_fake_demo()
    call_path = [call.node_name for call in fake_llm.calls]

    assert call_path == [
        "research_manager",
        "research_analysis",
        "model_design",
        "review",
        "model_design",
        "review",
    ]
    model_calls = [call for call in fake_llm.calls if call.node_name == "model_design"]
    assert "review_feedback" not in model_calls[0].user_prompt
    assert "review_feedback" in model_calls[1].user_prompt
    assert "previous_model_design" in model_calls[1].user_prompt
    assert result["revision_count"] == 1
    assert result["review_result"].decision == ReviewDecision.APPROVED
    assert len(result["literature_candidates"]) == 1
    assert result["data_profile"].sample_size == 12
    assert result["data_profile"].missing_rate == 0.0
    assert result["data_profile"].look_ahead_bias_checked is True
    assert result["data_profile"].dataset_fingerprint.startswith("sha256:")
    assert result["research_analysis"].key_papers[0].doi_or_url == (
        "https://example.invalid/offline-fixture"
    )
    assert result["final_report"].review_decision == ReviewDecision.APPROVED
    assert (
        result["final_report"].statistical_findings
        == result["experiment_result"].statistical_results
    )
    assert (
        result["final_report"].model_metrics
        == result["experiment_result"].model_metrics
    )
    assert (
        result["final_report"].data_fingerprint
        == result["experiment_result"].data_fingerprint
    )
    assert result["current_stage"] == "report"
