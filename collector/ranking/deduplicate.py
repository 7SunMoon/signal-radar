from __future__ import annotations

from difflib import SequenceMatcher

from collector.models import ArticleCandidate
from collector.text import canonicalize_url, normalize_title

PRIORITY = {"high": 3, "medium": 2, "low": 1}


def _quality(candidate: ArticleCandidate) -> tuple[int, int, int]:
    signals = candidate.social_signals
    engagement = int(signals.get("points", 0)) + int(signals.get("comments", 0))
    return (PRIORITY.get(candidate.source_priority, 1), len(candidate.snippet), engagement)


def _same_story(left: ArticleCandidate, right: ArticleCandidate, threshold: float) -> bool:
    if canonicalize_url(left.url) == canonicalize_url(right.url):
        return True
    a, b = normalize_title(left.title), normalize_title(right.title)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def deduplicate(candidates: list[ArticleCandidate], threshold: float = 0.84) -> list[ArticleCandidate]:
    retained: list[ArticleCandidate] = []
    for candidate in sorted(candidates, key=_quality, reverse=True):
        duplicate = next((item for item in retained if _same_story(candidate, item, threshold)), None)
        if duplicate:
            if candidate.source and candidate.source != duplicate.source:
                duplicate.duplicate_sources.append(candidate.source)
            continue
        retained.append(candidate)
    return retained
