from __future__ import annotations

from datetime import datetime, timezone

from collector.models import ArticleCandidate

PRIORITY_SCORE = {"high": 18, "medium": 11, "low": 5}


def _recency_score(published_at: str, max_age_days: int) -> float:
    if not published_at:
        return 4.0
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 4.0
    age_hours = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
    return max(0.0, 24.0 * (1 - age_hours / max(1, max_age_days * 24)))


def heuristic_score(candidate: ArticleCandidate, max_age_days: int = 10) -> float:
    category_fit = 24 if candidate.source_category != "other" else 8
    source = PRIORITY_SCORE.get(candidate.source_priority, 5)
    recency = _recency_score(candidate.published_at, max_age_days)
    metadata = min(12, len(candidate.snippet) / 100) + (4 if candidate.author else 0)
    engagement = min(
        18,
        float(candidate.social_signals.get("points", 0)) / 20
        + float(candidate.social_signals.get("comments", 0)) / 30,
    )
    return round(min(100.0, category_fit + source + recency + metadata + engagement), 2)


def pre_rank(
    candidates: list[ArticleCandidate],
    pool_size: int = 40,
    max_age_days: int = 10,
    chinese_ratio: float | None = None,
) -> list[tuple[ArticleCandidate, float]]:
    scored = [(candidate, heuristic_score(candidate, max_age_days)) for candidate in candidates]
    ranked = sorted(scored, key=lambda row: row[1], reverse=True)
    if chinese_ratio is None:
        return ranked[:pool_size]

    ratio = max(0.0, min(1.0, chinese_ratio))
    chinese_target = round(pool_size * ratio)
    foreign_target = pool_size - chinese_target
    chinese = [row for row in ranked if row[0].language.lower().startswith("zh")][:chinese_target]
    foreign = [row for row in ranked if not row[0].language.lower().startswith("zh")][:foreign_target]
    selected = chinese + foreign
    selected_ids = {row[0].id for row in selected}
    if len(selected) < pool_size:
        selected.extend(row for row in ranked if row[0].id not in selected_ids and len(selected) < pool_size)
    return sorted(selected, key=lambda row: row[1], reverse=True)
