"""Build the checked-in, offline-first demo snapshot; never calls a model."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.feedback_prd.workspace import build_workspace, render_template
from src.feedback_prd.analysis import load_feedback_file


def main():
    workspace = build_workspace(load_feedback_file(ROOT / "data" / "sample_feedback.csv"), curated=True)
    focus = next(need for need in workspace["needs"] if need["title"] == "回答可追溯与不确定性提示")
    workspace["documents"][focus["id"]] = {
        "markdown": render_template(focus, workspace["feedback"], workspace["context"]),
        "origin": "template", "edited": False, "stale": False, "updated_at": "",
    }
    output = ROOT / "public" / "demo.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(workspace, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Demo snapshot: {len(workspace['feedback'])} feedback, {len(workspace['needs'])} needs; no model calls.")


if __name__ == "__main__":
    main()
