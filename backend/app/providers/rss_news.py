from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.domain.models import NewsEvent
from app.providers.interfaces import NewsProvider
from app.services.entity_resolution import CompanyEntityResolver


class RssNewsProvider(NewsProvider):
    """Free RSS/Atom metadata provider using Python's standard library only."""

    def __init__(
        self,
        feed_urls: list[str],
        *,
        resolver: CompanyEntityResolver | None = None,
        symbol_keywords: dict[str, list[str]] | None = None,
        timeout_seconds: float = 10.0,
        user_agent: str = "ProfitPilotAI-News/0.1",
        max_items_per_feed: int = 50,
    ) -> None:
        self.feed_urls = [url.strip() for url in feed_urls if url.strip()]
        self.resolver = resolver
        self.symbol_keywords = {
            symbol.upper(): [keyword.casefold() for keyword in keywords]
            for symbol, keywords in (symbol_keywords or {}).items()
        }
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.max_items_per_feed = max(1, max_items_per_feed)

    async def fetch(self) -> list[NewsEvent]:
        batches = await asyncio.gather(
            *(self._fetch_feed(url) for url in self.feed_urls), return_exceptions=True
        )
        events: list[NewsEvent] = []
        seen: set[str] = set()
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for event in batch:
                if event.id not in seen:
                    seen.add(event.id)
                    events.append(event)
        return sorted(events, key=lambda event: event.published_at, reverse=True)

    async def _fetch_feed(self, feed_url: str) -> list[NewsEvent]:
        payload = await asyncio.to_thread(self._download, feed_url)
        return self._parse_feed(payload, feed_url)

    def _download(self, feed_url: str) -> bytes:
        request = Request(feed_url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()

    def _parse_feed(self, payload: bytes, feed_url: str) -> list[NewsEvent]:
        root = ElementTree.fromstring(payload)
        source = self._source_name(feed_url, root)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        events: list[NewsEvent] = []
        for item in items[: self.max_items_per_feed]:
            title = self._text(item, "title") or ""
            link = self._link(item)
            published = self._text(item, "pubDate") or self._text(item, "published")
            published = published or self._text(item, "updated")
            guid = self._text(item, "guid") or self._text(item, "id") or link or title
            if not title.strip():
                continue
            clean_title = self._clean_title(title)
            events.append(
                NewsEvent(
                    id=self._event_id(source, guid, clean_title),
                    title=clean_title,
                    source=source,
                    published_at=self._parse_datetime(published),
                    symbols=self._resolve_symbols(clean_title),
                    materiality=0.0,
                )
            )
        return events

    @staticmethod
    def _text(item: ElementTree.Element, name: str) -> str | None:
        node = item.find(name)
        if node is None:
            node = item.find(f"{{http://www.w3.org/2005/Atom}}{name}")
        if node is None or node.text is None:
            return None
        return node.text.strip()

    @staticmethod
    def _link(item: ElementTree.Element) -> str | None:
        node = item.find("link")
        if node is not None and node.text:
            return node.text.strip()
        atom = item.find("{http://www.w3.org/2005/Atom}link")
        if atom is not None:
            href = atom.attrib.get("href")
            if href:
                return href.strip()
        return None

    def _resolve_symbols(self, title: str) -> list[str]:
        if self.resolver is not None:
            return self.resolver.resolve_symbols(title)
        normalized = title.casefold()
        matches: list[str] = []
        for symbol, keywords in self.symbol_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                matches.append(symbol)
        return matches

    @staticmethod
    def _clean_title(title: str) -> str:
        return " ".join(title.split())

    @staticmethod
    def _source_name(feed_url: str, root: ElementTree.Element) -> str:
        channel_title = root.find("./channel/title")
        if channel_title is not None and channel_title.text:
            return channel_title.text.strip()
        atom_title = root.find("./{http://www.w3.org/2005/Atom}title")
        if atom_title is not None and atom_title.text:
            return atom_title.text.strip()
        return urlparse(feed_url).netloc

    @staticmethod
    def _event_id(source: str, guid: str, title: str) -> str:
        fingerprint = f"{source.casefold()}|{guid.strip()}|{title.casefold().strip()}"
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        return f"rss-{digest}"

    @staticmethod
    def _parse_datetime(value: str | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                return datetime.now(timezone.utc).isoformat()
