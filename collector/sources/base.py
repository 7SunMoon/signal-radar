from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from collector.models import ArticleCandidate


class SourceProvider(ABC):
    name: str

    @abstractmethod
    def discover(self, config: dict[str, Any]) -> list[ArticleCandidate]:
        """Return normalized candidate metadata. Provider failures are handled by the pipeline."""
