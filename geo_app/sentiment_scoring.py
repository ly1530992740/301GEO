from __future__ import annotations

import re
from typing import Any


POSITIVE_TERMS = {
    "专业": 7,
    "正规": 7,
    "安全": 7,
    "口碑": 6,
    "知名": 5,
    "连锁": 4,
    "权威": 6,
    "资质": 5,
    "经验": 4,
    "案例": 4,
    "服务好": 5,
    "性价比": 4,
    "可靠": 6,
    "推荐": 3,
    "高端": 3,
    "trusted": 6,
    "professional": 6,
    "reliable": 6,
    "popular": 4,
    "recommended": 4,
    "safe": 4,
}

RISK_TERMS = {
    "谨慎": -8,
    "争议": -10,
    "投诉": -12,
    "风险": -9,
    "价格不透明": -10,
    "评价分化": -8,
    "负面": -10,
    "不建议": -12,
    "避坑": -8,
    "纠纷": -12,
    "虚假": -14,
    "critical": -10,
    "complaint": -12,
    "risk": -9,
    "controversial": -10,
    "expensive": -4,
}


def score_text_sentiment(text: Any) -> dict[str, Any]:
    """Score AI-produced reasons/excerpts on a simple 0-100 sentiment scale."""

    value = str(text or "")
    if not value.strip():
        return {"sentiment_score": 50, "sentiment_label": "neutral", "positive_terms": [], "risk_terms": []}

    score = 50
    positive_hits: list[str] = []
    risk_hits: list[str] = []
    lowered = value.lower()
    for term, weight in POSITIVE_TERMS.items():
        haystack = lowered if re.match(r"^[a-z]+$", term) else value
        if term in haystack:
            score += weight
            positive_hits.append(term)
    for term, weight in RISK_TERMS.items():
        haystack = lowered if re.match(r"^[a-z]+$", term) else value
        if term in haystack:
            score += weight
            risk_hits.append(term)

    score = max(0, min(100, score))
    if score >= 70:
        label = "positive"
    elif score < 40:
        label = "critical"
    else:
        label = "neutral"
    return {
        "sentiment_score": score,
        "sentiment_label": label,
        "positive_terms": positive_hits[:8],
        "risk_terms": risk_hits[:8],
    }


def average_sentiment(items: list[Any]) -> int:
    scores = [score_text_sentiment(item)["sentiment_score"] for item in items if str(item or "").strip()]
    if not scores:
        return 50
    return round(sum(scores) / len(scores))
