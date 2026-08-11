from typing import ClassVar

from literature.crossref import CrossrefClient
from literature.journals import CORE_FINANCE_JOURNALS


class _Response:
    status_code = 200
    headers: ClassVar[dict[str, str]] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "message": {
                "items": [
                    {
                        "DOI": "10.1111/test",
                        "title": ["A Verified Paper"],
                        "author": [{"given": "Ada", "family": "Researcher"}],
                        "published-online": {"date-parts": [[2024, 1, 2]]},
                        "URL": "https://doi.org/10.1111/test",
                        "abstract": "<jats:p>A &amp; B result.</jats:p>",
                    }
                ]
            }
        }


class _Session:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple] = []

    def get(self, url: str, *, params: dict, timeout: float) -> _Response:
        self.calls.append((url, params, timeout))
        return _Response()


def test_crossref_client_parses_metadata_and_caches_response() -> None:
    session = _Session()
    client = CrossrefClient(mailto="research@example.com", session=session)

    first = client.search_journal(
        query="investor sentiment",
        journal=CORE_FINANCE_JOURNALS[0],
        rows=1,
    )
    second = client.search_journal(
        query="investor sentiment",
        journal=CORE_FINANCE_JOURNALS[0],
        rows=1,
    )

    assert len(session.calls) == 1
    assert first == second
    assert first[0].title == "A Verified Paper"
    assert first[0].authors == ["Ada Researcher"]
    assert first[0].abstract == "A & B result."
    assert first[0].journal == "The Journal of Finance"
    assert session.calls[0][1]["mailto"] == "research@example.com"
    assert "QuantResearchAgent" in session.headers["User-Agent"]
