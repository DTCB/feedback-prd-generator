"""HTTP API for the portfolio demo; the browser owns the working session."""
from __future__ import annotations

import json
import os
import zipfile
from io import BytesIO
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from . import quota, web_ai
from .workspace import build_workspace, estimate_reach, render_template, safe_excel

app = FastAPI(title="Feedback Lens API", docs_url=None, redoc_url=None, openapi_url=None)


class Model(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, str_max_length=16000)


class Context(Model):
    product: str = Field(default="AI 助手", max_length=1500)
    audience: str = Field(default="待确认", max_length=1500)
    goal: str = Field(default="待确认", max_length=1500)
    capabilities: str = Field(default="待确认", max_length=1500)
    constraints: str = Field(default="待确认", max_length=1500)


class Feedback(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    text: str = Field(min_length=1, max_length=12000)
    date: str = Field(default="", max_length=32)
    source: str = Field(default="手动导入", max_length=120)
    app_name: str = Field(default="未指定", max_length=120)
    rating: float | None = Field(default=None, ge=0, le=5)
    user_type: str = Field(default="未标注", max_length=100)
    module: str = Field(default="其他", max_length=120)
    thumbs_up: float = Field(default=0, ge=0, le=100000000)
    category: Literal["Bug", "功能需求", "体验问题", "内容质量问题", "咨询/付费问题"]
    sentiment: Literal["positive", "negative", "neutral"]
    severity: Literal["Low", "Medium", "High", "Critical"]
    need_id: str = Field(max_length=80)
    reviewed: bool = False
    origin: Literal["rule", "sample", "llm"] = "rule"
    quote: str = Field(default="", max_length=12000)
    scenario: str = Field(default="", max_length=1500)
    problem: str = Field(default="", max_length=12000)
    request: str = Field(default="", max_length=1500)
    reason: str = Field(default="", max_length=1500)


class Need(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=600)
    description: str = Field(default="", max_length=3000)
    category: str = Field(max_length=80)
    module: str = Field(max_length=120)
    feedback_ids: list[str] = Field(max_length=500)
    reach: float = Field(ge=0, le=1000000)
    impact: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    effort: float = Field(ge=0.1, le=10000)
    status: Literal["pending", "confirmed", "deferred"] = "pending"
    origin: Literal["rule", "sample", "llm"] = "rule"
    score_reason: str = Field(default="", max_length=1500)


class Document(Model):
    markdown: str = Field(max_length=40000)
    origin: Literal["template", "llm", "sample"] = "template"
    edited: bool = False
    stale: bool = False
    updated_at: str = Field(default="", max_length=50)


class Workspace(Model):
    feedback: list[Feedback] = Field(min_length=1, max_length=500)
    needs: list[Need] = Field(min_length=1, max_length=500)
    context: Context
    documents: dict[str, Document] = Field(default_factory=dict, max_length=500)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    is_sample: bool = False
    version: int = 1
    cleaning: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_links(self):
        feedback_ids = [item.id for item in self.feedback]
        need_ids = [item.id for item in self.needs]
        if len(feedback_ids) != len(set(feedback_ids)) or len(need_ids) != len(set(need_ids)):
            raise ValueError("反馈与需求 ID 必须唯一。")
        if any(item.need_id not in need_ids for item in self.feedback):
            raise ValueError("反馈关联了不存在的需求。")
        for need in self.needs:
            actual = {item.id for item in self.feedback if item.need_id == need.id}
            if set(need.feedback_ids) != actual or len(need.feedback_ids) != len(actual):
                raise ValueError("需求证据列表与反馈关联不一致。")
        for item in self.feedback:
            if item.quote and item.quote not in item.text:
                raise ValueError("引用片段必须存在于原文中。")
        if any(key not in need_ids for key in self.documents):
            raise ValueError("文档关联了不存在的需求。")
        return self


class AnalyzeRequest(Model):
    workspace: Workspace
    mode: Literal["rule", "llm"] = "rule"
    selected_ids: list[str] = Field(default_factory=list, max_length=30)


class PrdRequest(Model):
    workspace: Workspace
    need_id: str = Field(max_length=80)
    use_llm: bool = False
    action: Literal["generate", "revise"] = "generate"
    draft: str = Field(default="", max_length=16000)
    instruction: str = Field(default="", max_length=600)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method == "POST":
        maximum = 2 * 1024 * 1024 + 65536 if "multipart/form-data" in request.headers.get("content-type", "") else 8 * 1024 * 1024
        total, chunks = 0, []
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                return JSONResponse({"detail": "请求过大，文件上限为 2MB，工作区请求上限为 8MB。"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request, _exception):
    # Default validation output echoes request content; never echo private text.
    return JSONResponse({"detail": "数据格式或关联关系不正确，请检查输入或重置案例后重试。"}, status_code=422)


@app.exception_handler(quota.QuotaError)
async def quota_error(_request, exception):
    return JSONResponse({"detail": exception.message}, status_code=exception.status)


@app.get("/api/status")
def status():
    ready, message = web_ai.readiness()
    return {"ai_available": ready, "message": message, "limits": {"daily": 3, "monthly": 200, "max_feedback": 30, "max_characters": 12000}}


@app.post("/api/import")
async def import_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(400, "仅支持 CSV 或 XLSX 文件。")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 2MB。")
    try:
        if filename.lower().endswith(".xlsx"):
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if len(archive.infolist()) > 2000 or sum(item.file_size for item in archive.infolist()) > 32 * 1024 * 1024:
                    raise ValueError("表格解压后过大，请简化文件。")
            frame = pd.read_excel(BytesIO(content), nrows=501)
        else:
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    frame = pd.read_csv(BytesIO(content), encoding=encoding, nrows=501)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("CSV 编码无法识别，请另存为 UTF-8 后重试。")
        if len(frame.columns) > 100:
            raise ValueError("表格最多支持 100 列。")
        result = build_workspace(frame)
        Workspace.model_validate(result)
        return result
    except ValidationError:
        raise HTTPException(400, "表格字段过长或格式不正确，请检查来源、产品名称与日期字段。") from None
    except ValueError as exception:
        raise HTTPException(400, str(exception)[:180]) from None
    except Exception:
        raise HTTPException(400, "文件解析失败，请检查表格格式和反馈内容列。") from None


def raw_frame(workspace: Workspace) -> pd.DataFrame:
    return pd.DataFrame([{"feedback_id": item.id, "feedback_text": item.text, "date": item.date,
        "source": item.source, "app_name": item.app_name, "rating": item.rating,
        "module": item.module, "thumbs_up": item.thumbs_up, "user_type": item.user_type} for item in workspace.feedback])


def reserve_call(request: Request):
    ready, message = web_ai.readiness()
    if not ready:
        raise HTTPException(503, message)
    # Vercel replaces X-Forwarded-For at the trusted edge. Do not trust it locally.
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() if os.getenv("VERCEL") else "") or (request.client.host if request.client else "unknown")
    quota.reserve(ip)


@app.post("/api/analyze")
def analyze(request: Request, body: AnalyzeRequest):
    if body.mode == "rule":
        result = build_workspace(raw_frame(body.workspace))
        result["context"] = body.workspace.context.model_dump()
        return {"workspace": result, "used_llm": False, "message": "规则分析完成，结果尚需人工确认。"}
    selected = set(body.selected_ids)
    items = [item for item in body.workspace.feedback if item.id in selected]
    if not selected or len(items) != len(selected):
        raise HTTPException(400, "请选择 1–30 条有效反馈。")
    if sum(len(item.text) for item in items) > 12000:
        raise HTTPException(400, "实时分析的文本总长不能超过 12,000 字，请减少选择。")
    reserve_call(request)
    try:
        from .analysis import analyze_feedback
        analyzed = analyze_feedback(raw_frame(body.workspace).loc[lambda frame: frame.feedback_id.isin(selected)])
        records = json.loads(analyzed.to_json(orient="records", date_format="iso", force_ascii=False))
        patch, usage = web_ai.analyze(records, body.workspace.context.model_dump())
        result = body.workspace.model_dump()
        existing = {need["id"]: need for need in result["needs"]}
        for suggestion in patch["needs"]:
            old_id = suggestion["id"]
            same_title = next((need for need in result["needs"] if need["title"] == suggestion["title"]), None)
            if same_title:
                suggestion["id"] = same_title["id"]
            else:
                while suggestion["id"] in existing:
                    suggestion["id"] += "-ai"
            if old_id != suggestion["id"]:
                for item in patch["feedback"]:
                    if item["need_id"] == old_id:
                        item["need_id"] = suggestion["id"]
            if suggestion["id"] in existing:
                previous = existing[suggestion["id"]]
                for field in ("reach", "impact", "confidence", "effort", "score_reason"):
                    suggestion[field] = previous[field]
        result["feedback"] = [item for item in result["feedback"] if item["id"] not in selected] + patch["feedback"]
        by_id = {}
        for need in [*result["needs"], *patch["needs"]]:
            by_id[need["id"]] = need
        result["needs"] = []
        for identity, need in by_id.items():
            actual = [item["id"] for item in result["feedback"] if item["need_id"] == identity]
            if actual:
                previous = existing.get(identity)
                if previous is not None and set(actual) != set(previous["feedback_ids"]):
                    need["reach"] = estimate_reach([item for item in result["feedback"] if item["id"] in actual])
                    need["status"] = "pending"
                result["needs"].append({**need, "feedback_ids": actual})
        result["documents"] = {key: {**doc, "stale": True} for key, doc in result["documents"].items() if key in by_id and any(need["id"] == key for need in result["needs"])}
        Workspace.model_validate(result)
        return {"workspace": result, "used_llm": True, "usage": usage, "message": "真实 AI 分析完成；请预览后决定是否应用。"}
    except ValueError as exception:
        raise HTTPException(502, str(exception)[:180]) from None
    except Exception:
        raise HTTPException(502, "模型服务暂时无法完成分析，工作内容未改变。可稍后重试或继续人工校准。") from None


@app.post("/api/prd")
def prd(request: Request, body: PrdRequest):
    workspace = body.workspace.model_dump()
    need = next((item for item in workspace["needs"] if item["id"] == body.need_id), None)
    if need is None:
        raise HTTPException(404, "未找到该需求。")
    related = [item for item in workspace["feedback"] if item["id"] in need["feedback_ids"]]
    if not related:
        raise HTTPException(400, "该需求没有关联证据，请先关联反馈。")
    template = render_template(need, workspace["feedback"], workspace["context"])
    if not body.use_llm:
        return {"markdown": template, "origin": "template", "used_llm": False, "message": "已使用当前证据和评分生成模板草稿。"}
    if len(related) > 30 or sum(len(item["text"]) for item in related) > 12000:
        raise HTTPException(400, "实时生成最多使用 30 条、12,000 字关联反馈，请先缩小需求范围。")
    if body.action == "revise" and (not body.draft.strip() or not body.instruction.strip()):
        raise HTTPException(400, "请提供需要修改的章节和修改要求。")
    reserve_call(request)
    try:
        content, usage = web_ai.generate_prd(need, related, workspace["context"], body.draft or template,
            body.instruction if body.action == "revise" else "")
        return {"markdown": content, "origin": "llm", "used_llm": True, "usage": usage, "message": "真实 AI 草稿已生成，接受后才会替换当前内容。"}
    except ValueError as exception:
        raise HTTPException(502, str(exception)[:180]) from None
    except Exception:
        raise HTTPException(502, "模型服务暂不可用，当前文档已保留。你可以使用模板生成或稍后重试。") from None


@app.post("/api/export")
def export(workspace: Workspace):
    data = safe_excel(workspace.model_dump())
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="feedback-lens.xlsx"'})
