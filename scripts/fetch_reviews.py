"""Fetch Google Play reviews into the unified feedback CSV schema.

This script is intentionally optional: the application should not depend on it
at demo/runtime. Install google-play-scraper only when refreshing review data.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


FIELDNAMES = [
    "feedback_id",
    "date",
    "source",
    "app_name",
    "channel",
    "rating",
    "version",
    "user_type",
    "module",
    "feedback_text",
    "thumbs_up",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Google Play reviews and write the unified feedback CSV."
    )
    parser.add_argument("--app-id", required=True, help="Google Play package ID.")
    parser.add_argument(
        "--app-name",
        default=None,
        help="Display app name to store in the CSV. Defaults to --app-id.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of reviews to fetch. Defaults to 100.",
    )
    parser.add_argument("--lang", default="zh", help="Review language. Defaults to zh.")
    parser.add_argument(
        "--country", default="cn", help="Google Play country code. Defaults to cn."
    )
    parser.add_argument(
        "--output",
        default="data/google_play_reviews.csv",
        help="Output CSV path. Defaults to data/google_play_reviews.csv.",
    )
    return parser.parse_args()


def format_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value:
        return str(value)[:10]
    return ""


def map_review(review: dict[str, Any], index: int, app_name: str) -> dict[str, Any]:
    return {
        "feedback_id": f"GP{index:05d}",
        "date": format_date(review.get("at")),
        "source": "google_play",
        "app_name": app_name,
        "channel": "public_review",
        "rating": review.get("score", ""),
        "version": review.get("appVersion")
        or review.get("reviewCreatedVersion")
        or "",
        "user_type": "unknown",
        "module": "unknown",
        "feedback_text": review.get("content", ""),
        "thumbs_up": review.get("thumbsUpCount", 0),
    }


def write_csv(rows: Iterable[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def fetch_google_play_reviews(args: argparse.Namespace) -> list[dict[str, Any]]:
    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:
        raise RuntimeError(
            "Missing optional dependency 'google-play-scraper'. "
            "Install it with: pip install google-play-scraper"
        ) from exc

    raw_reviews, _continuation_token = reviews(
        args.app_id,
        lang=args.lang,
        country=args.country,
        sort=Sort.NEWEST,
        count=max(args.count, 0),
    )
    app_name = args.app_name or args.app_id
    return [
        map_review(review, index, app_name)
        for index, review in enumerate(raw_reviews, start=1)
    ]


def main() -> int:
    args = parse_args()
    if args.count < 0:
        print("--count must be greater than or equal to 0.", file=sys.stderr)
        return 2

    try:
        rows = fetch_google_play_reviews(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output = Path(args.output)
    write_csv(rows, output)
    print(f"Wrote {len(rows)} reviews to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
