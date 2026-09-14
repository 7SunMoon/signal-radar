from __future__ import annotations

import hashlib
from typing import Any

from collector.llm.base import ReviewProvider
from collector.models import ArticleCandidate
from collector.text import clean_text


class MockReviewProvider(ReviewProvider):
    """Deterministic offline reviewer for first-run demos and pipeline development."""

    def _score(self, seed: str, index: int, pre_score: float) -> float:
        digest = hashlib.sha1(f"{seed}:{index}".encode("utf-8")).digest()[0]
        # Metadata-only mode should remain conservative, while still allowing
        # strong, timely first-party sources to reach the visible digest.
        baseline = 3.2 + min(1.4, pre_score / 100)
        return round(max(0, min(5, baseline + (digest % 12 - 5) / 10)), 1)

    def review(
        self,
        candidate: ArticleCandidate,
        category: str,
        weights: dict[str, int],
        pre_score: float,
    ) -> dict[str, Any]:
        context = clean_text(candidate.snippet or candidate.content)[:360]
        is_chinese = candidate.language.lower().startswith("zh")
        title_zh = candidate.title
        focus = {
            "ai-news": "这项进展可能改变 AI 产品的能力边界、成本结构或交互方式",
            "product-insight": "文章提供了可以迁移到 AI 产品判断与设计中的分析框架",
            "career": "内容包含可用于求职表达、项目复盘或能力建设的具体线索",
        }.get(category, "该内容与当前关注方向存在一定关联")
        return {
            "category": category,
            "titleZh": title_zh,
            "summaryZh": (
                f"{focus}。{context or '当前仅获取到标题与来源信息，以下判断主要基于公开元数据。'}"
                if is_chinese
                else "当前为 Metadata Review。真实原文已经采集；配置 OpenAI 后将生成中文详细摘要与核心译文。"
            ),
            "translationZh": "",
            "keyIdeas": [
                f"核心信号围绕“{candidate.title}”展开，需要结合原文确认其实际影响范围。",
                "判断价值时应同时关注一手证据、可迁移的方法和作者未明说的前提。",
            ],
            "counterPoint": "现有信息可能夸大短期变化，且缺少足够的长期使用数据或反例；阅读时应区分事实、预测与作者立场。",
            "whyForMe": "它可用于训练你对 AI 产品机会的判断，并沉淀为面试中的行业观点或项目决策依据。",
            # Put a story-specific topic first so metadata mode does not collapse
            # every article in the same category into one diversity cluster.
            "topics": [candidate.title[:48], category],
            "importantTerms": [] if is_chinese else [
                {"term": "signal", "explanationZh": "尚未成为共识、但可能影响后续判断的早期迹象。"}
            ],
            "scores": {
                dimension: self._score(candidate.id, index, pre_score)
                for index, dimension in enumerate(weights)
            },
        }
