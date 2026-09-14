from __future__ import annotations

from collections import Counter
from typing import Any


def _topic_key(article: dict[str, Any]) -> str:
    topics = article.get("topics") or []
    return str(topics[0]).lower() if topics else article.get("category", "other")


def _is_chinese(article: dict[str, Any]) -> bool:
    return str(article.get("language", "")).lower().startswith("zh")


def _take_diverse(
    candidates: list[dict[str, Any]],
    limit: int,
    source_limit: int,
    topic_limit: int,
    chinese_ratio: float | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()

    def add_from(pool: list[dict[str, Any]], target: int) -> None:
        for article in pool:
            if len(selected) >= target:
                break
            if article in selected:
                continue
            source = article.get("source", "")
            topic = _topic_key(article)
            if source_counts[source] >= source_limit or topic_counts[topic] >= topic_limit:
                continue
            selected.append(article)
            source_counts[source] += 1
            topic_counts[topic] += 1

    if chinese_ratio is not None:
        ratio = max(0.0, min(1.0, chinese_ratio))
        chinese_target = round(limit * ratio)
        foreign_target = limit - chinese_target
        add_from([row for row in candidates if _is_chinese(row)], chinese_target)
        chinese_selected = len(selected)
        add_from([row for row in candidates if not _is_chinese(row)], chinese_selected + foreign_target)

    for article in candidates:
        if len(selected) >= limit:
            break
        if article in selected:
            continue
        source = article.get("source", "")
        topic = _topic_key(article)
        if source_counts[source] >= source_limit or topic_counts[topic] >= topic_limit:
            continue
        selected.append(article)
        source_counts[source] += 1
        topic_counts[topic] += 1
        if len(selected) >= limit:
            break
    selected.sort(key=lambda row: row.get("finalScore", 0), reverse=True)
    return selected


def _cap_total_balanced(
    articles: list[dict[str, Any]],
    limit: int,
    chinese_ratio: float | None,
) -> list[dict[str, Any]]:
    tier_priority = {"must-read": 0, "worth-reading": 1, "signal": 2}
    ranked = sorted(
        articles,
        key=lambda row: (tier_priority.get(row.get("readingTier", "signal"), 3), -row.get("finalScore", 0)),
    )
    if len(ranked) <= limit:
        return ranked
    if chinese_ratio is None:
        return ranked[:limit]

    chinese_target = round(limit * max(0.0, min(1.0, chinese_ratio)))
    foreign_target = limit - chinese_target
    selected = [row for row in ranked if _is_chinese(row)][:chinese_target]
    selected.extend([row for row in ranked if not _is_chinese(row)][:foreign_target])
    selected_ids = {row["id"] for row in selected}
    if len(selected) < limit:
        selected.extend(row for row in ranked if row["id"] not in selected_ids and len(selected) < limit)
    return sorted(
        selected,
        key=lambda row: (tier_priority.get(row.get("readingTier", "signal"), 3), -row.get("finalScore", 0)),
    )


def build_digest(articles: list[dict[str, Any]], ranking_config: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = ranking_config["thresholds"]
    limits = ranking_config["limits"]
    diversity = ranking_config["diversity"]
    balance = ranking_config.get("language_balance", {})
    chinese_ratio = float(balance.get("target_chinese_ratio", 0.5)) if balance.get("enabled", False) else None
    ranked = sorted(articles, key=lambda row: row.get("finalScore", 0), reverse=True)

    must_pool = [row for row in ranked if row["category"] != "other" and row["finalScore"] >= thresholds["must_read"]]
    must = _take_diverse(
        must_pool,
        limits["must_read"],
        diversity["max_per_source"],
        diversity["max_per_topic"],
        chinese_ratio,
    )
    used = {row["id"] for row in must}

    worth_pool = [
        row
        for row in ranked
        if row["id"] not in used
        and row["category"] != "other"
        and row["finalScore"] >= thresholds["worth_reading"]
    ]
    worth = _take_diverse(
        worth_pool,
        limits["worth_reading"],
        diversity["max_per_source"],
        diversity["max_per_topic"],
        chinese_ratio,
    )
    used.update(row["id"] for row in worth)

    signal_pool = [
        row
        for row in ranked
        if row["id"] not in used
        and row["category"] == "ai-news"
        and row["finalScore"] >= thresholds["signal"]
    ]
    signals = _take_diverse(
        signal_pool,
        limits["signals"],
        diversity["max_per_source"],
        diversity["max_per_topic"],
        chinese_ratio,
    )

    for article in must:
        article["readingTier"] = "must-read"
    for article in worth:
        article["readingTier"] = "worth-reading"
    for article in signals:
        article["readingTier"] = "signal"
    return _cap_total_balanced(must + worth + signals, int(limits.get("total", 18)), chinese_ratio)
