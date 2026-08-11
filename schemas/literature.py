"""Verified scholarly metadata retrieved before literature synthesis."""

from pydantic import BaseModel


class RetrievedPaper(BaseModel):
    title: str
    authors: list[str]
    year: int
    journal: str
    issn: str
    doi: str | None = None
    url: str
    abstract: str | None = None
    metadata_source: str = "crossref"
    journal_whitelisted: bool = True
