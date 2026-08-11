from scripts.release_audit import secret_findings


def test_secret_finding_detects_realistic_key() -> None:
    credential = "sk-" + "live-12345678901234567890"
    assert secret_findings(f"OPENAI_API_KEY={credential}") == [1]


def test_secret_finding_detects_gemini_key() -> None:
    credential = "AIza" + "live123456789012345678901234567890"
    assert secret_findings(f"key: {credential}") == [1]


def test_secret_finding_allows_documented_placeholder() -> None:
    assert secret_findings("OPENAI_API_KEY=your-api-key") == []


def test_secret_finding_honors_explicit_test_marker() -> None:
    value = "token=sk-fake-12345678901234567890 # release-audit: allow-secret"
    assert secret_findings(value) == []
