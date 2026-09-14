from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collector.models import ArticleCandidate  # noqa: E402
from collector.ranking.deduplicate import deduplicate  # noqa: E402
from collector.ranking.diversity import build_digest  # noqa: E402
from collector.ranking.prerank import pre_rank  # noqa: E402
from collector.ranking.scoring import calculate_final_score  # noqa: E402


class RankingTests(unittest.TestCase):
    def test_weighted_score_is_on_zero_to_one_hundred_scale(self) -> None:
        scores = {"impact": 5, "novelty": 2.5}
        self.assertEqual(calculate_final_score(scores, {"impact": 60, "novelty": 40}), 80.0)

    def test_deduplication_keeps_higher_priority_source(self) -> None:
        low = ArticleCandidate(
            id="low",
            title="A new model changes product design",
            url="https://mirror.example/story?utm_source=x",
            source="Mirror",
            source_priority="low",
        )
        high = ArticleCandidate(
            id="high",
            title="A new model changes product design",
            url="https://original.example/story",
            source="Original",
            source_priority="high",
        )
        result = deduplicate([low, high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "Original")
        self.assertIn("Mirror", result[0].duplicate_sources)

    def test_digest_balances_chinese_and_foreign_articles(self) -> None:
        articles = []
        for index, language in enumerate(["zh-CN", "en", "zh-CN", "en", "zh-CN", "en"]):
            articles.append(
                {
                    "id": str(index),
                    "source": f"source-{index}",
                    "category": "product-insight",
                    "language": language,
                    "topics": [f"topic-{index}"],
                    "finalScore": 95 - index,
                }
            )
        config = {
            "thresholds": {"must_read": 88, "worth_reading": 78, "signal": 64},
            "limits": {"total": 4, "must_read": 4, "worth_reading": 0, "signals": 0},
            "diversity": {"max_per_source": 2, "max_per_topic": 2},
            "language_balance": {"enabled": True, "target_chinese_ratio": 0.5},
        }
        selected = build_digest(articles, config)
        chinese = sum(1 for row in selected if row["language"].startswith("zh"))
        self.assertEqual(len(selected), 4)
        self.assertEqual(chinese, 2)

    def test_pre_rank_balances_review_pool_languages(self) -> None:
        candidates = [
            ArticleCandidate(
                id=str(index),
                title=f"article {index}",
                url=f"https://example.com/{index}",
                language="zh-CN" if index < 8 else "en",
                source_category="ai-news",
                source_priority="high",
            )
            for index in range(16)
        ]
        selected = pre_rank(candidates, pool_size=10, chinese_ratio=0.5)
        chinese = sum(1 for article, _ in selected if article.language.startswith("zh"))
        self.assertEqual(len(selected), 10)
        self.assertEqual(chinese, 5)


if __name__ == "__main__":
    unittest.main()
