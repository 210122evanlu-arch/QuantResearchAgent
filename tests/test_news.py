from datetime import date

import pytest

from data_sources.news import NewsFeed, RSSNewsClient


class Response:
    content = b"""
    <rss><channel>
      <item><title>Example Corp wins major order</title>
      <link>https://news.test/1</link>
      <pubDate>Sat, 08 Aug 2026 08:00:00 GMT</pubDate>
      <description><![CDATA[<b>Example Corp</b> disclosed a new order.]]></description></item>
      <item><title>Unrelated company update</title>
      <link>https://news.test/2</link>
      <pubDate>Sat, 08 Aug 2026 08:00:00 GMT</pubDate></item>
    </channel></rss>
    """

    def raise_for_status(self) -> None:
        return None


class Session:
    def get(self, _url: str, **_kwargs) -> Response:
        return Response()


def test_rss_news_client_filters_company_and_keeps_metadata_only() -> None:
    client = RSSNewsClient(
        [NewsFeed("Licensed Business Feed", "https://feed.test/rss")],
        session=Session(),
    )
    records = client.search(
        "Example Corp", start_date=date(2026, 8, 1), end_date=date(2026, 8, 10)
    )

    assert len(records) == 1
    assert records[0].source_type == "news"
    assert records[0].url == "https://news.test/1"
    assert "<b>" not in records[0].summary


def test_news_feed_and_date_range_are_validated() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        NewsFeed("Source", "file:///feed.xml")
    client = RSSNewsClient(
        [NewsFeed("Source", "https://feed.test/rss")], session=Session()
    )
    with pytest.raises(ValueError, match="must not exceed"):
        client.search("Company", start_date=date(2026, 8, 2), end_date=date(2026, 8, 1))
