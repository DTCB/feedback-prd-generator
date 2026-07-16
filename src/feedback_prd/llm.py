"""OpenAI-compatible LLM integration with safe template fallback."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - python-dotenv is optional at import time.
    load_dotenv = None


DEFAULT_MODEL = "gpt-4o-mini"


def load_llm_env() -> None:
    """Load local .env values when python-dotenv is available."""

    if load_dotenv is not None:
        load_dotenv()


def get_llm_config() -> dict[str, Any]:
    """Return OpenAI-compatible config without exposing the API key."""

    load_llm_env()
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


def get_llm_status() -> dict[str, Any]:
    """Report LLM readiness for UI display without leaking secrets."""

    config = get_llm_config()
    sdk_available, _client_class = _load_openai_client_class()
    api_key_configured = bool(config["api_key"])

    if not api_key_configured:
        status = "missing_key"
        message = "未配置 LLM_API_KEY / OPENAI_API_KEY，将使用模板兜底。"
    elif not sdk_available:
        status = "missing_sdk"
        message = "已配置 API Key，但未安装 openai 包，将使用模板兜底。"
    else:
        status = "ready"
        message = "已配置 OpenAI 兼容 LLM，开启后将调用真实模型生成 PRD。"

    return {
        "status": status,
        "message": message,
        "api_key_configured": api_key_configured,
        "sdk_available": sdk_available,
        "model": config["model"],
        "base_url_configured": bool(config["base_url"]),
        "base_url": config["base_url"] or "OpenAI default",
    }


def generate_prd_with_llm_metadata(
    need_row: dict[str, Any],
    related_feedback: pd.DataFrame,
    fallback_markdown: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Return PRD markdown plus whether the real LLM was used."""

    config = get_llm_config()
    if model:
        config["model"] = model

    status = get_llm_status()
    if status["status"] != "ready":
        return _fallback_result(fallback_markdown, status["status"], status["message"])

    sdk_available, client_class = _load_openai_client_class()
    if not sdk_available or client_class is None:
        return _fallback_result(fallback_markdown, "missing_sdk", "未安装 openai 包，将使用模板兜底。")

    prompt = _build_prompt(need_row, related_feedback, fallback_markdown)
    client_kwargs = {"api_key": config["api_key"]}
    if config["base_url"]:
        client_kwargs["base_url"] = config["base_url"]

    try:
        client = client_class(**client_kwargs)
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是资深产品经理，请基于用户反馈输出结构化、可执行的中文 PRD Markdown。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if content and content.strip():
            return {
                "markdown": content.strip(),
                "used_llm": True,
                "status": "llm_success",
                "message": f"已使用真实 LLM 生成，模型：{config['model']}。",
                "model": config["model"],
                "base_url": status["base_url"],
            }
        return _fallback_result(fallback_markdown, "empty_response", "LLM 返回为空，已使用模板兜底。")
    except Exception as exc:
        return _fallback_result(
            fallback_markdown,
            "api_error",
            f"LLM 调用失败，已使用模板兜底：{_safe_error_message(exc)}",
        )


def generate_prd_markdown_with_llm(
    need_row: dict[str, Any],
    related_feedback: pd.DataFrame,
    fallback_markdown: str,
    model: str | None = None,
) -> str:
    """Backward-compatible helper that returns markdown only."""

    return generate_prd_with_llm_metadata(
        need_row,
        related_feedback,
        fallback_markdown,
        model=model,
    )["markdown"]


def _fallback_result(markdown: str, status: str, message: str) -> dict[str, Any]:
    return {
        "markdown": markdown,
        "used_llm": False,
        "status": status,
        "message": message,
        "model": get_llm_config()["model"],
        "base_url": get_llm_config()["base_url"] or "OpenAI default",
    }


def _load_openai_client_class() -> tuple[bool, Any]:
    try:
        from openai import OpenAI

        return True, OpenAI
    except Exception:
        return False, None


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    for value in [os.getenv("LLM_API_KEY"), os.getenv("OPENAI_API_KEY")]:
        if value:
            text = text.replace(value, "***")
    return text[:240]


def _build_prompt(need_row: dict[str, Any], related_feedback: pd.DataFrame, fallback_markdown: str) -> str:
    evidence = []
    if not related_feedback.empty and "feedback_text" in related_feedback:
        for text in related_feedback["feedback_text"].dropna().astype(str).head(8):
            evidence.append(f"- {text[:160]}")

    return f"""请优化下面的 PRD 草稿，使其更具体、可验收、适合研发和设计评审。

要求:
- 保留 Markdown 结构。
- 明确用户场景、功能边界、验收标准和指标口径。
- 不要编造不存在的数据，只能基于需求信息和反馈样例合理归纳。
- 输出中文。

需求信息:
{need_row}

原始反馈样例:
{chr(10).join(evidence) if evidence else "- 暂无"}

PRD 草稿:
{fallback_markdown}
"""
