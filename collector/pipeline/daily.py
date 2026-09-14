from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from collector.config import PROJECT_ROOT, load_local_env, load_ranking, load_sources
from collector.fetchers import ArticleExtractor
from collector.llm import MockReviewProvider, OpenAIReviewProvider, ReviewProvider
from collector.models import ArticleCandidate, utc_now_iso
from collector.ranking import build_digest, calculate_final_score, classify, deduplicate, pre_rank
from collector.sources import BraveSearchProvider, HackerNewsProvider, RSSProvider
from collector.text import stable_id


@dataclass
class PipelineState:
    candidates: list[ArticleCandidate] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def record_error(self, source: str, error: Exception | str) -> None:
        self.errors.append({"source": source, "error": str(error), "timestamp": utc_now_iso()})


def _discover(source_config: dict[str, Any]) -> list[ArticleCandidate]:
    provider_type = source_config.get("type")
    if provider_type == "rss":
        return RSSProvider().discover(source_config)
    if provider_type == "hacker-news":
        return HackerNewsProvider().discover(source_config)
    raise ValueError(f"Unsupported source type: {provider_type}")


def discover_all(config: dict[str, Any], state: PipelineState) -> None:
    sources = config.get("sources", [])
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(sources)))) as executor:
        jobs = [(source, executor.submit(_discover, source)) for source in sources]
        for source, future in jobs:
            try:
                state.candidates.extend(future.result())
            except Exception as exc:  # isolation boundary: one source cannot stop the run
                state.record_error(source.get("name", source.get("type", "unknown")), exc)

    search_config = config.get("web_search", {})
    if search_config.get("enabled", False):
        provider = BraveSearchProvider()
        if provider.available:
            try:
                state.candidates.extend(provider.discover(search_config))
            except Exception as exc:
                state.record_error("Brave Search", exc)


def _review_provider() -> tuple[ReviewProvider, str]:
    requested = os.getenv("LLM_PROVIDER", "auto").lower()
    openai = OpenAIReviewProvider()
    if requested == "openai" and not openai.available:
        raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is missing")
    if openai.available and requested in {"auto", "openai"}:
        return openai, "openai"
    return MockReviewProvider(), "metadata"


def _article_record(
    candidate: ArticleCandidate,
    category: str,
    review: dict[str, Any],
    final_score: float,
    pre_score: float,
) -> dict[str, Any]:
    text_length = len(candidate.content or candidate.snippet)
    reading_minutes = max(1, round(text_length / 900)) if text_length else None
    is_chinese = candidate.language.lower().startswith("zh")
    translation_zh = str(review.get("translationZh", "")).strip()
    return {
        "id": candidate.id,
        "title": candidate.title,
        "titleZh": review.get("titleZh") or candidate.title,
        "url": candidate.url,
        "author": candidate.author,
        "source": candidate.source,
        "publishedAt": candidate.published_at,
        "discoveredAt": candidate.discovered_at,
        "language": candidate.language,
        "category": review.get("category") if review.get("category") in {"ai-news", "product-insight", "career"} else category,
        "summaryZh": review.get("summaryZh", ""),
        "translationZh": translation_zh,
        "translationStatus": "not-needed" if is_chinese else ("available" if translation_zh else "pending"),
        "sourceSnippet": candidate.snippet,
        "keyIdeas": review.get("keyIdeas", [])[:5],
        "counterPoint": review.get("counterPoint", ""),
        "whyForMe": review.get("whyForMe", ""),
        "topics": review.get("topics", [])[:6],
        "importantTerms": review.get("importantTerms", [])[:5],
        "scores": review.get("scores", {}),
        "finalScore": final_score,
        "preRankingScore": pre_score,
        "readingTier": "unselected",
        "socialSignals": candidate.social_signals,
        "contentAvailability": candidate.content_availability,
        "estimatedReadingMinutes": reading_minutes,
        "duplicateSources": sorted(set(candidate.duplicate_sources)),
    }


def _write_digest(payload: dict[str, Any], date: str) -> Path:
    daily_dir = PROJECT_ROOT / "data" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    dated_path = daily_dir / f"{date}.json"
    latest_path = daily_dir / "latest.json"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    return dated_path


def _write_errors(errors: list[dict[str, str]], date: str) -> None:
    if not errors:
        return
    error_dir = PROJECT_ROOT / "data" / "errors"
    error_dir.mkdir(parents=True, exist_ok=True)
    path = error_dir / f"{date}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        for error in errors:
            handle.write(json.dumps(error, ensure_ascii=False) + "\n")


def sample_candidates() -> list[ArticleCandidate]:
    """Small offline input set used by tests and first-run demos."""
    now = utc_now_iso()
    rows = [
        ("AI agents move from demos to governed workflows", "https://example.com/ai-agent-workflows", "Research Lab", "ai-news", "A release focused on tool reliability, approvals and long-running tasks."),
        ("Why product teams should measure decision quality", "https://example.com/decision-quality", "Product Field Notes", "product-insight", "A framework for separating decision quality from outcome luck."),
        ("How I turned one AI prototype into an interview story", "https://example.com/pm-interview-story", "Builder Journal", "career", "A concrete project retrospective with metrics, tradeoffs and failures."),
        ("A smaller multimodal model changes on-device economics", "https://example.com/on-device-model", "AI Systems", "ai-news", "New latency and cost tradeoffs make local product experiences more feasible."),
    ]
    return [
        ArticleCandidate(
            id=stable_id(url, title),
            title=title,
            url=url,
            author="Editorial Team",
            source=source,
            source_category=category,
            source_priority="high",
            published_at=now,
            snippet=snippet,
            canonical_url=url,
        )
        for title, url, source, category, snippet in rows
    ]


def run_daily_pipeline(*, date: str | None = None, sample: bool = False) -> tuple[dict[str, Any], Path]:
    load_local_env()
    timezone_name = os.getenv("RADAR_TIMEZONE", "Asia/Shanghai")
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_timezone = timezone.utc
    run_date = date or datetime.now(local_timezone).date().isoformat()
    sources_config = load_sources()
    ranking_config = load_ranking()
    state = PipelineState(candidates=sample_candidates() if sample else [])
    if not sample:
        discover_all(sources_config, state)
    discovered_count = len(state.candidates)

    threshold = float(ranking_config["diversity"].get("title_similarity_threshold", 0.84))
    unique = deduplicate(state.candidates, threshold)
    eligible: list[ArticleCandidate] = []
    categories: dict[str, str] = {}
    for candidate in unique:
        category = classify(candidate)
        categories[candidate.id] = category
        if category != "other":
            candidate.source_category = category
            eligible.append(candidate)

    pre_config = ranking_config["pre_ranking"]
    balance_config = ranking_config.get("language_balance", {})
    chinese_ratio = (
        float(balance_config.get("target_chinese_ratio", 0.5))
        if balance_config.get("enabled", False)
        else None
    )
    candidate_pool = pre_rank(
        eligible,
        pool_size=int(pre_config["candidate_pool_size"]),
        max_age_days=int(pre_config["max_age_days"]),
        chinese_ratio=chinese_ratio,
    )
    extractor = ArticleExtractor()
    with ThreadPoolExecutor(max_workers=6) as executor:
        extracted = list(executor.map(lambda row: extractor.extract(row[0]), candidate_pool))

    try:
        reviewer, review_mode = _review_provider()
    except RuntimeError as exc:
        state.record_error("OpenAI", exc)
        reviewer, review_mode = MockReviewProvider(), "metadata-fallback"

    if sample:
        review_mode = "demo"

    reviewed: list[dict[str, Any]] = []
    rubrics = ranking_config["rubrics"]
    consecutive_llm_failures = 0
    llm_failure_limit = max(1, int(os.getenv("LLM_CONSECUTIVE_FAILURE_LIMIT", "2")))
    for index, ((candidate, pre_score), extracted_candidate) in enumerate(zip(candidate_pool, extracted)):
        category = categories[candidate.id]
        weights = rubrics[category]
        try:
            review = reviewer.review(extracted_candidate, category, weights, pre_score)
            consecutive_llm_failures = 0
        except Exception as exc:
            state.record_error(f"LLM:{candidate.id}", exc)
            review = MockReviewProvider().review(extracted_candidate, category, weights, pre_score)
            consecutive_llm_failures += 1
            if (
                not isinstance(reviewer, MockReviewProvider)
                and consecutive_llm_failures >= llm_failure_limit
            ):
                reviewer = MockReviewProvider()
                review_mode = "metadata-fallback"
                state.record_error(
                    "LLM circuit breaker",
                    f"Disabled LLM review after {consecutive_llm_failures} consecutive failures",
                )
        final_score = calculate_final_score(review.get("scores", {}), weights)
        reviewed.append(_article_record(extracted_candidate, category, review, final_score, pre_score))

    selected = build_digest(reviewed, ranking_config)
    if isinstance(reviewer, OpenAIReviewProvider):
        extracted_by_id = {candidate.id: candidate for candidate in extracted}
        for article in selected:
            needs_translation = (
                not article["language"].lower().startswith("zh")
                and article.get("translationStatus") != "available"
            )
            candidate = extracted_by_id.get(article["id"])
            if not needs_translation or candidate is None:
                continue
            try:
                translation = reviewer.translate_to_chinese(candidate)
                article["translationZh"] = translation
                article["translationStatus"] = "available"
            except Exception as exc:
                state.record_error(f"Translation:{article['id']}", exc)
    payload = {
        "schemaVersion": 1,
        "date": run_date,
        "generatedAt": utc_now_iso(),
        "mode": review_mode,
        "stats": {
            "discovered": discovered_count,
            "afterDeduplication": len(unique),
            "deepReviewed": len(candidate_pool),
            "recommended": len(selected),
        },
        "articles": selected,
        "errors": state.errors,
    }
    output = _write_digest(payload, run_date)
    _write_errors(state.errors, run_date)
    return payload, output
