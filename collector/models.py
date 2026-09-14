from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ArticleCandidate:
    id: str
    title: str
    url: str
    author: str = ""
    source: str = ""
    source_url: str = ""
    source_category: str = "other"
    source_priority: str = "medium"
    published_at: str = ""
    discovered_at: str = field(default_factory=utc_now_iso)
    language: str = "en"
    snippet: str = ""
    social_signals: dict[str, Any] = field(default_factory=dict)
    canonical_url: str = ""
    content: str = ""
    content_availability: str = "partial"
    duplicate_sources: list[str] = field(default_factory=list)

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_content:
            data.pop("content", None)
        return data
