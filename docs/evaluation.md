# Release evaluation

The release benchmark protects the business contract above the unit-test layer. It
is deterministic, credential-free, and runs in CI.

## Coverage

The routing evaluation covers all six platform service lines:

- listed-company research, including conditional DCF routing;
- industry research;
- quantitative research;
- market strategy;
- event study;
- corporate advisory.

The showcase evaluation checks that the five approved portfolio reports exist,
retain their required decision sections, and remain substantive enough to function
as interview-ready deliverables.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m evals.release_benchmark `
  --baseline evals/baseline.json
```

The command fails when current behaviour differs from the approved baseline. A
baseline update is a reviewed product decision, not an automatic response to a
failed check:

```powershell
.\.venv\Scripts\python.exe -m evals.release_benchmark --write
```

This benchmark verifies routing and release artifacts. It does not claim that a
language model's prose is factually correct. Live-model quality should additionally
be evaluated with licensed evidence, frozen prompts, human scoring rubrics, and
Provider/version metadata before production use.
