import pytest

from app.domain.models import NewsEvent
from app.providers.rss_news import RssNewsProvider


RSS_PAYLOAD = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Trial Market Feed</title>
    <item>
      <title>Reliance Industries wins a major contract</title>
      <link>https://example.com/reliance-1</link>
      <guid>reliance-1</guid>
      <pubDate>Mon, 07 Sep 2026 09:30:00 +0530</pubDate>
    </item>
    <item>
      <title>Tata Consultancy Services announces an update</title>
      <link>https://example.com/tcs-1</link>
      <guid>tcs-1</guid>
      <pubDate>Mon, 07 Sep 2026 09:20:00 +0530</pubDate>
    </item>
  </channel>
</rss>'''


class FakeRssProvider(RssNewsProvider):
    def _download(self, feed_url: str) -> bytes:
        return RSS_PAYLOAD


@pytest.mark.asyncio
async def test_rss_provider_parses_and_resolves_symbols() -> None:
    provider = FakeRssProvider(
        ["https://example.com/feed.xml"],
        symbol_keywords={
            "RELIANCE": ["Reliance Industries"],
            "TCS": ["Tata Consultancy Services"],
        },
    )

    events = await provider.fetch()

    assert len(events) == 2
    assert events[0].source == "Trial Market Feed"
    assert events[0].symbols == ["RELIANCE"]
    assert events[1].symbols == ["TCS"]
    assert events[0].published_at == "2026-09-07T04:00:00+00:00"


@pytest.mark.asyncio
async def test_rss_provider_deduplicates_same_feed_item() -> None:
    provider = FakeRssProvider(
        ["https://example.com/a.xml", "https://example.com/b.xml"],
    )

    events = await provider.fetch()

    assert len(events) == 2
    assert len({event.id for event in events}) == 2


def test_rss_event_ids_are_stable() -> None:
    first = RssNewsProvider._event_id("Reuters", "guid-1", "Market update")
    second = RssNewsProvider._event_id("Reuters", "guid-1", "Market update")
    assert first == second
    assert first.startswith("rss-")
