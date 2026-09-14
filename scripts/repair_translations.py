from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collector.config import load_local_env  # noqa: E402
from collector.fetchers import ArticleExtractor  # noqa: E402
from collector.llm import OpenAIReviewProvider  # noqa: E402
from collector.models import ArticleCandidate  # noqa: E402


def main() -> int:
    load_local_env()
    latest_path = PROJECT_ROOT / "data" / "daily" / "latest.json"
    digest = json.loads(latest_path.read_text(encoding="utf-8"))
    provider = OpenAIReviewProvider()
    extractor = ArticleExtractor()
    repaired = 0

    for article in digest.get("articles", []):
        if article.get("language", "en").lower().startswith("zh"):
            continue
        if article.get("translationStatus") == "available" and article.get("translationZh"):
            continue
        candidate = ArticleCandidate(
            id=article["id"],
            title=article["title"],
            url=article["url"],
            author=article.get("author", ""),
            source=article.get("source", ""),
            source_category=article.get("category", "other"),
            language=article.get("language", "en"),
            snippet=article.get("sourceSnippet", ""),
        )
        candidate = extractor.extract(candidate)
        article["translationZh"] = provider.translate_to_chinese(candidate)
        article["translationStatus"] = "available"
        repaired += 1

    serialized = json.dumps(digest, ensure_ascii=False, indent=2) + "\n"
    latest_path.write_text(serialized, encoding="utf-8")
    dated_path = PROJECT_ROOT / "data" / "daily" / f"{digest['date']}.json"
    dated_path.write_text(serialized, encoding="utf-8")
    print(f"Translation repair complete: {repaired} article(s) repaired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
