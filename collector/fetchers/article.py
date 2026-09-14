from __future__ import annotations

import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from collector.models import ArticleCandidate
from collector.text import canonicalize_url, clean_text


class ArticleExtractor:
    """Best-effort article extraction. Full text is kept in memory only."""

    def __init__(self) -> None:
        self.timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
        self.user_agent = os.getenv("USER_AGENT", "SignalRadar/0.1 (+personal research tool)")

    def extract(self, candidate: ArticleCandidate) -> ArticleCandidate:
        try:
            response = requests.get(
                candidate.url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                return candidate

            soup = BeautifulSoup(response.text, "html.parser")
            canonical = soup.select_one('link[rel="canonical"]')
            if canonical and canonical.get("href"):
                candidate.canonical_url = canonicalize_url(urljoin(candidate.url, canonical["href"]))

            if not candidate.author:
                author = soup.select_one('meta[name="author"]')
                if author:
                    candidate.author = clean_text(author.get("content"))

            for tag in soup.select("script, style, nav, footer, header, aside, form, noscript"):
                tag.decompose()

            container = soup.select_one("article") or soup.select_one("main") or soup.body
            if not container:
                return candidate

            paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in container.select("p, h2, h3, li")]
            text = "\n".join(paragraph for paragraph in paragraphs if len(paragraph) >= 35)
            if len(text) >= 500:
                candidate.content = text[:20000]
                candidate.content_availability = "full"
            elif text:
                candidate.content = text[:5000]
            return candidate
        except (requests.RequestException, UnicodeError, ValueError):
            return candidate
