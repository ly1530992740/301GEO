from __future__ import annotations

from typing import Any


def build_standard_geo_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """Build Topify-style GEO metrics from existing workflow outputs."""

    summary = data.get("neutral_visibility_summary") or data.get("geo_visibility_summary") or {}
    diagnostic_summary = data.get("brand_diagnostic_summary") or {}
    prompt_runs = data.get("prompt_runs") or []
    brand_metrics = data.get("brand_visibility_metrics") or []
    own_metric = next((item for item in brand_metrics if item.get("is_user_brand")), {})

    total_brand_mentions = sum(_safe_int(item.get("mention_count")) for item in brand_metrics)
    own_mentions = _safe_int(own_metric.get("mention_count") or summary.get("mention_count"))
    sov = _safe_float(own_metric.get("share_of_voice"))
    if not sov and total_brand_mentions:
        sov = own_mentions / total_brand_mentions

    sentiment_score = _safe_int(diagnostic_summary.get("sentiment_score") or summary.get("sentiment_score") or 50)
    visibility_score = _safe_float(summary.get("visibility_score"))
    prompt_success = _safe_float(summary.get("prompt_success_rate"))

    return {
        "metric_version": "geo_metrics_v1",
        "visibility": {
            "score": visibility_score,
            "level": summary.get("visibility_level", ""),
            "value_label": f"{visibility_score}%",
            "formula": "客户品牌被提及的有效 AI 回答数 / 有效 AI 回答总数",
            "numerator": _safe_int(summary.get("brand_mentioned_responses")),
            "denominator": _safe_int(summary.get("total_ai_responses")),
            "business_meaning": "品牌在中立推荐类 AI 回答中出现得越频繁，GEO 可见度越高。",
        },
        "sentiment": {
            "score": sentiment_score,
            "label": _sentiment_label(sentiment_score),
            "formula": "AI 回答中对客户品牌的正负面描述、风险词和背书词综合评分",
            "positive_terms": own_metric.get("positive_terms") or [],
            "risk_terms": own_metric.get("risk_terms") or [],
            "business_meaning": "分数越高，AI 对品牌描述越正面；低分通常意味着投诉、风险、价格不透明等表达较多。",
        },
        "position": {
            "avg_rank": summary.get("avg_position"),
            "value_label": _rank_label(summary.get("avg_position")),
            "formula": "客户品牌在 AI 推荐列表中出现时的平均名次",
            "business_meaning": "平均名次越靠前，越容易被用户注意到并形成点击或咨询。",
        },
        "sov": {
            "score": round(sov, 4),
            "value_label": f"{round(sov * 100, 1)}%",
            "formula": "客户品牌 AI 提及次数 / 所有品牌 AI 提及次数",
            "numerator": own_mentions,
            "denominator": total_brand_mentions,
            "business_meaning": "SOV 越高，代表客户品牌在 AI 推荐声量中的占比越大。",
        },
        "provider_coverage": {
            "covered": _safe_int(summary.get("provider_coverage_count")),
            "total": _safe_int(summary.get("provider_total_count")),
            "formula": "提及客户品牌的 AI 平台数 / 本轮测试 AI 平台总数",
        },
        "prompt_success": {
            "score": prompt_success,
            "value_label": f"{round(prompt_success * 100, 1)}%",
            "formula": "客户品牌出现过的测试问题数 / 测试问题总数",
        },
        "prompt_count": len({item.get("prompt") for item in prompt_runs if item.get("prompt")}),
    }


def _safe_int(value: Any) -> int:
    try:
        if value in (None, "", "None"):
            return 0
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        if value in (None, "", "None"):
            return 0.0
        return round(float(str(value).replace(",", "").strip()), 4)
    except (TypeError, ValueError):
        return 0.0


def _rank_label(value: Any) -> str:
    if value in (None, "", "None"):
        return "未出现"
    try:
        number = float(value)
        return f"#{int(number)}" if number.is_integer() else f"#{number:.2f}"
    except (TypeError, ValueError):
        return str(value)


def _sentiment_label(score: int) -> str:
    if score >= 75:
        return "正面"
    if score >= 60:
        return "偏正面"
    if score >= 40:
        return "中性"
    return "风险偏高"
