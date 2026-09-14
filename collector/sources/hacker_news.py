from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from collector.models import ArticleCandidate
from collector.sources.base import SourceProvider
from collector.text import canonicalize_url, clean_text, iso_from_timestamp, stable_id


class HackerNewsProvider(SourceProvider):
    name = "hacker-news"
    api_root = "https://hacker-news.firebaseio.com/v0"

    def __init__(self) -> None:
        self.timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

    def _fetch_item(self, item_id: int) -> dict[str, Any]:
        response = requests.get(f"{self.api_root}/item/{item_id}.json", timeout=self.timeout)
        response.raise_for_status()
        return response.json() or {}

    def discover(self, config: dict[str, Any]) -> list[ArticleCandidate]:
        limit = int(config.get("limit", 45))
        response = requests.get(f"{self.api_root}/topstories.json", timeout=self.timeout)
        response.raise_for_status()
        ids = response.json()[:limit]
        items: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._fetch_item, item_id) for item_id in ids]
            for future in as_completed(futures):
                try:
                    item = future.result()
                except requests.RequestException:
                    continue
                if item.get("type") == "story" and item.get("title"):
                    items.append(item)

        candidates: list[ArticleCandidate] = []
        for item in sorted(items, key=lambda row: row.get("score", 0), reverse=True):
            url = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
            title = clean_text(item.get("title"))
            candidates.append(
                ArticleCandidate(
                    id=stable_id(url, title),
                    title=title,
                    url=url,
                    author=item.get("by", ""),
                    source="Hacker News",
                    source_url="https://news.ycombinator.com/",
                    source_category=config.get("category", "other"),
                    source_priority=config.get("priority", "medium"),
                    published_at=iso_from_timestamp(item.get("time")),
                    language=config.get("language", "en"),
                    snippet=clean_text(item.get("text"))[:1200],
                    social_signals={
                        "points": int(item.get("score", 0)),
                        "comments": int(item.get("descendants", 0)),
                        "hnUrl": f"https://news.ycombinator.com/item?id={item['id']}",
                    },
                    canonical_url=canonicalize_url(url),
                )
            )
        return candidates
