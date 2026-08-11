"""Configurable RSS/Atom ingestion that stores metadata rather than article text."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from xml.etree import ElementTree

import requests

from schemas.platform import EvidenceRecord


class NewsResponse(Protocol):
    content: bytes

    def raise_for_status(self) -> None: ...


class NewsSession(Protocol):
    def get(self, url: str, **kwargs) -> NewsResponse: ...


@dataclass(frozen=True)
class NewsFeed:
    source_name: str
    url: str

    def __post_init__(self) -> None:
        if not self.source_name.strip() or not self.url.startswith(
            ("http://", "https://")
        ):
            raise ValueError("news feed requires a source name and HTTP(S) URL")


def _text(element: ElementTree.Element, *names: str) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()[:400]


class RSSNewsClient:
    def __init__(
        self,
        feeds: list[NewsFeed],
        *,
        session: NewsSession | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not feeds:
            raise ValueError("at least one news feed is required")
        self.feeds = feeds
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def search(
        self, company_name: str, *, start_date: date, end_date: date
    ) -> list[EvidenceRecord]:
        if start_date > end_date:
            raise ValueError("news start_date must not exceed end_date")
        records: list[EvidenceRecord] = []
        retrieved = datetime.now(UTC)
        for feed in self.feeds:
            response = self.session.get(feed.url, timeout=self.timeout_seconds)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            entries = [*root.findall(".//item"), *root.findall(".//{*}entry")]
            for entry in entries:
                title = _text(entry, "title", "{*}title")
                summary = _text(
                    entry, "description", "summary", "{*}summary", "{*}content"
                )
                haystack = f"{title} {_plain_text(summary)}".lower()
                if company_name.lower() not in haystack:
                    continue
                published = _published(
                    _text(
                        entry,
                        "pubDate",
                        "published",
                        "updated",
                        "{*}published",
                        "{*}updated",
                    )
                )
                if published is None or not start_date <= published.date() <= end_date:
                    continue
                link = _text(entry, "link", "{*}link")
                if not link:
                    link_node = entry.find("{*}link")
                    link = link_node.get("href", "") if link_node is not None else ""
                digest = (
                    hashlib.sha256(
                        f"{feed.source_name}|{link}|{title}|{published.date()}".encode()
                    )
                    .hexdigest()[:10]
                    .upper()
                )
                records.append(
                    EvidenceRecord(
                        evidence_id=f"NEWS-{digest}",
                        source_type="news",
                        title=title,
                        source_name=feed.source_name,
                        url=link or None,
                        published_at=published,
                        retrieved_at=retrieved,
                        summary=_plain_text(summary) or "News metadata only.",
                    )
                )
        return records
