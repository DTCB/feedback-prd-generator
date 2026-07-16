"""Core feedback normalization, rule analysis, need pooling, and PRD drafting."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


CANONICAL_COLUMNS = [
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

ANALYSIS_COLUMNS = [
    "category",
    "sentiment",
    "severity",
    "need_summary",
    "rice_reach",
    "rice_impact",
    "rice_confidence",
    "rice_effort",
    "priority_score",
]

FIELD_ALIASES = {
    "feedback_id": [
        "feedback_id",
        "feedback id",
        "id",
        "uid",
        "反馈id",
        "反馈编号",
        "编号",
        "工单id",
        "工单编号",
        "评论id",
        "留言id",
    ],
    "date": [
        "date",
        "created_at",
        "created at",
        "create_time",
        "created time",
        "time",
        "timestamp",
        "提交时间",
        "创建时间",
        "反馈时间",
        "评论时间",
        "日期",
        "时间",
    ],
    "source": [
        "source",
        "platform",
        "来源",
        "数据来源",
        "平台",
        "渠道来源",
    ],
    "app_name": [
        "app_name",
        "app name",
        "app",
        "product",
        "product_name",
        "产品",
        "产品名称",
        "应用",
        "应用名称",
        "小程序",
    ],
    "channel": [
        "channel",
        "entry",
        "入口",
        "渠道",
        "反馈渠道",
        "触点",
        "场景",
        "页面来源",
    ],
    "rating": [
        "rating",
        "score",
        "stars",
        "star",
        "nps",
        "csat",
        "评分",
        "星级",
        "满意度",
        "打分",
        "分数",
    ],
    "version": [
        "version",
        "app_version",
        "app version",
        "build",
        "版本",
        "应用版本",
        "客户端版本",
        "系统版本",
    ],
    "user_type": [
        "user_type",
        "user type",
        "segment",
        "persona",
        "role",
        "用户类型",
        "用户分层",
        "用户身份",
        "角色",
        "会员类型",
    ],
    "module": [
        "module",
        "feature",
        "function",
        "功能模块",
        "模块",
        "功能",
        "业务线",
        "问题模块",
        "页面",
    ],
    "feedback_text": [
        "feedback_text",
        "feedback text",
        "feedback",
        "content",
        "text",
        "comment",
        "review",
        "description",
        "message",
        "issue",
        "body",
        "反馈内容",
        "反馈",
        "内容",
        "评论",
        "评价",
        "用户反馈",
        "问题描述",
        "描述",
        "留言",
        "建议",
        "需求描述",
    ],
    "thumbs_up": [
        "thumbs_up",
        "thumbs up",
        "likes",
        "like_count",
        "upvotes",
        "votes",
        "helpful",
        "agree_count",
        "点赞",
        "点赞数",
        "赞同数",
        "有用数",
        "支持数",
        "投票数",
    ],
}

CATEGORY_KEYWORDS = {
    "Bug": [
        "bug",
        "crash",
        "error",
        "exception",
        "fail",
        "failed",
        "broken",
        "blank screen",
        "cannot",
        "can't",
        "unable",
        "卡死",
        "崩溃",
        "闪退",
        "报错",
        "错误",
        "异常",
        "失败",
        "失效",
        "无响应",
        "白屏",
        "黑屏",
        "加载不出",
        "打不开",
        "无法",
        "不能",
        "登录不上",
    ],
    "功能需求": [
        "feature",
        "request",
        "add",
        "support",
        "need",
        "would like",
        "希望",
        "建议",
        "增加",
        "新增",
        "支持",
        "能不能",
        "可不可以",
        "想要",
        "需要",
        "需求",
        "最好",
        "希望能",
    ],
    "体验问题": [
        "slow",
        "lag",
        "confusing",
        "hard to use",
        "ux",
        "ui",
        "卡顿",
        "很慢",
        "太慢",
        "难用",
        "不好用",
        "不方便",
        "找不到",
        "复杂",
        "麻烦",
        "体验",
        "交互",
        "页面",
        "流程",
        "布局",
        "看不懂",
        "不清楚",
    ],
    "内容质量问题": [
        "content",
        "typo",
        "translation",
        "inaccurate",
        "wrong answer",
        "内容",
        "质量",
        "错别字",
        "翻译",
        "文案",
        "不准确",
        "错误答案",
        "推荐不准",
        "资料",
        "数据不对",
        "图片",
        "视频",
        "审核",
        "重复",
    ],
    "咨询/付费问题": [
        "payment",
        "pricing",
        "price",
        "refund",
        "invoice",
        "subscription",
        "subscribe",
        "billing",
        "account",
        "付费",
        "会员",
        "价格",
        "退款",
        "发票",
        "订阅",
        "支付",
        "充值",
        "扣费",
        "账单",
        "账户",
        "账号",
        "咨询",
        "怎么",
        "如何",
        "是否",
        "客服",
    ],
}

MODULE_KEYWORDS = [
    ("登录/账号", ["登录", "注册", "账号", "账户", "密码", "验证码", "login", "account"]),
    ("付费/会员", ["付费", "会员", "订阅", "支付", "充值", "退款", "发票", "价格", "payment", "billing"]),
    ("上传/导入", ["上传", "导入", "文件", "表格", "excel", "csv", "upload", "import"]),
    ("导出/下载", ["导出", "下载", "分享", "download", "export", "share"]),
    ("搜索/筛选", ["搜索", "筛选", "过滤", "排序", "search", "filter", "sort"]),
    ("分析/生成", ["分析", "总结", "生成", "prd", "ai", "模型", "analysis", "generate"]),
    ("内容/推荐", ["内容", "文案", "推荐", "资料", "图片", "视频", "content", "recommend"]),
    ("通知/消息", ["通知", "消息", "提醒", "推送", "notification", "message"]),
    ("性能/稳定性", ["卡顿", "慢", "崩溃", "闪退", "白屏", "性能", "slow", "crash"]),
    ("页面/交互", ["页面", "按钮", "入口", "交互", "布局", "ui", "ux", "button"]),
    ("权限/安全", ["权限", "隐私", "安全", "permission", "privacy", "security"]),
]

SENTIMENT_NEGATIVE = [
    "差",
    "糟",
    "烂",
    "垃圾",
    "失望",
    "生气",
    "崩溃",
    "卡死",
    "报错",
    "无法",
    "不能",
    "失败",
    "难用",
    "慢",
    "麻烦",
    "不好",
    "不准",
    "不对",
    "refund",
    "bad",
    "poor",
    "angry",
    "terrible",
    "broken",
    "fail",
]

SENTIMENT_POSITIVE = [
    "好用",
    "不错",
    "喜欢",
    "满意",
    "感谢",
    "赞",
    "稳定",
    "流畅",
    "great",
    "good",
    "nice",
    "love",
    "thanks",
]


def load_feedback_file(uploaded_file_or_path: Any) -> pd.DataFrame:
    """Load a CSV/Excel/JSON feedback file and return standardized columns."""

    name = _get_file_name(uploaded_file_or_path)
    suffix = Path(name).suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(uploaded_file_or_path)
    elif suffix == ".json":
        df = pd.read_json(uploaded_file_or_path)
    elif suffix in {".csv", ".txt", ""}:
        df = _read_csv_with_fallback(uploaded_file_or_path)
    else:
        raise ValueError(f"Unsupported feedback file type: {suffix or 'unknown'}")

    return standardize_feedback(df)


def standardize_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """Map common upload field names to the canonical feedback schema."""

    if not isinstance(df, pd.DataFrame):
        raise TypeError("standardize_feedback expects a pandas DataFrame")

    source_df = df.copy()
    normalized_to_originals: dict[str, list[str]] = {}
    for column in source_df.columns:
        normalized_to_originals.setdefault(_normalize_column_name(column), []).append(column)

    output = pd.DataFrame(index=source_df.index)
    consumed_columns: set[str] = set()

    for canonical in CANONICAL_COLUMNS:
        matches = []
        for alias in [canonical, *FIELD_ALIASES[canonical]]:
            matches.extend(normalized_to_originals.get(_normalize_column_name(alias), []))
        matches = _dedupe(matches)

        if matches:
            output[canonical] = _coalesce_columns(source_df, matches)
            consumed_columns.update(matches)
        else:
            output[canonical] = pd.NA

    if output["feedback_text"].isna().all():
        text_candidate = _find_text_candidate(source_df, consumed_columns)
        if text_candidate is not None:
            output["feedback_text"] = source_df[text_candidate]
            consumed_columns.add(text_candidate)

    output["feedback_id"] = _clean_text_series(output["feedback_id"])
    missing_id = output["feedback_id"].isna() | (output["feedback_id"] == "")
    output.loc[missing_id, "feedback_id"] = [
        f"fb_{position:06d}" for position, is_missing in enumerate(missing_id.tolist(), start=1) if is_missing
    ]

    output["date"] = pd.to_datetime(output["date"], errors="coerce")
    output["rating"] = pd.to_numeric(output["rating"], errors="coerce")
    output["thumbs_up"] = pd.to_numeric(output["thumbs_up"], errors="coerce").fillna(0).clip(lower=0)

    for column in ["source", "app_name", "channel", "version", "user_type", "module", "feedback_text"]:
        output[column] = _clean_text_series(output[column])

    extra_columns = [column for column in source_df.columns if column not in consumed_columns]
    return pd.concat([output[CANONICAL_COLUMNS], source_df[extra_columns]], axis=1)


def analyze_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """Apply deterministic rule classification and row-level RICE scoring."""

    standardized = standardize_feedback(df)
    records = []

    for _, row in standardized.iterrows():
        text = str(row.get("feedback_text") or "")
        module = _module_for_row(row)
        category, category_strength = _classify_category(text)
        sentiment = _classify_sentiment(text, row.get("rating"), category)
        severity = _classify_severity(text, row.get("rating"), category, sentiment)
        need_summary = _build_need_summary(category, module, text)
        impact = _estimate_impact(category, severity)
        effort = _estimate_effort(category, module, text)
        confidence = _estimate_confidence(text, category_strength, row.get("rating"))

        record = row.to_dict()
        record.update(
            {
                "category": category,
                "sentiment": sentiment,
                "severity": severity,
                "need_summary": need_summary,
                "_analysis_module": module,
                "_category_strength": category_strength,
                "_rice_impact_base": impact,
                "_rice_effort_base": effort,
                "_rice_confidence_base": confidence,
            }
        )
        records.append(record)

    analyzed = pd.DataFrame(records)
    if analyzed.empty:
        analyzed = standardized.copy()
        for column in ANALYSIS_COLUMNS:
            analyzed[column] = pd.Series(dtype="object")
        return analyzed[CANONICAL_COLUMNS + ANALYSIS_COLUMNS]

    grouped = analyzed.groupby("need_summary", dropna=False)
    group_count = grouped["feedback_id"].transform("count")
    group_likes = grouped["thumbs_up"].transform("sum").fillna(0)
    reach = group_count.map(_reach_from_count) + group_likes.map(_reach_from_likes)
    analyzed["rice_reach"] = reach.clip(lower=1, upper=10).round(2)

    analyzed["rice_impact"] = analyzed["_rice_impact_base"].round(2)
    analyzed["rice_confidence"] = (
        analyzed["_rice_confidence_base"] + group_count.map(lambda count: min(0.2, max(0, count - 1) * 0.04))
    ).clip(lower=0.35, upper=0.95).round(2)
    analyzed["rice_effort"] = analyzed["_rice_effort_base"].round(2)
    analyzed["priority_score"] = (
        analyzed["rice_reach"] * analyzed["rice_impact"] * analyzed["rice_confidence"] / analyzed["rice_effort"]
    ).round(2)

    helper_columns = [column for column in analyzed.columns if column.startswith("_")]
    ordered = [column for column in CANONICAL_COLUMNS if column in analyzed.columns]
    ordered += [column for column in analyzed.columns if column not in ordered + ANALYSIS_COLUMNS + helper_columns]
    ordered += ANALYSIS_COLUMNS
    return analyzed[ordered]


def build_need_pool(analyzed_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate analyzed feedback into stable product need rows."""

    if analyzed_df.empty:
        return pd.DataFrame(
            columns=[
                "need_id",
                "need_summary",
                "category",
                "sentiment",
                "severity",
                "module",
                "feedback_count",
                "source_count",
                "avg_rating",
                "rice_reach",
                "rice_impact",
                "rice_confidence",
                "rice_effort",
                "priority_score",
                "evidence",
            ]
        )

    analyzed = analyze_feedback(analyzed_df) if not _has_columns(analyzed_df, ANALYSIS_COLUMNS) else analyzed_df.copy()
    analyzed["module"] = analyzed.apply(_module_for_row, axis=1)

    groups = []
    for index, ((category, module, need_summary), group) in enumerate(
        analyzed.groupby(["category", "module", "need_summary"], dropna=False), start=1
    ):
        feedback_count = int(len(group))
        source_count = int(group["source"].replace("", pd.NA).dropna().nunique()) if "source" in group else 0
        thumbs_sum = float(pd.to_numeric(group.get("thumbs_up", 0), errors="coerce").fillna(0).sum())
        reach = min(10.0, _reach_from_count(feedback_count) + _reach_from_likes(thumbs_sum))
        impact = float(group["rice_impact"].max())
        confidence = min(
            0.95,
            float(group["rice_confidence"].mean()) + min(0.12, max(0, feedback_count - 1) * 0.02),
        )
        effort = max(0.5, float(group["rice_effort"].median()))
        priority_score = round(reach * impact * confidence / effort, 2)

        groups.append(
            {
                "need_id": f"need_{index:03d}",
                "need_summary": need_summary,
                "category": category,
                "sentiment": _mode_or_default(group["sentiment"], "neutral"),
                "severity": _max_severity(group["severity"]),
                "module": module,
                "feedback_count": feedback_count,
                "source_count": source_count,
                "avg_rating": _safe_round(pd.to_numeric(group["rating"], errors="coerce").mean(), 2),
                "rice_reach": round(reach, 2),
                "rice_impact": round(impact, 2),
                "rice_confidence": round(confidence, 2),
                "rice_effort": round(effort, 2),
                "priority_score": priority_score,
                "evidence": _sample_evidence(group),
            }
        )

    return pd.DataFrame(groups).sort_values(
        ["priority_score", "feedback_count"], ascending=[False, False]
    ).reset_index(drop=True)


def generate_prd_markdown(
    need_row: pd.Series | dict[str, Any],
    analyzed_df: pd.DataFrame,
    use_llm: bool = False,
) -> str:
    """Generate a PRD markdown draft for one need, with optional LLM enhancement."""

    return generate_prd_with_metadata(need_row, analyzed_df, use_llm=use_llm)["markdown"]


def generate_prd_with_metadata(
    need_row: pd.Series | dict[str, Any],
    analyzed_df: pd.DataFrame,
    use_llm: bool = False,
) -> dict[str, Any]:
    """Generate a PRD markdown draft and return generation metadata."""

    row = need_row.to_dict() if isinstance(need_row, pd.Series) else dict(need_row)
    related = _related_feedback(row, analyzed_df)
    template = _render_prd_template(row, related)

    if not use_llm:
        return {
            "markdown": template,
            "used_llm": False,
            "status": "template",
            "message": "未开启 LLM，当前使用规则模板生成 PRD。",
        }

    try:
        from .llm import generate_prd_with_llm_metadata

        return generate_prd_with_llm_metadata(row, related, fallback_markdown=template)
    except Exception:
        return {
            "markdown": template,
            "used_llm": False,
            "status": "llm_wrapper_error",
            "message": "LLM 封装加载失败，已使用模板兜底。",
        }


def _get_file_name(file_or_path: Any) -> str:
    if isinstance(file_or_path, (str, Path)):
        return str(file_or_path)
    return getattr(file_or_path, "name", "")


def _read_csv_with_fallback(file_or_path: Any) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            if hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            return pd.read_csv(file_or_path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(file_or_path)


def _normalize_column_name(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[\s_\-./\\()（）【】\[\]:：]+", "", text)


def _dedupe(values: Iterable[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _coalesce_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=df.index)
    for column in columns:
        candidate = df[column]
        result = result.where(_is_present(result), candidate)
    return result


def _is_present(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "")


def _clean_text_series(series: pd.Series) -> pd.Series:
    return series.where(series.notna(), "").astype(str).str.strip().replace({"nan": "", "NaT": "", "<NA>": ""})


def _find_text_candidate(df: pd.DataFrame, consumed_columns: set[str]) -> str | None:
    candidates = []
    for column in df.columns:
        if column in consumed_columns:
            continue
        as_text = _clean_text_series(df[column])
        avg_len = as_text.str.len().mean()
        candidates.append((avg_len, column))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates and candidates[0][0] >= 8 else None


def _has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    return all(column in df.columns for column in columns)


def _classify_category(text: str) -> tuple[str, int]:
    normalized = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for keyword in keywords if keyword.lower() in normalized)

    if not any(scores.values()):
        return "体验问题", 0

    priority_order = ["Bug", "咨询/付费问题", "功能需求", "体验问题", "内容质量问题"]
    best = max(priority_order, key=lambda category: (scores[category], -priority_order.index(category)))
    return best, scores[best]


def _classify_sentiment(text: str, rating: Any, category: str) -> str:
    rating_value = _to_float(rating)
    if rating_value is not None:
        if rating_value <= 2:
            return "negative"
        if rating_value >= 4 and category not in {"Bug", "体验问题"}:
            return "positive"

    normalized = text.lower()
    negative = sum(1 for keyword in SENTIMENT_NEGATIVE if keyword.lower() in normalized)
    positive = sum(1 for keyword in SENTIMENT_POSITIVE if keyword.lower() in normalized)

    if negative > positive:
        return "negative"
    if positive > negative and category not in {"Bug", "体验问题"}:
        return "positive"
    if category in {"Bug", "体验问题", "内容质量问题"}:
        return "negative"
    return "neutral"


def _classify_severity(text: str, rating: Any, category: str, sentiment: str) -> str:
    normalized = text.lower()
    rating_value = _to_float(rating)
    critical_terms = ["崩溃", "闪退", "数据丢失", "无法登录", "支付失败", "扣费", "crash", "data loss"]
    high_terms = ["无法", "不能", "失败", "打不开", "白屏", "黑屏", "卡死", "broken", "cannot", "unable"]

    if category == "Bug" and any(term in normalized for term in critical_terms):
        return "Critical"
    if category == "Bug" and (any(term in normalized for term in high_terms) or rating_value is not None and rating_value <= 1):
        return "High"
    if category == "咨询/付费问题" and any(term in normalized for term in ["扣费", "支付失败", "退款", "发票", "billing", "refund"]):
        return "High"
    if category in {"Bug", "体验问题", "内容质量问题"} and sentiment == "negative":
        return "Medium"
    if category == "功能需求":
        return "Medium"
    return "Low"


def _module_for_row(row: pd.Series | dict[str, Any]) -> str:
    explicit_module = str(row.get("module") or "").strip()
    if explicit_module:
        return explicit_module

    text = str(row.get("feedback_text") or "").lower()
    for module, keywords in MODULE_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return module
    return "其他"


def _build_need_summary(category: str, module: str, text: str) -> str:
    topic = _topic_from_text(text)
    if category == "Bug":
        return f"修复{module}{topic}异常"
    if category == "功能需求":
        return f"新增或完善{module}{topic}能力"
    if category == "体验问题":
        return f"优化{module}{topic}体验"
    if category == "内容质量问题":
        return f"提升{module}{topic}内容质量"
    return f"完善{module}{topic}咨询与付费支持"


def _topic_from_text(text: str) -> str:
    normalized = text.lower()
    topic_keywords = [
        ("登录", ["登录", "注册", "验证码", "密码", "login"]),
        ("支付", ["支付", "扣费", "退款", "发票", "订阅", "payment", "refund"]),
        ("上传", ["上传", "导入", "文件", "excel", "csv", "upload"]),
        ("导出", ["导出", "下载", "download", "export"]),
        ("搜索", ["搜索", "筛选", "排序", "search", "filter"]),
        ("生成", ["生成", "总结", "分析", "prd", "generate"]),
        ("页面", ["页面", "按钮", "入口", "布局", "ui"]),
        ("性能", ["卡顿", "慢", "加载", "性能", "slow"]),
        ("内容", ["内容", "文案", "翻译", "推荐", "资料", "content"]),
    ]
    for topic, keywords in topic_keywords:
        if any(keyword.lower() in normalized for keyword in keywords):
            return topic
    return "相关"


def _estimate_impact(category: str, severity: str) -> float:
    severity_impact = {"Critical": 5.0, "High": 4.0, "Medium": 3.0, "Low": 2.0}
    category_bonus = {
        "Bug": 0.4,
        "功能需求": 0.1,
        "体验问题": 0.0,
        "内容质量问题": -0.1,
        "咨询/付费问题": 0.2,
    }
    return min(5.0, max(1.0, severity_impact.get(severity, 2.0) + category_bonus.get(category, 0)))


def _estimate_effort(category: str, module: str, text: str) -> float:
    base = {
        "Bug": 2.0,
        "功能需求": 4.0,
        "体验问题": 3.0,
        "内容质量问题": 1.5,
        "咨询/付费问题": 2.0,
    }.get(category, 3.0)

    normalized = text.lower()
    if any(term in normalized for term in ["新增", "支持", "打通", "自动", "ai", "模型", "权限"]):
        base += 1.5
    if module in {"页面/交互", "内容/推荐", "其他"}:
        base += 0.5
    if any(term in normalized for term in ["文案", "错别字", "发票", "说明", "提示"]):
        base -= 0.5
    return round(min(8.0, max(0.5, base)), 2)


def _estimate_confidence(text: str, category_strength: int, rating: Any) -> float:
    text_length = len(text.strip())
    confidence = 0.45
    confidence += min(0.2, category_strength * 0.06)
    if text_length >= 12:
        confidence += 0.08
    if text_length >= 40:
        confidence += 0.08
    if _to_float(rating) is not None:
        confidence += 0.06
    return min(0.9, max(0.35, confidence))


def _reach_from_count(count: Any) -> float:
    count_value = max(1.0, float(count or 1))
    return min(8.0, 1.5 + math.log2(count_value + 1) * 1.8)


def _reach_from_likes(likes: Any) -> float:
    likes_value = max(0.0, float(likes or 0))
    if likes_value <= 0:
        return 0.0
    return min(2.0, math.log2(likes_value + 1) * 0.45)


def _mode_or_default(series: pd.Series, default: str) -> str:
    values = series.dropna()
    return str(values.mode().iloc[0]) if not values.empty else default


def _max_severity(series: pd.Series) -> str:
    order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    values = [str(value) for value in series.dropna()]
    return max(values, key=lambda value: order.get(value, 0)) if values else "Low"


def _sample_evidence(group: pd.DataFrame, limit: int = 3) -> str:
    samples = []
    sorted_group = group.sort_values("priority_score", ascending=False) if "priority_score" in group else group
    for text in sorted_group["feedback_text"].dropna().astype(str):
        cleaned = re.sub(r"\s+", " ", text).strip()
        if cleaned and cleaned not in samples:
            samples.append(cleaned[:120])
        if len(samples) >= limit:
            break
    return "\n".join(f"- {sample}" for sample in samples)


def _related_feedback(row: dict[str, Any], analyzed_df: pd.DataFrame) -> pd.DataFrame:
    if analyzed_df.empty:
        return analyzed_df

    analyzed = analyze_feedback(analyzed_df) if not _has_columns(analyzed_df, ANALYSIS_COLUMNS) else analyzed_df.copy()
    need_summary = row.get("need_summary")
    category = row.get("category")
    module = row.get("module")

    mask = pd.Series(True, index=analyzed.index)
    if need_summary:
        mask &= analyzed["need_summary"] == need_summary
    if category:
        mask &= analyzed["category"] == category
    if module and "module" in analyzed.columns:
        mask &= analyzed.apply(_module_for_row, axis=1) == module
    return analyzed.loc[mask].copy()


def _render_prd_template(row: dict[str, Any], related: pd.DataFrame) -> str:
    title = str(row.get("need_summary") or "用户反馈需求")
    category = str(row.get("category") or "未分类")
    module = str(row.get("module") or "其他")
    severity = str(row.get("severity") or "Medium")
    feedback_count = int(row.get("feedback_count") or len(related) or 0)
    priority_score = row.get("priority_score", "")

    evidence = row.get("evidence") or _sample_evidence(related)
    success_metric = _success_metric(category)

    return f"""# PRD: {title}

## 1. 背景与问题
- 需求来源: 用户反馈分析
- 所属模块: {module}
- 问题类型: {category}
- 严重程度: {severity}
- 反馈量: {feedback_count}
- 优先级分: {priority_score}

## 2. 用户问题
用户在「{module}」相关场景中集中反馈: {title}。该问题会影响满意度、任务完成效率或付费转化，需要结合反馈证据进一步确认方案边界。

## 3. 目标
- 降低同类负向反馈数量。
- 提升相关流程的完成率和可理解性。
- 在不显著增加使用成本的前提下解决核心用户诉求。

## 4. 范围
- In Scope: 针对「{title}」的产品、交互、内容或系统修复。
- Out of Scope: 与该需求无直接关系的全局重构、商业策略大改、非核心路径改版。

## 5. 核心方案
1. 梳理触发场景和用户路径，定位主要失败点或缺口。
2. 设计最小可验证方案，优先覆盖高频反馈场景。
3. 增加必要的提示、状态、校验或配置能力。
4. 上线后通过反馈回流和关键指标验证效果。

## 6. 验收标准
- 用户可以在目标场景中顺利完成关键任务。
- 异常、疑问或低质反馈有明确提示或处理路径。
- 新方案不破坏现有主流程。
- 关键指标达到预期: {success_metric}

## 7. 反馈证据
{evidence or "- 暂无可展示的原始反馈样例"}

## 8. RICE
- Reach: {row.get("rice_reach", "")}
- Impact: {row.get("rice_impact", "")}
- Confidence: {row.get("rice_confidence", "")}
- Effort: {row.get("rice_effort", "")}
- Priority Score: {priority_score}
"""


def _success_metric(category: str) -> str:
    if category == "Bug":
        return "同类错误率下降，相关工单/反馈量下降。"
    if category == "功能需求":
        return "目标功能使用率提升，相关需求反馈下降。"
    if category == "体验问题":
        return "流程完成率提升，平均操作时长下降。"
    if category == "内容质量问题":
        return "内容纠错反馈下降，内容满意度提升。"
    return "付费/咨询转化路径完成率提升，相关咨询量下降。"


def _to_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_round(value: Any, digits: int) -> float | None:
    value = _to_float(value)
    return round(value, digits) if value is not None else None
