from __future__ import annotations

from typing import Any


ASSET_RULES = [
    ("brand_intro", "品牌介绍", ("品牌", "公司", "简介", "about", "who we are")),
    ("product_service", "产品/服务页", ("产品", "服务", "项目", "解决方案", "service", "product")),
    ("price", "价格/套餐/费用", ("价格", "费用", "报价", "套餐", "price", "pricing", "cost")),
    ("case", "案例/客户故事", ("案例", "客户", "作品", "效果", "case", "customer story", "before after")),
    ("faq", "FAQ/问答", ("faq", "常见问题", "问答", "问题", "q&a")),
    ("credential", "资质/证书/备案", ("资质", "证书", "认证", "备案", "许可证", "license", "certificate")),
    ("comparison", "对比/选择指南", ("对比", "比较", "怎么选", "哪家", "排名", "comparison", "versus", "vs")),
    ("media", "媒体报道/新闻", ("新闻", "媒体", "报道", "动态", "press", "news", "media")),
    ("location", "地区/门店/联系方式", ("地址", "门店", "电话", "联系", "地图", "location", "contact")),
]


def audit_owned_assets(sources: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Audit whether owned assets are useful as AI-citable structured sources."""

    pages = sources.get("website_pages") or []
    pdfs = sources.get("pdf_documents") or []
    text = _combined_text(sources)
    pages_by_rule = []
    present_count = 0
    for key, label, terms in ASSET_RULES:
        matched_pages = [
            {
                "url": page.get("url", ""),
                "matched_terms": _matched_terms(_page_text(page), terms),
            }
            for page in pages
            if _matched_terms(_page_text(page), terms)
        ]
        present = bool(matched_pages) or bool(_matched_terms(text, terms))
        if present:
            present_count += 1
        pages_by_rule.append(
            {
                "asset_key": key,
                "asset_name": label,
                "present": present,
                "matched_pages": matched_pages[:5],
                "recommendation": _asset_recommendation(key, label, present, profile),
            }
        )

    crawl_success = len([page for page in pages if page.get("text") and not page.get("error")])
    crawl_total = len(pages)
    schema_hits = _schema_hits(text)
    ai_readability_score = _score_assets(present_count, len(ASSET_RULES), crawl_success, crawl_total, schema_hits)
    missing_assets = [item for item in pages_by_rule if not item.get("present")]
    return {
        "owned_asset_audit_version": "owned_asset_audit_v1",
        "website_url": sources.get("website_url", ""),
        "owned_asset_score": ai_readability_score,
        "ai_readability_score": ai_readability_score,
        "crawl_success_count": crawl_success,
        "crawl_total_count": crawl_total,
        "pdf_document_count": len(pdfs),
        "schema_signals": schema_hits,
        "asset_checks": pages_by_rule,
        "missing_assets": missing_assets,
        "structured_source_actions": _structured_actions(missing_assets, schema_hits, crawl_success, crawl_total, profile),
        "definitions": {
            "owned_asset_score": "官网作为 AI 可解析信源的综合评分，基于页面可抓取性、关键内容资产和结构化信号。",
            "structured_source": "让官网具备 AI 可引用的明确事实块，例如 FAQ、价格、资质、案例、对比、媒体报道和结构化数据。",
        },
    }


def _combined_text(sources: dict[str, Any]) -> str:
    parts = []
    for page in sources.get("website_pages") or []:
        parts.extend([str(page.get("url") or ""), str(page.get("text") or ""), str(page.get("error") or "")])
    for pdf in sources.get("pdf_documents") or []:
        parts.extend([str(pdf.get("name") or ""), str(pdf.get("text_excerpt") or ""), str(pdf.get("error") or "")])
    return "\n".join(parts).lower()


def _page_text(page: dict[str, Any]) -> str:
    return f"{page.get('url') or ''}\n{page.get('text') or ''}".lower()


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    value = str(text or "").lower()
    return [term for term in terms if term.lower() in value][:8]


def _schema_hits(text: str) -> list[str]:
    value = str(text or "").lower()
    hits = []
    if "schema.org" in value:
        hits.append("schema.org")
    if "application/ld+json" in value or "json-ld" in value:
        hits.append("JSON-LD")
    if "faqpage" in value:
        hits.append("FAQPage")
    if "organization" in value:
        hits.append("Organization")
    if "localbusiness" in value:
        hits.append("LocalBusiness")
    return list(dict.fromkeys(hits))


def _score_assets(present_count: int, total_count: int, crawl_success: int, crawl_total: int, schema_hits: list[str]) -> int:
    asset_score = (present_count / max(total_count, 1)) * 70
    crawl_score = (crawl_success / max(crawl_total, 1)) * 20 if crawl_total else 0
    schema_score = min(len(schema_hits) * 4, 10)
    return round(min(100, asset_score + crawl_score + schema_score))


def _asset_recommendation(key: str, label: str, present: bool, profile: dict[str, Any]) -> str:
    category = profile.get("category_local") or profile.get("category_en") or "业务"
    if present:
        return f"已识别到{label}信号，建议补充更新时间、来源依据和可直接引用的结论句。"
    mapping = {
        "faq": f"新增围绕“{category}怎么选/价格/风险/适合人群”的 FAQ 页面。",
        "price": "补充价格区间、套餐边界或询价说明，避免 AI 只能引用竞品价格。",
        "credential": "补充资质、证书、备案、授权和合规说明，尤其适合高风险行业。",
        "case": "补充真实案例、客户故事或前后对比，并标注适用场景与限制。",
        "comparison": "补充对比/选择指南页面，帮助 AI 在推荐场景中引用客户品牌。",
    }
    return mapping.get(key, f"新增{label}页面或内容块，让官网成为 AI 可引用的结构化信源。")


def _structured_actions(
    missing_assets: list[dict[str, Any]],
    schema_hits: list[str],
    crawl_success: int,
    crawl_total: int,
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = []
    if crawl_total and crawl_success < crawl_total:
        actions.append(
            {
                "priority": "高",
                "action": "修复官网部分页面抓取失败或正文不可读问题",
                "reason": "AI 搜索和内容分析依赖可抓取正文，抓取失败会降低官网作为信源的可用性。",
            }
        )
    if not schema_hits:
        actions.append(
            {
                "priority": "高",
                "action": "为官网补充 Organization/LocalBusiness/FAQPage JSON-LD",
                "reason": "结构化数据能帮助 AI 和搜索引擎识别品牌、地区、服务和 FAQ。",
            }
        )
    for item in missing_assets[:8]:
        actions.append(
            {
                "priority": "高" if item.get("asset_key") in {"faq", "price", "credential", "comparison"} else "中",
                "action": item.get("recommendation", ""),
                "reason": f"缺少{item.get('asset_name')}会让 AI 更难引用客户官网作为权威来源。",
            }
        )
    return actions[:12]
