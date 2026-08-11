"""Read-only Crossref metadata demo; no model API or API key is required."""

import os

from dotenv import load_dotenv

from literature.crossref import CrossrefClient
from literature.journals import CORE_FINANCE_JOURNALS


def main() -> None:
    load_dotenv()
    client = CrossrefClient(mailto=os.getenv("CROSSREF_MAILTO"))
    papers = client.search_journal(
        query="investor sentiment stock returns",
        journal=CORE_FINANCE_JOURNALS[0],
        rows=3,
    )

    print("Crossref verified metadata results:")
    for paper in papers:
        print(f"- {paper.title} ({paper.year})")
        print(f"  {paper.journal} | {paper.doi or paper.url}")


if __name__ == "__main__":
    main()
