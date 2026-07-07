from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


DEFAULT_KEYWORDS = {
    "价格/性价比": ["价格", "性价比", "便宜", "平价", "折扣", "预算", "price", "affordable", "value", "budget"],
    "口碑/评价": ["口碑", "评价", "推荐", "评分", "好评", "差评", "review", "rating", "trusted"],
    "品质/特色": ["特色", "品质", "质量", "卖点", "差异化", "quality", "feature", "unique"],
    "服务/售后": ["服务", "售后", "客服", "响应", "质保", "support", "service", "warranty"],
    "本地门店/地标": ["本地", "门店", "附近", "商圈", "地铁", "大学城", "local", "nearby", "store"],
    "加盟/投资": ["加盟", "招商", "创业", "投资", "回本", "培训", "franchise", "investment"],
    "资质/安全": ["资质", "认证", "安全", "合规", "禁忌", "证书", "certified", "safe", "compliance"],
    "性能/参数": ["性能", "参数", "续航", "降噪", "音质", "配置", "performance", "battery", "noise"],
}


def derive_content_topic_analysis(
    recommendation_items: list[dict[str, Any]],
    source_articles: list[dict[str, Any]],
    content_pattern_report: str,
    topic_taxonomy: list[str] | None = None,
) -> dict[str, Any]:
    taxonomy = [str(item).strip() for item in (topic_taxonomy or []) if str(item).strip()]
    if not taxonomy:
        taxonomy = list(DEFAULT_KEYWORDS.keys())
    topic_counts: Counter[str] = Counter()
    brand_topics: defaultdict[str, Counter[str]] = defaultdict(Counter)
    rules = [{"topic": topic, "keywords": keywords_for_topic(topic)} for topic in taxonomy]

    for item in recommendation_items:
        brand = str(item.get("brand_name") or "").strip() or "Unknown"
        text = " ".join(str(item.get(key, "")) for key in ("brand_name", "product_name", "reason", "trend_term")).lower()
        for topic in match_topics(text, rules):
            topic_counts[topic] += 1
            brand_topics[brand][topic] += 1
    for item in source_articles[:30]:
        text = str(item.get("text_excerpt") or "").lower()
        for topic in match_topics(text, rules):
            topic_counts[topic] += 1
    for topic in match_topics(str(content_pattern_report or "").lower(), rules):
        topic_counts[topic] += 1

    topic_rows = [{"topic": topic, "count": count} for topic, count in topic_counts.most_common()]
    matrix = []
    for brand, counts in brand_topics.items():
        for topic, count in counts.items():
            matrix.append({"brand": brand, "topic": topic, "count": count})
    return {
        "topics": topic_rows,
        "brand_topic_matrix": sorted(matrix, key=lambda item: (-item["count"], item["brand"], item["topic"])),
        "topic_rules": rules,
    }


def match_topics(text: str, rules: list[dict[str, Any]]) -> list[str]:
    matched = []
    for rule in rules:
        topic = str(rule.get("topic") or "").strip()
        keywords = [str(item).lower() for item in rule.get("keywords") or []]
        if topic and any(keyword and keyword in text for keyword in keywords):
            matched.append(topic)
    return matched or ["综合推荐"]


def keywords_for_topic(topic: str) -> list[str]:
    if topic in DEFAULT_KEYWORDS:
        return DEFAULT_KEYWORDS[topic]
    text = topic.lower()
    keywords = [topic]
    if any(word in text for word in ("口味", "味道", "爆品", "菜品", "饮品")):
        keywords.extend(["口味", "味道", "爆品", "好喝", "好吃", "特色"])
    if any(word in text for word in ("价格", "性价比", "收费")):
        keywords.extend(DEFAULT_KEYWORDS["价格/性价比"])
    if any(word in text for word in ("门店", "地标", "位置", "本地")):
        keywords.extend(DEFAULT_KEYWORDS["本地门店/地标"])
    if any(word in text for word in ("加盟", "投资", "招商", "培训")):
        keywords.extend(DEFAULT_KEYWORDS["加盟/投资"])
    if any(word in text for word in ("资质", "安全", "合规", "认证")):
        keywords.extend(DEFAULT_KEYWORDS["资质/安全"])
    if any(word in text for word in ("性能", "参数", "续航", "音质")):
        keywords.extend(DEFAULT_KEYWORDS["性能/参数"])
    if any(word in text for word in ("服务", "售后", "响应")):
        keywords.extend(DEFAULT_KEYWORDS["服务/售后"])
    if any(word in text for word in ("口碑", "评价", "人气")):
        keywords.extend(DEFAULT_KEYWORDS["口碑/评价"])
    return list(dict.fromkeys(keywords))
