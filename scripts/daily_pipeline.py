from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collector.pipeline import run_daily_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Signal Radar daily discovery pipeline.")
    parser.add_argument("--date", help="Digest date in YYYY-MM-DD format (defaults to today in UTC).")
    parser.add_argument("--sample", action="store_true", help="Use offline sample candidates instead of the network.")
    args = parser.parse_args()

    payload, output = run_daily_pipeline(date=args.date, sample=args.sample)
    stats = payload["stats"]
    print(
        f"Signal Radar complete: {stats['discovered']} discovered, "
        f"{stats['deepReviewed']} reviewed, {stats['recommended']} recommended."
    )
    print(f"Digest: {output}")
    if payload["errors"]:
        print(f"Non-blocking errors: {len(payload['errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
