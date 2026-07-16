from io import BytesIO
from pathlib import Path

import pandas as pd

from src.feedback_prd.analysis import (
    analyze_feedback,
    build_need_pool,
    generate_prd_markdown,
    load_feedback_file,
    standardize_feedback,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sample_feedback_pipeline_generates_need_pool_and_prd():
    feedback = load_feedback_file(ROOT / "data" / "sample_feedback.csv")
    assert len(feedback) >= 60
    assert {"feedback_id", "feedback_text", "rating"}.issubset(feedback.columns)

    analyzed = analyze_feedback(feedback)
    assert {"category", "severity", "priority_score"}.issubset(analyzed.columns)
    assert {"Bug", "功能需求", "体验问题", "内容质量问题", "咨询/付费问题"}.issubset(
        set(analyzed["category"])
    )

    need_pool = build_need_pool(analyzed)
    assert not need_pool.empty
    assert need_pool.iloc[0]["priority_score"] >= need_pool.iloc[-1]["priority_score"]

    prd = generate_prd_markdown(need_pool.iloc[0], analyzed)
    assert "# PRD:" in prd
    assert "验收标准" in prd


def test_upload_field_aliases_are_standardized():
    uploaded = pd.DataFrame(
        {
            "review": ["导出失败，生成的长文格式全乱", "希望增加 Markdown 导出"],
            "score": [1, 4],
            "at": ["2026-01-01", "2026-01-02"],
            "app": ["AI Writer", "AI Writer"],
            "likes": [10, 3],
        }
    )
    buffer = BytesIO()
    uploaded.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)
    buffer.name = "upload.csv"

    standardized = load_feedback_file(buffer)
    assert list(standardized.columns[:11]) == [
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
    assert standardized.loc[0, "feedback_text"] == "导出失败，生成的长文格式全乱"
    assert standardized.loc[1, "thumbs_up"] == 3
