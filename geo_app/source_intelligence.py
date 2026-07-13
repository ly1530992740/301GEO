from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .brand_normalizer import brand_key
from .utils import domain_from_url


UGC_DOMAINS = ("zhihu", "xiaohongshu", "tieba", "douban", "weibo", "reddit", "quora", "bilibili")
EDITORIAL_DOMAINS = (
    "sohu",
    "163",
    "qq.com",
    "toutiao",
    "baijiahao",
    "sina",
    "ifeng",
    "thepaper",
    "36kr",
    "people",
    "xinhuanet",
)
REFERENCE_DOMAINS = ("baike", "wikipedia", "wiki", "360doc", "docin")
INSTITUTIONAL_DOMAINS = ("gov.", ".gov", "edu.", ".edu", "org.", ".org", "nhc.gov", "samr.gov")


def build_source_intelligence(
    source_links: list[dict[str, Any]],
    source_articles: list[dict[str, Any]],
    recommendation_items: list[dict[str, Any]],
    top_brands: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Summarize AI citation domains and source opportunities."""

    articles_by_url = {_clean_url(item.get("url")): item for item in source_articles if item.get("url")}
    brands = _brand_names(top_brands, recommendation_items, profile)
    own_terms = _own_terms(profile)
    total_responses = (
        len({(item.get("engine"), item.get("question")) for item in recommendation_items if item.get("engine") or item.get("question")})
        or 1
    )

    grouped: dict[str, dict[str, Any]] = {}
    response_seen: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
    providers: defaultdict[str, set[str]] = defaultdict(set)
    labels: defaultdict[str, Counter[str]] = defaultdict(Counter)
    brand_hits: defaultdict[str, Counter[str]] = defaultdict(Counter)
    urls: defaultdict[str, list[str]] = defaultdict(list)

    for link in source_links:
        url = _clean_url(link.get("url"))
        domain = str(link.get("domain") or domain_from_url(url) or "").lower()
        if not domain:
            continue
        article = articles_by_url.get(url, {})
        text = " ".join(
            [
                str(link.get("label") or ""),
                str(article.get("label") or ""),
                str(article.get("text_excerpt") or ""),
            ]
        )
        grouped.setdefault(
            domain,
            {
                "domain": domain,
                "domain_type": classify_domain(domain),
                "citation_count": 0,
                "used_response_count": 0,
                "used_rate": 0.0,
                "avg_citations": 0.0,
                "mentioned_user_brand": False,
                "brands_appear": [],
                "providers": [],
                "sample_urls": [],
                "action": "",
            },
        )
        grouped[domain]["citation_count"] += 1
        response_seen[domain].add((str(link.get("engine") or ""), str(link.get("trend_term") or link.get("label") or url)))
        if link.get("engine"):
            providers[domain].add(str(link.get("engine")))
        if link.get("label"):
            labels[domain][str(link.get("label"))] += 1
        urls[domain].append(url)
        for brand in brands:
            if _mentions(text, [brand]):
                brand_hits[domain][brand] += 1
        if _mentions(text, own_terms):
            grouped[domain]["mentioned_user_brand"] = True

    rows = []
    for domain, row in grouped.items():
        used_count = len(response_seen[domain])
        citation_count = int(row.get("citation_count") or 0)
        row["used_response_count"] = used_count
        row["used_rate"] = round(used_count / total_responses, 4)
        row["avg_citations"] = round(citation_count / max(used_count, 1), 2)
        row["providers"] = sorted(providers[domain])
        row["brands_appear"] = [brand for brand, _ in brand_hits[domain].most_common(10)]
        if not row["brands_appear"]:
            row["brands_appear"] = [brand for brand, _ in labels[domain].most_common(5)]
        row["sample_urls"] = list(dict.fromkeys(urls[domain]))[:5]
        row["action"] = _source_action(row)
        rows.append(row)

    rows.sort(key=lambda item: (-int(item.get("citation_count") or 0), -float(item.get("used_rate") or 0), item.get("domain", "")))
    for idx, item in enumerate(rows, start=1):
        item["rank"] = idx

    type_counter = Counter(item.get("domain_type") or "Other" for item in rows)
    opportunity_rows = [
        {
            "domain": item["domain"],
            "domain_type": item["domain_type"],
            "reason": "AI 已引用该域名，但来源内容暂未识别到客户品牌。",
            "action": item["action"],
            "priority": "高" if item["citation_count"] >= 2 else "中",
        }
        for item in rows
        if not item.get("mentioned_user_brand")
    ][:12]
    return {
        "source_intelligence_version": "source_intelligence_v1",
        "domain_summary": rows,
        "domain_type_distribution": [{"domain_type": domain_type, "count": count} for domain_type, count in type_counter.most_common()],
        "source_opportunities": opportunity_rows,
        "definitions": {
            "domain_type": "Corporate/UGC/Editorial/Reference/Institutional/Other 的信源类型分类。",
            "used_rate": "至少一次出现在 AI 回答引用中的回答占比。",
            "avg_citations": "该域名被引用时，平均每个回答贡献的引用次数。",
            "mentioned_user_brand": "抓取文本或链接标签中是否识别到客户品牌。",
            "brands_appear": "该信源内容或引用标签中出现的品牌/竞品。",
        },
    }


def classify_domain(domain: str) -> str:
    value = str(domain or "").lower()
    if any(item in value for item in INSTITUTIONAL_DOMAINS):
        return "Institutional"
    if any(item in value for item in REFERENCE_DOMAINS):
        return "Reference"
    if any(item in value for item in UGC_DOMAINS):
        return "UGC"
    if any(item in value for item in EDITORIAL_DOMAINS):
        return "Editorial"
    if value:
        return "Corporate"
    return "Other"


def _source_action(row: dict[str, Any]) -> str:
    domain_type = row.get("domain_type")
    if row.get("mentioned_user_brand"):
        return "保持该信源内容更新，并补充可引用的价格、案例、FAQ 和来源依据。"
    if domain_type == "UGC":
        return "优先补充问答、测评、用户经验或对比型内容，让客户品牌进入该信源语境。"
    if domain_type == "Editorial":
        return "优先安排新闻稿、榜单稿、行业解读或本地媒体内容投放。"
    if domain_type == "Corporate":
        return "检查是否为竞品官网或行业站；如可投放，补充品牌介绍、对比和案例内容。"
    if domain_type == "Reference":
        return "补充百科、资料型、定义型内容，提升 AI 引用时的事实依据。"
    if domain_type == "Institutional":
        return "补充资质、备案、合规证明和权威来源引用，避免夸大宣传。"
    return "评估该信源是否可发布内容，并补充品牌可验证信息。"


def _brand_names(top_brands: list[dict[str, Any]], items: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    values = [
        profile.get("brand_name"),
        profile.get("product_name"),
        *(profile.get("brand_aliases") or []),
        *[item.get("brand_name") for item in top_brands],
        *[item.get("brand_name") for item in items],
    ]
    result = []
    seen = set()
    for value in values:
        clean = str(value or "").strip()
        key = brand_key(clean)
        if clean and key and key not in seen:
            seen.add(key)
            result.append(clean)
    return result[:40]


def _own_terms(profile: dict[str, Any]) -> list[str]:
    return [
        str(value).strip()
        for value in [profile.get("brand_name"), profile.get("product_name"), *(profile.get("brand_aliases") or [])]
        if str(value or "").strip()
    ]


def _mentions(text: str, terms: list[str]) -> bool:
    text_value = str(text or "").lower().replace(" ", "")
    text_key = brand_key(text)
    for term in terms:
        clean = str(term or "").lower().replace(" ", "")
        key = brand_key(term)
        if clean and clean in text_value:
            return True
        if key and key in text_key:
            return True
    return False


def _clean_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/")
