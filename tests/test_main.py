import pytest

from main import main


def test_main_without_live_flag_only_compiles_graph(capsys) -> None:
    main([])

    output = capsys.readouterr().out
    assert "workflow initialized" in output
    assert "Use --live" in output


def test_main_live_requires_question_and_data() -> None:
    with pytest.raises(SystemExit):
        main(["--live"])
