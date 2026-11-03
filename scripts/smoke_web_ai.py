"""Two bounded real-provider smoke calls, with no credentials in output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.feedback_prd import web_ai
from src.feedback_prd.analysis import analyze_feedback, load_feedback_file
from src.feedback_prd.workspace import DEFAULT_CONTEXT, render_template


def main():
    if not web_ai.readiness()[0]:
        print(json.dumps({"success": False, "reason": "AI not configured"}))
        return 1
    frame = load_feedback_file(ROOT / "data/sample_feedback.csv")
    record = analyze_feedback(frame.loc[frame.feedback_id == "FB0022"])
    records = json.loads(record.to_json(orient="records", date_format="iso", force_ascii=False))
    try:
        workspace, analysis_usage = web_ai.analyze(records, DEFAULT_CONTEXT)
        workspace["context"] = DEFAULT_CONTEXT
        need = workspace["needs"][0]
        template = render_template(need, workspace["feedback"], DEFAULT_CONTEXT)
        content, prd_usage = web_ai.generate_prd(need, workspace["feedback"], DEFAULT_CONTEXT, template)
        print(json.dumps({"success": True, "analysis_items": len(workspace["feedback"]), "prd_characters": len(content),
            "evidence_checked": True, "analysis_usage": analysis_usage, "prd_usage": prd_usage}, ensure_ascii=False))
        return 0
    except Exception as exception:
        print(json.dumps({"success": False, "error_type": type(exception).__name__,
            "reason": str(exception) if isinstance(exception, ValueError) else "Provider unavailable; no credentials logged"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
