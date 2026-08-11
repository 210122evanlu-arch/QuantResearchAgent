"""Crossref-backed discovery limited to a curated journal registry."""

import html
import re
import time
from collections.abc import Iterable

import requests

from literature.journals import CORE_FINANCE_JOURNALS, JournalDefinition
from schemas.literature import RetrievedPaper
from schemas.research_plan import ResearchPlan

_TAG_PATTERN = re.compile(r"<[^>]+>")


class LiteratureRetrievalError(RuntimeError):
    """Raised when scholarly metadata cannot be retrieved safely."""


def _published_year(item: dict) -> int | None:
    for field in ("published-print", "published-online", "issued", "created"):
        parts = item.get(field, {}).get("date-parts", [])
        if parts and parts[0]:
            return int(parts[0][0])
    return None


def _authors(item: dict) -> list[str]:
    names: list[str] = []
    for author in item.get("author", []):
        name = " ".join(
            part for part in (author.get("given", ""), author.get("family", "")) if part
        ).strip()
        if name:
            names.append(name)
    return names


def _clean_abstract(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = html.unescape(_TAG_PATTERN.sub(" ", value))
    return " ".join(cleaned.split()) or None


class CrossrefClient:
    """Small, polite Crossref REST client with retry and in-memory caching."""

    base_url = "https://api.crossref.org"

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        session: requests.Session | None = None,
    ) -> None:
        self.mailto = (mailto or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = session or requests.Session()
        contact = self.mailto or "contact-not-configured"
        self.session.headers.update(
            {"User-Agent": f"QuantResearchAgent/0.1 (mailto:{contact})"}
        )
        self._cache: dict[tuple, list[RetrievedPaper]] = {}

    def search_journal(
        self,
        *,
        query: str,
        journal: JournalDefinition,
        rows: int = 3,
        from_year: int | None = None,
    ) -> list[RetrievedPaper]:
        if not 1 <= rows <= 20:
            raise ValueError("rows must be between 1 and 20")
        cache_key = (query, journal.issn, rows, from_year)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        params: dict[str, str | int] = {
            "query.bibliographic": query,
            "rows": rows,
            "select": "DOI,title,author,published-print,published-online,issued,created,URL,abstract,ISSN,container-title,type",
        }
        if self.mailto:
            params["mailto"] = self.mailto
        if from_year is not None:
            params["filter"] = f"from-pub-date:{from_year}-01-01,type:journal-article"
        else:
            params["filter"] = "type:journal-article"

        url = f"{self.base_url}/journals/{journal.issn}/works"
        payload = self._get_json(url, params)
        papers = [
            paper
            for item in payload.get("message", {}).get("items", [])
            if (paper := self._parse_item(item, journal)) is not None
        ]
        self._cache[cache_key] = papers
        return list(papers)

    def _get_json(self, url: str, params: dict) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise LiteratureRetrievalError("Crossref request failed") from exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    raise LiteratureRetrievalError(
                        f"Crossref returned HTTP {response.status_code}"
                    )
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else float(2**attempt)
                except ValueError:
                    delay = float(2**attempt)
                time.sleep(min(delay, 30.0))
                continue

            try:
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                raise LiteratureRetrievalError("Invalid Crossref response") from exc

        raise LiteratureRetrievalError("Crossref retry loop exhausted")

    @staticmethod
    def _parse_item(item: dict, journal: JournalDefinition) -> RetrievedPaper | None:
        titles = item.get("title", [])
        year = _published_year(item)
        doi = item.get("DOI")
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
        if not titles or year is None or not url:
            return None

        return RetrievedPaper(
            title=titles[0],
            authors=_authors(item),
            year=year,
            journal=journal.name,
            issn=journal.issn,
            doi=doi,
            url=url,
            abstract=_clean_abstract(item.get("abstract")),
            metadata_source="crossref",
            journal_whitelisted=True,
        )


class CrossrefLiteratureRetriever:
    """Search selected curated journals and deduplicate DOI/title matches."""

    def __init__(
        self,
        client: CrossrefClient,
        *,
        journals: Iterable[JournalDefinition] = CORE_FINANCE_JOURNALS[:4],
        rows_per_journal: int = 3,
        from_year: int | None = None,
    ) -> None:
        self.client = client
        self.journals = tuple(journals)
        self.rows_per_journal = rows_per_journal
        self.from_year = from_year

    def search(self, plan: ResearchPlan) -> list[RetrievedPaper]:
        hypothesis_text = " ".join(
            " ".join(
                (
                    hypothesis.statement,
                    hypothesis.dependent_variable,
                    hypothesis.independent_variable,
                    hypothesis.rationale,
                )
            )
            for hypothesis in plan.hypotheses
        )
        raw_query = " ".join(
            (
                plan.research_question,
                plan.research_objective,
                plan.methodology,
                " ".join(plan.required_data),
                hypothesis_text,
            )
        )
        ascii_terms = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", raw_query))
        if re.search(r"\bivol\b", raw_query, flags=re.IGNORECASE):
            query = "idiosyncratic volatility expected stock returns"
        else:
            query = ascii_terms or plan.research_type.value.replace("_", " ")
        papers: list[RetrievedPaper] = []
        for journal in self.journals:
            papers.extend(
                self.client.search_journal(
                    query=query,
                    journal=journal,
                    rows=self.rows_per_journal,
                    from_year=self.from_year,
                )
            )

        deduplicated: dict[str, RetrievedPaper] = {}
        for paper in papers:
            key = (paper.doi or paper.title).strip().lower()
            deduplicated.setdefault(key, paper)
        return list(deduplicated.values())
