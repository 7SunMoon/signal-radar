from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import requests

from collector.models import ArticleCandidate
from collector.text import canonicalize_url, clean_text, stable_id


class WebSearchProvider(ABC):
    name = "web-search"

    @abstractmethod
    def search(self, query: str, count: int = 8) -> list[dict[str, Any]]:
        """Return provider-neutral search results."""

    def discover(self, config: dict[str, Any]) -> list[ArticleCandidate]:
        candidates: list[ArticleCandidate] = []
        count = int(config.get("max_results_per_query", 8))
        for query_config in config.get("queries", []):
            for result in self.search(query_config["query"], count=count):
                url = result.get("url", "")
                title = clean_text(result.get("title"))
                if not url or not title:
                    continue
                candidates.append(
                    ArticleCandidate(
                        id=stable_id(url, title),
                        title=title,
                        url=url,
                        source=result.get("source") or self.name,
                        source_category=query_config.get("category", "other"),
                        source_priority="medium",
                        published_at=result.get("published_at", ""),
                        language=result.get("language", "en"),
                        snippet=clean_text(result.get("snippet"))[:1200],
                        canonical_url=canonicalize_url(url),
                    )
                )
        return candidates


class BraveSearchProvider(WebSearchProvider):
    name = "Brave Search"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, count: int = 8) -> list[dict[str, Any]]:
        if not self.api_key:
            return []
        response = requests.get(
            self.endpoint,
            params={"q": query, "count": max(1, min(count, 20)), "freshness": "pw"},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return [
            {
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "snippet": row.get("description", ""),
                "published_at": row.get("page_age", ""),
                "language": row.get("language", "en"),
                "source": row.get("profile", {}).get("long_name", "Brave Search"),
            }
            for row in results
        ]
