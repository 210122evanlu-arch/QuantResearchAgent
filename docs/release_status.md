# Release and interface status

- Public release: v0.1.0
- Main branch: Unreleased
- API contract: 0.3.0
- Python runtime: 3.11

The public GitHub release is the last tagged portfolio snapshot. The `main` branch
contains the additions listed under `Unreleased` in `CHANGELOG.md`; it remains
subject to the same CI quality gates but has not yet been assigned a new release
tag.

The API contract version is the FastAPI/OpenAPI interface version. It can advance
independently from the repository's public release tag and must not be presented as
the package version.
