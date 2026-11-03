"""Shared, stateless workspace representation for the web application."""
from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from typing import Any

import pandas as pd

from .analysis import _reach_from_count, _reach_from_likes, analyze_feedback, build_need_pool, generate_prd_markdown, standardize_feedback

CATEGORIES = ["Bug", "功能需求", "体验问题", "内容质量问题", "咨询/付费问题"]
DEFAULT_CONTEXT = {
    "product": "面向知识工作者的 AI 助手",
    "audience": "使用 AI 进行资料查证、内容写作和日常办公的用户",
    "goal": "提高输出的可核验性与任务完成质量，减少人工返工",
    "capabilities": "对话问答、长文总结、写作改写与文档导出",
    "constraints": "两周内验证一个最小方案；保留人工判断，不承诺所有回答正确",
}
MODULE_LABELS = {
    "content": "回答质量", "citation": "引用与溯源", "summary": "长文总结",
    "performance": "性能体验", "crash": "运行稳定性", "export": "内容导出",
    "login": "账号登录", "subscription": "订阅管理", "payment": "支付服务",
    "pricing": "计费说明", "writing": "写作改写", "template": "场景模板",
    "voice": "语音输入", "keyboard": "键盘输入", "privacy": "隐私保护",
    "history": "历史记录", "memory": "上下文记忆", "search": "内容搜索",
    "ads": "广告体验", "sync": "跨端同步", "permission": "权限管理",
    "tone": "语气调整", "brand_voice": "品牌语气", "localization": "本地化",
    "translation": "翻译", "paraphrase": "改写", "grammar": "语法检查",
    "collaboration": "团队协作", "workflow": "使用流程", "onboarding": "新手引导",
    "prompt": "提示词", "chat": "对话体验",
}


def clean_feedback(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    if len(frame) > 500:
        raise ValueError("最多导入 500 条反馈，请拆分后重试。")
    normalized = standardize_feedback(frame)
    original = len(normalized)
    normalized["feedback_text"] = normalized["feedback_text"].fillna("").astype(str).str.strip()
    if normalized["feedback_text"].str.len().gt(12000).any():
        raise ValueError("单条反馈不能超过 12,000 字。")
    normalized = normalized.loc[normalized["feedback_text"].ne("")].copy()
    empty = original - len(normalized)
    before_dedupe = len(normalized)
    normalized = normalized.drop_duplicates(subset=["feedback_text"]).reset_index(drop=True)
    duplicates = before_dedupe - len(normalized)
    if normalized.empty:
        raise ValueError("没有有效反馈，请提供包含文字的反馈内容列。")
    normalized["rating"] = normalized["rating"].where(normalized["rating"].between(0, 5))
    # Canonical, safe, unique IDs are required for citations and HTML anchors.
    seen: set[str] = set()
    for index in normalized.index:
        candidate = str(normalized.at[index, "feedback_id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", candidate) or candidate in seen:
            candidate = f"FB-{index + 1:04d}"
            while candidate in seen:
                candidate += "x"
        seen.add(candidate)
        normalized.at[index, "feedback_id"] = candidate
    return normalized, {"original": original, "valid": len(normalized), "empty": empty, "duplicates": duplicates}


def sample_theme(row: dict[str, Any]) -> str:
    """Editorial grouping for the explicitly labelled, pre-arranged demo only."""
    text, module = str(row["feedback_text"]), str(row["module"])
    if any(word in text for word in ["事实", "核对", "结论不完整", "改变原意", "负责人", "引用"]):
        return "回答可追溯与不确定性提示"
    if module in {"crash", "performance", "keyboard"}:
        return "长任务稳定性与性能优化"
    if module == "export":
        return "保留结构的多格式文档导出"
    if module in {"subscription", "payment", "pricing"}:
        return "订阅状态与计费透明化"
    if module == "login":
        return "登录异常与账号恢复"
    if module in {"history", "memory", "sync"}:
        return "历史记录与上下文管理"
    if module in {"privacy", "permission", "ads"}:
        return "权限透明与无干扰体验"
    return "写作场景与输出控制"


def build_workspace(frame: pd.DataFrame, *, curated: bool = False) -> dict[str, Any]:
    normalized, cleaning = clean_feedback(frame)
    analyzed = analyze_feedback(normalized)
    records = json.loads(analyzed.to_json(orient="records", date_format="iso", force_ascii=False))
    if curated:
        for row in records:
            row["need_summary"] = sample_theme(row)
    workspace = assemble_workspace(records, origin="sample" if curated else "rule")
    workspace.update({"cleaning": cleaning, "context": DEFAULT_CONTEXT.copy(), "is_sample": curated})
    return workspace


def assemble_workspace(records: list[dict[str, Any]], origin: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        groups.setdefault(row["need_summary"], []).append(row)
    needs, feedback = [], []
    for title, rows in groups.items():
        need_id = "N-" + hashlib.sha256(title.encode()).hexdigest()[:10]
        # Reuse the established RICE estimator with one aggregate group, without
        # changing each feedback's original category or source module.
        pool_input = pd.DataFrame(rows).assign(need_summary=title, category=rows[0]["category"], module="工作台需求")
        estimate = build_need_pool(pool_input).iloc[0].to_dict()
        needs.append({
            "id": need_id, "title": title, "description": f"从 {len(rows)} 条关联反馈中整理的问题线索，需结合产品目标与原文进一步确认。",
            "category": rows[0]["category"], "module": MODULE_LABELS.get(str(rows[0].get("module")), "其他"),
            "feedback_ids": [row["feedback_id"] for row in rows],
            "reach": float(estimate["rice_reach"]), "impact": float(estimate["rice_impact"]),
            "confidence": float(estimate["rice_confidence"]), "effort": float(estimate["rice_effort"]),
            "status": "pending", "origin": origin,
            "score_reason": "初值来自现有规则估计；Reach 为反馈数与点赞数的归一化代理值，Impact、Confidence、Effort 需人工评估。",
        })
        for row in rows:
            text = row["feedback_text"]
            feedback.append({
                "id": row["feedback_id"], "text": text, "date": (row.get("date") or "")[:10],
                "source": row.get("source") or "手动导入", "app_name": row.get("app_name") or "未指定产品",
                "rating": row.get("rating"), "user_type": row.get("user_type") or "未标注",
                "module": MODULE_LABELS.get(str(row.get("module")), str(row.get("module") or "其他")),
                "thumbs_up": row.get("thumbs_up", 0), "category": row["category"],
                "sentiment": row["sentiment"], "severity": row["severity"],
                "need_id": need_id, "reviewed": False, "origin": origin,
                "quote": row.get("quote") or text[:240],
                "scenario": row.get("scenario") or f"使用{MODULE_LABELS.get(str(row.get('module')), 'AI 助手')}完成任务时",
                "problem": row.get("problem") or text[:300],
                "request": row.get("request") or "结合原文确认具体诉求与功能边界。",
                "reason": row.get("reason") or ("规则预分析结果，请根据原始反馈校准；演示分组由人工整理。" if origin == "sample" else "规则依据关键词与评分估计，需要人工复核。"),
            })
    feedback.sort(key=lambda item: item["id"])
    return {"feedback": feedback, "needs": needs, "documents": {}, "history": [], "version": 1}


def score_need(need: dict[str, Any]) -> float:
    return round(need["reach"] * need["impact"] * need["confidence"] / need["effort"], 2)


def estimate_reach(feedback: list[dict[str, Any]]) -> float:
    return round(min(10, _reach_from_count(len(feedback)) + _reach_from_likes(sum(item["thumbs_up"] for item in feedback))), 2)


def render_template(need: dict[str, Any], feedback: list[dict[str, Any]], context: dict[str, str]) -> str:
    related = [item for item in feedback if item["id"] in need["feedback_ids"]]
    row = {"need_summary": need["title"], "category": need["category"], "module": need["module"],
           "feedback_count": len(related), "priority_score": score_need(need),
           **{f"rice_{key}": need[key] for key in ("reach", "impact", "confidence", "effort")},
           "evidence": "\n".join(f"- [{item['id']}](#evidence-{item['id']})：{item['text']}" for item in related)}
    # Reuse the old generator while supplying the explicit, reviewed evidence set.
    legacy = generate_prd_markdown(row, pd.DataFrame(), use_llm=False)
    context_text = "\n".join(f"- {label}：{context.get(key, '待确认')}" for key, label in [
        ("product", "产品"), ("audience", "目标用户"), ("goal", "业务目标"), ("capabilities", "已有能力"), ("constraints", "约束")])
    return legacy + f"\n\n## 9. 产品背景与约束\n{context_text}\n\n## 10. 事实、建议与待确认\n- 事实：本草稿关联 {len(related)} 条反馈，证据见第 7 节；样本数不代表整体用户规模。\n- 建议：核心方案与验收标准为模板建议，需评审确认。\n- 待确认：真实影响范围、基线指标、开发成本与上线目标值。\n"


def safe_excel(workspace: dict[str, Any]) -> bytes:
    def safe(value: Any) -> Any:
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    sheets = {
        "反馈证据": workspace["feedback"],
        "需求与RICE": [{**need, "feedback_count": len(need["feedback_ids"]), "priority_score": score_need(need)} for need in workspace["needs"]],
        "产品背景": [{"字段": key, "内容": value} for key, value in workspace["context"].items()],
        "修改记录": workspace.get("history", []),
        "PRD文档": [{"need_id": key, **value} for key, value in workspace.get("documents", {}).items()],
    }
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}}) as writer:
        for name, rows in sheets.items():
            frame = pd.DataFrame(rows).map(safe)
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes(1, 0)
            sheet.set_column(0, max(len(frame.columns) - 1, 0), 24)
    return output.getvalue()
