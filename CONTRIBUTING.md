# Contributing

QuantResearchAgent requires Python 3.11. Install the exact development environment with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==25.3
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
```

Before opening a pull request, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy agents data_sources graph literature llm schemas tools examples production.py config.py logging_config.py main.py
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\release_audit.py
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pip_audit -r requirements.lock
```

Windows 中文路径下运行 `pip-audit` 时设置 `PYTHONUTF8=1`，用于规避其依赖读取 pip 输出时的编码差异。

Regenerate locks after intentionally changing an input requirement:

```powershell
.\.venv\Scripts\pip-compile.exe --strip-extras --output-file=requirements.lock requirements.txt
.\.venv\Scripts\pip-compile.exe --allow-unsafe --strip-extras --output-file=requirements-dev.lock requirements-dev.txt
```

Never commit `.env`, vendor market data, client information, or generated research reports. New statistical methods require deterministic fixtures and tests covering routing, inference, and failure behavior.
