from __future__ import annotations

from collector.models import ArticleCandidate
from collector.text import normalize_title

KEYWORDS = {
    "career": {
        "interview",
        "career",
        "resume",
        "job search",
        "hiring",
        "product manager",
        "求职",
        "面试",
        "简历",
        "项目复盘",
    },
    "product-insight": {
        "product strategy",
        "product management",
        "case study",
        "growth",
        "retention",
        "user research",
        "product-market fit",
        "产品",
        "增长",
        "用户研究",
    },
    "ai-news": {
        "artificial intelligence",
        "machine learning",
        "llm",
        "model",
        "openai",
        "anthropic",
        "deepmind",
        "agent",
        "人工智能",
        "大模型",
        "多模态",
    },
}


def classify(candidate: ArticleCandidate) -> str:
    if candidate.source_category in {"ai-news", "product-insight", "career"}:
        return candidate.source_category

    haystack = normalize_title(f"{candidate.title} {candidate.snippet}")
    matches = {
        category: sum(1 for keyword in keywords if keyword in haystack)
        for category, keywords in KEYWORDS.items()
    }
    category, score = max(matches.items(), key=lambda row: row[1])
    return category if score else "other"
