from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from collector.models import ArticleCandidate


class ReviewProvider(ABC):
    @abstractmethod
    def review(
        self,
        candidate: ArticleCandidate,
        category: str,
        weights: dict[str, int],
        pre_score: float,
    ) -> dict[str, Any]:
        """Return a structured deep review without permanently storing article text."""
