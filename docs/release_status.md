# Release and interface status

- Public release: v0.2.0
- Main branch baseline: Unreleased after v0.2.0
- API contract: 0.4.0
- Python runtime: 3.11

The public GitHub release is the last tagged portfolio snapshot. The `main` branch
currently contains subsequent work recorded under `Unreleased`
in `CHANGELOG.md` and remains subject to the same CI quality gates.

The API contract version is the FastAPI/OpenAPI interface version. It can advance
independently from the repository's public release tag and must not be presented as
the package version.
