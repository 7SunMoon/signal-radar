from __future__ import annotations

import os
from typing import Any
from xml.etree import ElementTree

import requests

from collector.models import ArticleCandidate
from collector.sources.base import SourceProvider
from collector.text import canonicalize_url, clean_text, parse_date, stable_id


class RSSProvider(SourceProvider):
    name = "rss"

    def __init__(self) -> None:
        self.timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
        self.user_agent = os.getenv("USER_AGENT", "SignalRadar/0.1 (+personal research tool)")

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    @classmethod
    def _child_text(cls, node: ElementTree.Element, *names: str) -> str:
        expected = {name.lower() for name in names}
        for child in list(node):
            if cls._local_name(child.tag) not in expected:
                continue
            if cls._local_name(child.tag) == "author":
                nested = cls._child_text(child, "name")
                return nested or clean_text("".join(child.itertext()))
            return clean_text("".join(child.itertext()))
        return ""

    @classmethod
    def _entry_link(cls, node: ElementTree.Element) -> str:
        for child in list(node):
            if cls._local_name(child.tag) != "link":
                continue
            href = child.attrib.get("href", "").strip()
            rel = child.attrib.get("rel", "alternate")
            if href and rel in {"alternate", ""}:
                return href
            if child.text and child.text.strip():
                return child.text.strip()
        return cls._child_text(node, "guid")

    def discover(self, config: dict[str, Any]) -> list[ArticleCandidate]:
        response = requests.get(
            config["url"],
            headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        entries = [node for node in root.iter() if self._local_name(node.tag) in {"item", "entry"}]

        candidates: list[ArticleCandidate] = []
        for entry in entries[: int(config.get("limit", 35))]:
            url = self._entry_link(entry)
            title = self._child_text(entry, "title")
            if not url or not title:
                continue
            published = parse_date(self._child_text(entry, "published", "updated", "pubDate", "date"))
            candidates.append(
                ArticleCandidate(
                    id=stable_id(url, title),
                    title=title,
                    url=url,
                    author=self._child_text(entry, "author", "creator"),
                    source=config["name"],
                    source_url=config["url"],
                    source_category=config.get("category", "other"),
                    source_priority=config.get("priority", "medium"),
                    published_at=published,
                    language=config.get("language", "en"),
                    snippet=self._child_text(entry, "summary", "description", "content", "encoded")[:1200],
                    canonical_url=canonicalize_url(url),
                )
            )
        return candidates
