"""Behavioral tests for the public API. These never contact a real model."""
import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from src.feedback_prd import quota, web_ai
from src.feedback_prd.web_api import Workspace, app

ROOT = Path(__file__).resolve().parents[1]


def test_dashscope_hybrid_model_uses_non_thinking_drafts_by_default(monkeypatch):
    monkeypatch.delenv("LLM_ENABLE_THINKING", raising=False)
    config = {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "deepseek-v4.1-flash-1017"}
    assert web_ai.request_options(config) == {"extra_body": {"enable_thinking": False}}
    monkeypatch.setenv("LLM_ENABLE_THINKING", "true")
    assert web_ai.request_options(config) == {"extra_body": {"enable_thinking": True}}


def test_other_providers_do_not_receive_dashscope_specific_parameters():
    assert web_ai.request_options({"base_url": "https://api.example.com/v1", "model": "deepseek-v4.1-flash-1017"}) == {}
    assert web_ai.request_options({"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "unrelated-model"}) == {}


@pytest.fixture
def workspace():
    return json.loads((ROOT / "public/demo.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(web_ai, "get_llm_config", lambda: {"api_key": "", "model": "test", "base_url": ""})
    return TestClient(app)


def test_default_snapshot_has_consistent_evidence(workspace):
    result = Workspace.model_validate(workspace)
    assert len(result.feedback) == 65
    assert sum(len(need.feedback_ids) for need in result.needs) == 65


def test_status_omits_credentials_and_vendor(client):
    result = client.get("/api/status").json()
    assert result["ai_available"] is False
    assert not any(key in result for key in ("api_key", "base_url", "model"))


def test_import_cleans_duplicates_and_empty_rows(client):
    response = client.post("/api/import", files={"file": ("feedback.csv", '反馈内容,评分\n"导出失败",1\n"导出失败",1\n"",3\n"希望支持引用来源",3'.encode(), "text/csv")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["cleaning"] == {"original": 4, "valid": 2, "empty": 1, "duplicates": 1}
    Workspace.model_validate(result)


def test_import_rejects_unsupported_oversized_or_too_many_rows(client):
    assert client.post("/api/import", files={"file": ("bad.txt", b"test", "text/plain")}).status_code == 400
    assert client.post("/api/import", files={"file": ("huge.csv", b"x" * (2 * 1024 * 1024 + 1), "text/csv")}).status_code == 413
    content = "feedback_text\n" + "\n".join(f"反馈 {index}" for index in range(501))
    assert client.post("/api/import", files={"file": ("many.csv", content.encode(), "text/csv")}).status_code == 400


def test_template_uses_current_evidence_and_scores(client, workspace):
    need = workspace["needs"][0]
    need["effort"] = 2.5
    response = client.post("/api/prd", json={"workspace": workspace, "need_id": need["id"]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["used_llm"] is False
    assert "Effort: 2.5" in result["markdown"]
    for identity in need["feedback_ids"]:
        assert f"#evidence-{identity}" in result["markdown"]


def test_inconsistent_links_and_non_finite_scores_rejected_without_echo(client, workspace):
    workspace["feedback"][0]["need_id"] = "missing-private-secret"
    response = client.post("/api/export", json=workspace)
    assert response.status_code == 422
    assert "missing-private-secret" not in response.text


def test_export_contains_current_calibration_and_safe_strings(client, workspace):
    original_id = workspace["feedback"][0]["id"]
    workspace["feedback"][0].update(text='=HYPERLINK("https://invalid.example")', quote='=HYPERLINK("https://invalid.example")', reviewed=True, category="Bug")
    need = workspace["needs"][0]
    need["reach"], need["impact"], need["confidence"], need["effort"] = 8, 3, 0.8, 2
    response = client.post("/api/export", json=workspace)
    assert response.status_code == 200, response.text
    book = openpyxl.load_workbook(BytesIO(response.content))
    assert {"反馈证据", "需求与RICE", "PRD文档", "修改记录"}.issubset(book.sheetnames)
    rows = list(book["反馈证据"].values)
    header = rows[0]
    row = next(item for item in rows[1:] if item[0] == original_id)
    assert row[header.index("category")] == "Bug"
    assert row[header.index("reviewed")] is True
    assert row[header.index("text")].startswith("'=HYPERLINK")
    pool = list(book["需求与RICE"].values)
    selected = next(item for item in pool[1:] if item[0] == need["id"])
    assert selected[pool[0].index("priority_score")] == 9.6


def test_model_cannot_invent_evidence_or_modify_original(client, monkeypatch, workspace):
    before = copy.deepcopy(workspace)
    monkeypatch.setattr(web_ai, "readiness", lambda: (True, "ready"))
    monkeypatch.setattr(quota, "reserve", lambda ip: None)
    monkeypatch.setattr(web_ai, "call_model", lambda *args: ('{"items":[{"id":"invented"}]}', {}))
    response = client.post("/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": [workspace["feedback"][0]["id"]]})
    assert response.status_code == 502
    assert "证据校验" in response.json()["detail"]
    assert workspace == before


def test_valid_model_analysis_keeps_unselected_feedback(client, monkeypatch, workspace):
    selected = workspace["feedback"][0]
    item = {"id": selected["id"], "scenario": "办公写作", "problem": "格式需要校准", "request": "待确认", "quote": selected["text"][:8],
            "theme": "格式与可编辑交付", "reason": "原文提到格式问题", "category": "体验问题", "sentiment": "neutral", "severity": "Low"}
    monkeypatch.setattr(web_ai, "readiness", lambda: (True, "ready"))
    monkeypatch.setattr(quota, "reserve", lambda ip: None)
    monkeypatch.setattr(web_ai, "call_model", lambda *args: (json.dumps({"items": [item]}, ensure_ascii=False), {}))
    response = client.post("/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": [selected["id"]]})
    assert response.status_code == 200, response.text
    result = response.json()["workspace"]
    assert len(result["feedback"]) == len(workspace["feedback"])
    assert next(row for row in result["feedback"] if row["id"] == selected["id"])["origin"] == "llm"
    assert next(row for row in result["feedback"] if row["id"] == workspace["feedback"][1]["id"]) == workspace["feedback"][1]
    Workspace.model_validate(result)


def test_model_prd_rejects_unrelated_citation(client, monkeypatch, workspace):
    monkeypatch.setattr(web_ai, "readiness", lambda: (True, "ready"))
    monkeypatch.setattr(quota, "reserve", lambda ip: None)
    monkeypatch.setattr(web_ai, "call_model", lambda *args: ("# 草稿\n[FB-NOTREAL](#evidence-FB-NOTREAL)", {}))
    result = client.post("/api/prd", json={"workspace": workspace, "need_id": workspace["needs"][0]["id"], "use_llm": True})
    assert result.status_code == 502
    assert "不存在" in result.json()["detail"]


def test_ai_request_limits_enforced_before_call(client, monkeypatch, workspace):
    monkeypatch.setattr(web_ai, "call_model", lambda *args: pytest.fail("model must not be called"))
    result = client.post("/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": [item["id"] for item in workspace["feedback"][:31]]})
    assert result.status_code == 422
    workspace["feedback"][0]["text"] = workspace["feedback"][0]["quote"] = "文" * 12000
    result = client.post("/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": [item["id"] for item in workspace["feedback"][:2]]})
    assert result.status_code == 400


def test_production_real_ai_fails_closed_without_budget_and_redis(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("AI_BUDGET_CONFIRMED", raising=False)
    monkeypatch.setattr(web_ai, "get_llm_config", lambda: {"api_key": "configured", "base_url": "secret", "model": "private"})
    assert web_ai.readiness()[0] is False
    monkeypatch.setenv("AI_BUDGET_CONFIRMED", "1")
    monkeypatch.setattr(quota, "configured", lambda: False)
    assert web_ai.readiness()[0] is False


def test_concurrent_local_quota_allows_exactly_three(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(quota, "configured", lambda: False)
    quota._local.clear()
    def attempt(_):
        try:
            quota.reserve("192.0.2.7", now=datetime(2026, 10, 28, tzinfo=timezone.utc))
            return True
        except quota.QuotaError:
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(attempt, range(40))) == 3
    quota._local.clear()


def test_redis_error_never_falls_back_to_per_instance_quota(monkeypatch):
    monkeypatch.setattr(quota, "configured", lambda: True)
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "secret-test-token")
    class BrokenClient:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, *args, **kwargs): raise RuntimeError("private service details")
    monkeypatch.setattr(quota.httpx, "Client", BrokenClient)
    with pytest.raises(quota.QuotaError) as error:
        quota.reserve("192.0.2.1")
    assert error.value.status == 503
    assert "secret" not in error.value.message and "private" not in error.value.message


def test_monthly_quota_shared_across_different_visitors(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(quota, "configured", lambda: False)
    quota._local.clear()
    def attempt(index):
        try:
            quota.reserve(f"visitor-{index}", now=datetime(2026, 10, 28, tzinfo=timezone.utc))
            return True
        except quota.QuotaError:
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(attempt, range(240))) == 200
    quota._local.clear()


def test_uploaded_out_of_range_rating_is_treated_as_unavailable(client):
    response = client.post("/api/import", files={"file": ("feedback.csv", 'feedback_text,rating\n希望导出,10'.encode(), "text/csv")})
    assert response.status_code == 200
    result = response.json()
    assert result["feedback"][0]["rating"] is None
    Workspace.model_validate(result)


def test_model_association_preserves_manual_rice_and_refreshes_reach(client, monkeypatch, workspace):
    from src.feedback_prd.workspace import estimate_reach
    selected = workspace["feedback"][0]
    target = next(need for need in workspace["needs"] if need["title"] == "回答可追溯与不确定性提示")
    target.update(impact=2.5, effort=1.5, confidence=0.9, status="confirmed", score_reason="人工评审成本与影响")
    item = {"id": selected["id"], "scenario": "知识工作", "problem": "需要核验", "request": "提供依据", "quote": selected["text"][:8],
            "theme": target["title"], "reason": "用于验证关联一致性", "category": "内容质量问题", "sentiment": "neutral", "severity": "Medium"}
    monkeypatch.setattr(web_ai, "readiness", lambda: (True, "ready"))
    monkeypatch.setattr(quota, "reserve", lambda ip: None)
    monkeypatch.setattr(web_ai, "call_model", lambda *args: (json.dumps({"items": [item]}, ensure_ascii=False), {}))
    response = client.post("/api/analyze", json={"workspace": workspace, "mode": "llm", "selected_ids": [selected["id"]]})
    assert response.status_code == 200, response.text
    result = response.json()["workspace"]
    updated = next(need for need in result["needs"] if need["id"] == target["id"])
    assert (updated["impact"], updated["effort"], updated["confidence"]) == (2.5, 1.5, 0.9)
    assert updated["score_reason"] == "人工评审成本与影响"
    assert updated["status"] == "pending"
    related = [row for row in result["feedback"] if row["need_id"] == target["id"]]
    assert updated["reach"] == estimate_reach(related)
    assert selected["id"] in updated["feedback_ids"]
    Workspace.model_validate(result)
