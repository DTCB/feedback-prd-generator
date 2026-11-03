"""Measure a fixed reference set. Real model evaluation requires --mode llm."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.feedback_prd.analysis import analyze_feedback, load_feedback_file
from src.feedback_prd.workspace import DEFAULT_CONTEXT
from src.feedback_prd import web_ai


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rule", "llm"], default="rule")
    parser.add_argument("--output", default="public/evaluation.json")
    args = parser.parse_args()
    gold = json.loads((ROOT / "evaluation/gold.json").read_text(encoding="utf-8"))
    frame = load_feedback_file(ROOT / "data/sample_feedback.csv")
    frame = frame.loc[frame.feedback_id.isin([item["id"] for item in gold["items"]])]
    start = time.monotonic()
    analyzed = analyze_feedback(frame)
    if args.mode == "llm":
        result, usage = web_ai.analyze(json.loads(analyzed.to_json(orient="records", date_format="iso", force_ascii=False)), DEFAULT_CONTEXT)
        actual = {item["id"]: item for item in result["feedback"]}
    else:
        actual = {item["feedback_id"]: item for item in json.loads(analyzed.to_json(orient="records", date_format="iso", force_ascii=False))}
        usage = None
    rows = [{"id": item["id"], "expected_category": item["category"], "actual_category": actual[item["id"]]["category"],
             "expected_sentiment": item["sentiment"], "actual_sentiment": actual[item["id"]]["sentiment"]} for item in gold["items"]]
    report = {
        "mode": args.mode, "sample_count": len(rows), "label_note": gold["description"],
        "category_correct": sum(row["expected_category"] == row["actual_category"] for row in rows),
        "sentiment_correct": sum(row["expected_sentiment"] == row["actual_sentiment"] for row in rows),
        "elapsed_seconds": round(time.monotonic() - start, 3), "usage": usage,
        "generated_at": datetime.now(timezone.utc).isoformat(), "items": rows,
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("mode", "sample_count", "category_correct", "sentiment_correct", "elapsed_seconds", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
