"""Check a deployment; --live runs 3 model operations and a fourth-call quota probe."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.feedback_prd.web_ai import validate_prd
from src.feedback_prd.web_api import Workspace


def verify(base: str, live: bool) -> dict:
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Use an HTTPS origin without credentials or a path")
    result = {"success": False, "live_requested": live}
    with httpx.Client(base_url=base.rstrip("/"), timeout=110, follow_redirects=False) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        status = request("GET", "/api/status")
        if set(status) != {"ai_available", "message", "limits"}:
            raise RuntimeError("Unexpected public status fields")
        result.update(ai_available=status["ai_available"], limits=status["limits"])
        if not live:
            return {**result, "success": True, "model_calls": 0}
        if not status["ai_available"]:
            raise RuntimeError("Real AI is still disabled")
        csv = "反馈内容\n回答里没有来源链接，无法核验结论，希望提供可点击的原文出处。\n"
        workspace = request("POST", "/api/import", files={"file": ("synthetic-smoke.csv", csv.encode("utf-8"), "text/csv")})
        Workspace.model_validate(workspace)
        ids = [row["id"] for row in workspace["feedback"]]
        analyzed = request("POST", "/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": ids})
        if analyzed.get("used_llm") is not True:
            raise RuntimeError("Analysis did not use a real model")
        workspace = analyzed["workspace"]
        Workspace.model_validate(workspace)
        if any(row["quote"] not in row["text"] for row in workspace["feedback"]):
            raise RuntimeError("Analysis quote is not from the source")
        need = workspace["needs"][0]
        payload = {"workspace": workspace, "need_id": need["id"], "use_llm": True}
        generated = request("POST", "/api/prd", json=payload)
        if generated.get("used_llm") is not True:
            raise RuntimeError("PRD did not use a real model")
        validate_prd(generated["markdown"], workspace["feedback"])
        identity = ids[0]
        draft = f"## 验收标准\n用户可查看来源链接并核验结论。[{identity}](#evidence-{identity})"
        revised = request("POST", "/api/prd", json={**payload, "action": "revise", "draft": draft,
            "instruction": "仅改写验收标准章节，用三条可测试的标准表达，并保留给定证据引用。"})
        if revised.get("used_llm") is not True:
            raise RuntimeError("Revision did not use a real model")
        validate_prd(revised["markdown"], workspace["feedback"])
        blocked = client.post("/api/prd", json=payload)
        if blocked.status_code != 429 or "今天" not in blocked.json().get("detail", ""):
            raise RuntimeError("The fourth call was not rejected by the daily limiter")
        template = request("POST", "/api/prd", json={**payload, "use_llm": False})
        if template.get("used_llm") is not False:
            raise RuntimeError("Template fallback failed after exhaustion")
        return {**result, "success": True, "model_calls": 3, "source_quotes_checked": True,
                "prd_citations_checked": True, "fourth_call_status": 429, "template_after_limit": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://feedback-lens-six.vercel.app")
    parser.add_argument("--live", action="store_true", help="Spend 3 model calls; requires an unused daily IP allowance")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.base_url, args.live), ensure_ascii=False))
        return 0
    except Exception as exception:
        print(json.dumps({"success": False, "error_type": type(exception).__name__,
                          "reason": "Deployment verification failed; no retries or extra model calls were made."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
