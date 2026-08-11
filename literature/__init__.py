"""Verified literature discovery and journal-quality controls."""

from literature.crossref import CrossrefClient, CrossrefLiteratureRetriever
from literature.journals import CORE_FINANCE_JOURNALS, JournalDefinition
from literature.protocol import LiteratureRetriever, StaticLiteratureRetriever

__all__ = [
    "CORE_FINANCE_JOURNALS",
    "CrossrefClient",
    "CrossrefLiteratureRetriever",
    "JournalDefinition",
    "LiteratureRetriever",
    "StaticLiteratureRetriever",
]
