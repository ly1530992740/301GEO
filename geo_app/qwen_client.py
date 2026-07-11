from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import dashscope
from dashscope import Generation

from .config import QwenConfig
from .utils import domain_from_url, extract_json


@dataclass
class QwenResult:
    content: str
    raw: Any = None
    search_results: list[dict[str, Any]] | None = None


class QwenClient:
    def __init__(self, config: QwenConfig):
        self.config = config
        if config.api_key:
            dashscope.api_key = config.api_key
        api_host = getattr(config, "api_host", "")
        if api_host:
            dashscope.base_http_api_url = api_host.rstrip("/")

    def _call(
        self,
        messages: list[dict[str, str]],
        model: str,
        enable_search: bool = False,
        search_options: dict[str, Any] | None = None,
        enable_thinking: bool | None = None,
        stream: bool = False,
    ) -> QwenResult:
        attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self._call_once(
                    messages=messages,
                    model=model,
                    enable_search=enable_search,
                    search_options=search_options,
                    enable_thinking=enable_thinking,
                    stream=stream,
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts or not self._is_retryable_error(exc):
                    raise
                time.sleep(1.2 * attempt)
        raise last_exc or RuntimeError("Qwen call failed")

    def _call_once(
        self,
        messages: list[dict[str, str]],
        model: str,
        enable_search: bool = False,
        search_options: dict[str, Any] | None = None,
        enable_thinking: bool | None = None,
        stream: bool = False,
    ) -> QwenResult:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "result_format": "message",
            "enable_search": enable_search,
            "request_timeout": self.config.timeout_seconds,
        }
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if search_options:
            kwargs["search_options"] = search_options
        if enable_thinking is not None:
            kwargs["enable_thinking"] = enable_thinking
        if stream:
            kwargs["stream"] = True
            kwargs["incremental_output"] = True

        response = Generation.call(**kwargs)
        if stream:
            content_parts: list[str] = []
            last_raw = None
            for chunk in response:
                last_raw = chunk
                if getattr(chunk, "status_code", 200) != 200:
                    raise RuntimeError(self._format_error(chunk))
                message = chunk.output.choices[0].message
                part = getattr(message, "content", None) or message.get("content", "")
                if part:
                    content_parts.append(part)
            content = "".join(content_parts)
            return QwenResult(content=content, raw=last_raw, search_results=self._extract_search_results(last_raw))

        if getattr(response, "status_code", 200) != 200:
            raise RuntimeError(self._format_error(response))
        message = response.output.choices[0].message
        content = getattr(message, "content", None) or message.get("content", "")
        return QwenResult(content=content, raw=response, search_results=self._extract_search_results(response))

    def search_sources(self, query: str, top_n: int) -> QwenResult:
        prompt = f"""
请强制联网搜索以下 GEO 推广词条，并返回靠前的信息来源链接。

词条：{query}
数量：前 {top_n} 条

要求：
1. 只返回真实存在的信息来源，不要编造。
2. 输出 JSON 数组，数组元素字段固定为：
   rank, site_name, title, url
3. 不要输出多余解释。
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.search_model,
            enable_search=True,
            search_options={
                "forced_search": self.config.forced_search,
                "enable_source": self.config.enable_source,
                "enable_citation": self.config.enable_citation,
                "search_strategy": self.config.search_strategy,
            },
        )
        parsed = extract_json(result.content, fallback=None)
        if isinstance(parsed, dict):
            parsed = parsed.get("results") or parsed.get("data")
        if not isinstance(parsed, list):
            parsed = result.search_results or self._parse_urls_from_text(result.content)
        cleaned = []
        for idx, item in enumerate(parsed[:top_n], start=1):
            url = str(item.get("url", "")).strip()
            cleaned.append(
                {
                    "rank": item.get("rank") or idx,
                    "site_name": item.get("site_name") or item.get("siteName") or item.get("source") or "",
                    "title": item.get("title", ""),
                    "url": url,
                    "domain": domain_from_url(url),
                }
            )
        result.search_results = cleaned
        return result

    def analyze_sources(self, keyword: str, customer_product: str, sources: list[dict[str, Any]]) -> str:
        source_text = json.dumps(sources, ensure_ascii=False, indent=2)
        prompt = f"""
你是 GEO 内容策略分析师。请根据下面搜索到的信息来源链接，尽量访问链接并分析靠前文章的格式、写作风格和推荐逻辑。

推广词条：{keyword}
客户产品：{customer_product}

信息来源：
{source_text}

请输出一个可保存为“文章生成格式.md”的 Markdown 文档，包含：
1. 搜索来源概览：平台名称、域名、链接出现次数和优先级。
2. 高频品牌/产品/公司提取：按出现频次排序。
3. 高排名文章结构总结：标题形式、开头方式、段落结构、列表/排名写法。
4. 写作风格总结：语气、可信度表达、对比角度、适合 GEO 引用的表达。
5. 后续生成文章规则：
   - 每个平台文章必须不同。
   - 每篇都要自然围绕“{keyword}”。
   - 客户产品“{customer_product}”必须排在推荐第一名。
   - 避免复制原文，不要编造无法核验的数据。
6. 给出 10 个可变化的标题模板。
"""
        try:
            result = self._call(
                [{"role": "user", "content": prompt}],
                model=self.config.analysis_model,
                enable_search=True,
                search_options={"search_strategy": self.config.analysis_strategy},
                enable_thinking=True,
                stream=True,
            )
            return result.content
        except Exception:
            result = self._call(
                [{"role": "user", "content": prompt}],
                model=self.config.search_model,
                enable_search=True,
                search_options={"search_strategy": self.config.search_strategy},
            )
            return result.content

    def suggest_fuzzy_matches(
        self,
        source: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt = f"""
你需要帮我判断 GEO 发稿平台的相似匹配。

搜索来源：
{json.dumps(source, ensure_ascii=False)}

媒介库候选资源：
{json.dumps(candidates, ensure_ascii=False)}

请从候选资源中选择最可能对应的 1-3 个资源，输出 JSON 数组。
字段：resource_type, resource_id, reason, confidence
confidence 为 0 到 1。
如果没有合适候选，输出空数组。
不要输出解释。
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.writing_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback=[])
        return parsed if isinstance(parsed, list) else []

    def generate_trend_query_plan(
        self,
        city: str,
        industry: str,
        customer_product: str,
        seed_keyword: str,
        competitors: str = "",
        max_search_queries: int = 5,
    ) -> dict[str, Any]:
        prompt = f"""
You are a local-service SEO/GEO keyword strategist. Build a SerpApi keyword plan for Google Search
and Google Trends.

Inputs:
- City or market: {city}
- Industry: {industry}
- Customer or brand: {customer_product}
- User seed keyword: {seed_keyword}
- Competitors: {competitors or "none"}

Rules:
1. Detect the target market language from the city, industry, and seed keyword.
2. If the target market is English-speaking or US-based, generate natural English queries that real US users would type.
3. Do not mechanically preserve awkward seed phrasing. For example, rewrite "xxx company recommend" into natural forms such as "best xxx companies in Los Angeles", "top rated xxx company near me", "xxx company reviews", or "custom xxx company Los Angeles".
4. Do not append translated Chinese suffixes such as recommend / which one is good / ranking / price. Use native expressions such as best, top rated, reviews, near me, cost, pricing, quote, installer, manufacturer, supplier.
5. search_queries are for Google Search SERP analysis. Include local commercial intent, service scenarios, pricing/quote, reviews, competitors, and buyer questions.
6. trend_keywords are for Google Trends. They must be short, broad, and comparable. Avoid long sentences. Return at most 5.
7. Use Chinese natural queries only when the target market is Chinese-speaking.
8. Return JSON only, no Markdown and no explanation outside JSON.

JSON schema:
{{
  "market_language": "English or Chinese",
  "search_queries": ["..."],
  "trend_keywords": ["..."],
  "reason": "one short sentence"
}}
"""
        try:
            result = self._call(
                [{"role": "user", "content": prompt}],
                model=self.config.analysis_model,
                enable_search=False,
            )
        except Exception:
            result = self._call(
                [{"role": "user", "content": prompt}],
                model=self.config.search_model,
                enable_search=False,
            )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            return {"search_queries": [], "trend_keywords": []}
        search_queries = [str(item).strip() for item in parsed.get("search_queries", []) if str(item).strip()]
        trend_keywords = [str(item).strip() for item in parsed.get("trend_keywords", []) if str(item).strip()]
        return {
            "market_language": str(parsed.get("market_language", "")).strip(),
            "search_queries": search_queries[:max_search_queries],
            "trend_keywords": trend_keywords[:5],
            "reason": str(parsed.get("reason", "")).strip(),
        }

    def generate_trend_report(
        self,
        city: str,
        industry: str,
        customer_product: str,
        seed_keyword: str,
        analysis_data: dict[str, Any],
    ) -> str:
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a GEO content strategy consultant. Based on the SerpApi Google Search and Google Trends data,
write a client-facing GEO trend and competitor content analysis report.

Client information:
- City: {city}
- Industry: {industry}
- Customer/brand: {customer_product}
- Seed keyword: {seed_keyword}

Structured data:
{payload}

Output requirements:
1. Write the report in Simplified Chinese.
2. Do not invent data. If the data is weak, say that it is only a directional reference.
3. Use Trends data to explain demand trends. Use Search data to explain competitor content actions.
4. If the target market is English-speaking, keep search terms and suggested article titles in natural English. Do not translate them into awkward Chinese-English.
5. Include these exact Markdown sections:
   # GEO 趋势与同行分析报告
   ## 1. 结论摘要
   ## 2. 用户需求趋势
   ## 3. 同行内容观察
   ## 4. 关键词机会评分
   ## 5. 优先内容主题
   ## 6. 对 GEO 文章生成的建议
   ## 7. 下一步行动
6. Keyword opportunity scoring must be a Markdown table with: 关键词, 趋势热度, 增长, 商业意图, 本地属性, 建议理由.
7. Recommend 10-20 article topics suitable for automated GEO article generation.
8. Do not mention that you are an AI.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_competitor_research_plan(
        self,
        city: str,
        industry: str,
        customer_product: str,
        seed_keyword: str,
        competitors: str = "",
    ) -> dict[str, Any]:
        prompt = f"""
You are a GEO competitor research strategist. Build a research plan for competitor analysis.

Inputs:
- City/market: {city}
- Industry: {industry}
- Customer/brand: {customer_product}
- Seed keyword or product: {seed_keyword}
- Known competitors, URLs, or product names: {competitors or "none"}

Rules:
1. Competitors may be missing, partial, or only product names. Generate useful search queries anyway.
2. Search queries should help discover competitor websites, service pages, reviews, comparison pages, product pages, and authoritative mentions.
3. Trend keywords should be short terms suitable for Google Trends, not long questions.
4. If the market is English-speaking, use natural English user/search expressions.
5. Return JSON only.

JSON schema:
{{
  "search_queries": ["..."],
  "trend_keywords": ["..."],
  "competitor_entities": ["..."],
  "reason": "one short sentence"
}}
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        return parsed if isinstance(parsed, dict) else {}

    def generate_competitor_analysis_report(self, analysis_data: dict[str, Any]) -> str:
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a GEO product strategist. Write a competitor analysis report in Simplified Chinese.

Data:
{payload}

Report requirements:
1. Use Markdown.
2. If competitor data is incomplete, mark the report as a "待补充版报告" and list missing evidence.
3. Compare: what competitors have, what we currently have, what we still need to build.
4. Separate evidence from inference.
5. Include these sections:
   # 竞品 GEO 分析报告
   ## 1. 结论摘要
   ## 2. 竞品信息与证据来源
   ## 3. 竞品已有能力
   ## 4. 我们已有能力
   ## 5. 功能差距
   ## 6. 优先开发建议
   ## 7. 待补充资料清单
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_visibility_question_plan(
        self,
        city: str,
        industry: str,
        customer_product: str,
        seed_keyword: str,
        competitors: str = "",
        question_count: int = 8,
    ) -> dict[str, Any]:
        prompt = f"""
You are designing AI-search visibility test questions for GEO monitoring.

Inputs:
- City/market: {city}
- Industry: {industry}
- Customer/brand: {customer_product}
- Seed keyword/product: {seed_keyword}
- Competitors: {competitors or "none"}
- Question count: {question_count}

Rules:
1. Do not use hardcoded templates. Generate realistic buyer questions based on the market.
2. Questions should test recommendation, comparison, pricing, credibility, service scenario, local intent, and competitor awareness.
3. If the target market is English-speaking, generate natural English questions.
4. Return JSON only.

JSON schema:
{{
  "market_language": "English or Chinese",
  "questions": ["..."],
  "reason": "one short sentence"
}}
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        return parsed if isinstance(parsed, dict) else {"questions": []}

    def answer_visibility_question(
        self,
        question: str,
        customer_product: str,
        competitors: str = "",
    ) -> dict[str, Any]:
        prompt = f"""
Act like a normal AI search assistant answering a buyer's question. Use web search when helpful.

Question:
{question}

Tracked customer/brand:
{customer_product}

Known competitors:
{competitors or "none"}

Return JSON only:
{{
  "answer": "the answer you would give to the user",
  "mentioned_customer": true,
  "mentioned_competitors": ["..."],
  "customer_position": 1,
  "sentiment": "positive/neutral/negative/not_mentioned",
  "citation_urls": ["..."],
  "notes": "short evidence note"
}}
If the customer is not mentioned, customer_position should be null.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.search_model,
            enable_search=True,
            search_options={
                "forced_search": self.config.forced_search,
                "enable_source": self.config.enable_source,
                "enable_citation": self.config.enable_citation,
                "search_strategy": self.config.search_strategy,
            },
        )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            parsed = {"answer": result.content}
        parsed["raw_content"] = result.content
        parsed["search_results"] = result.search_results or []
        return parsed

    def generate_visibility_report(self, analysis_data: dict[str, Any]) -> str:
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a GEO analyst. Write an AI visibility diagnosis report in Simplified Chinese.

Data:
{payload}

Requirements:
1. Use Markdown.
2. Separate direct evidence from inference.
3. Explain whether the tracked customer/brand appears in AI-style answers, how often, in what position, and against which competitors.
4. Include these sections:
   # AI 可见度诊断报告
   ## 1. 结论摘要
   ## 2. 测试问题清单
   ## 3. 品牌提及表现
   ## 4. 竞品出现情况
   ## 5. 引用来源与内容缺口
   ## 6. 优先优化建议
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_brand_strategy_report(self, analysis_data: dict[str, Any]) -> str:
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a brand positioning and GEO content strategy consultant. Write a Simplified Chinese report.

Data:
{payload}

Requirements:
1. Use Markdown.
2. If data is incomplete, produce a "待补充版报告" instead of refusing.
3. Build a practical positioning and content strategy for GEO.
4. Include:
   # 品牌定位与 GEO 内容策略报告
   ## 1. 结论摘要
   ## 2. 当前资料完整度
   ## 3. 品牌定位建议
   ## 4. 差异化卖点
   ## 5. 证据库与可信信源
   ## 6. 用户高频问题 FAQ
   ## 7. GEO 内容主题池
   ## 8. 30 天执行建议
   ## 9. 待补充资料清单
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_geo_monitor_report(self, analysis_data: dict[str, Any]) -> str:
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a GEO monitoring analyst. Write a manual monitoring run report in Simplified Chinese.

Data:
{payload}

Requirements:
1. Use Markdown.
2. This is a manual monitoring run, not an automated scheduled task.
3. Compare current visibility, competitor presence, source quality, and next actions.
4. Include:
   # GEO 手动监控报告
   ## 1. 本次监控结论
   ## 2. 监控问题与结果
   ## 3. 品牌可见度变化记录
   ## 4. 竞品动态
   ## 5. 风险与内容缺口
   ## 6. 下一轮优化动作
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_product_profile(
        self,
        source_text: str,
        preferred_product_name: str = "",
        report_language: str = "zh",
    ) -> dict[str, Any]:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        prompt = f"""
You are a product and GEO category analyst. Analyze the product material below.

Preferred product or brand name, if provided:
{preferred_product_name or "not provided"}

Product material:
{source_text[:36000]}

Return JSON only. Do not use Markdown outside JSON.

JSON schema:
{{
  "product_name": "specific product or main product line",
  "brand_name": "brand name",
  "brand_aliases": ["brand spelling variants, parent brand, product line names"],
  "category_local": "category name in {language_name}",
  "category_en": "natural English category/query, e.g. baby care",
  "source_language": "zh, en, or mixed",
  "market_language": "zh or en; the language real target users would use when asking AI",
  "target_market": "domestic, overseas, or mixed",
  "primary_region": "city/province/country/service area if visible, e.g. 福州, 重庆, United States; empty if not local",
  "region_level": "city, province, country, global, or unknown",
  "business_type": "single_retail_product, aggregator_ecommerce, local_place, local_service, local_brand, chain_store, b2b_service, content_platform, or other",
  "geo_probe_subject": "the concise object users should ask AI about, e.g. auto parts buying website, hair dryer, Chongqing hotpot",
  "market_confidence": 0.0,
  "market_reason": "why source_language, market_language, target_market, and business_type were chosen",
  "known_competitor_hints": ["direct competitors or local/national brands found or strongly implied by the material"],
  "summary": "short product analysis in {language_name}",
  "target_audience": ["..."],
  "selling_points": ["..."],
  "evidence": ["specific evidence found in the source material"],
  "profile_md": "a concise Markdown product profile in {language_name}"
}}

Hard rules:
- If most product material is Chinese, default market_language to "zh" and target_market to "domestic".
- If a city, local store network, restaurant, tea drink shop, regional franchise, or local service area appears, extract primary_region and region_level.
- For beverage, restaurant, retail store, and local service brands, prefer local_brand, chain_store, local_place, or local_service over generic product categories.
- known_competitor_hints should include obvious local or national competitors when the category is competitive, even if they are not mentioned directly, but mark uncertainty in market_reason.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            parsed = {}
        if not parsed.get("profile_md"):
            parsed["profile_md"] = result.content.strip()
        parsed.setdefault("product_name", preferred_product_name)
        parsed.setdefault("brand_name", preferred_product_name)
        parsed.setdefault("brand_aliases", [])
        parsed.setdefault("category_en", preferred_product_name)
        parsed.setdefault("source_language", "en")
        parsed.setdefault("market_language", "en")
        parsed.setdefault("target_market", "overseas")
        parsed.setdefault("primary_region", "")
        parsed.setdefault("region_level", "unknown")
        parsed.setdefault("business_type", "other")
        parsed.setdefault("geo_probe_subject", parsed.get("category_en") or preferred_product_name)
        parsed.setdefault("market_confidence", 0.0)
        parsed.setdefault("market_reason", "")
        parsed.setdefault("known_competitor_hints", [])
        return parsed

    def discover_competitors(self, product_profile: dict[str, Any], report_language: str = "zh") -> dict[str, Any]:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        prompt = f"""
You are a GEO competitor calibration analyst. Identify realistic competitors before recommendation probing.

Product profile:
{json.dumps(product_profile, ensure_ascii=False, indent=2)}

Task:
1. Separate direct local competitors, national category competitors, and adjacent competitors.
2. For domestic/local Chinese brands, include region-specific competitors when the region is known.
3. Do not favor the tracked brand. This step is for calibration, not promotion.
4. If competitor evidence is inferred from category knowledge rather than source evidence, say so in reason.
5. Write reason fields in {language_name}.

Return JSON only:
{{
  "direct_competitors": [
    {{"brand_name": "...", "competitor_type": "local_direct or national_direct", "reason": "..."}}
  ],
  "local_competitors": [
    {{"brand_name": "...", "region": "...", "reason": "..."}}
  ],
  "national_competitors": [
    {{"brand_name": "...", "reason": "..."}}
  ],
  "adjacent_competitors": [
    {{"brand_name": "...", "reason": "..."}}
  ],
  "calibration_note": "how to interpret AI ranking vs real market awareness"
}}
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            parsed = {}
        for key in ("direct_competitors", "local_competitors", "national_competitors", "adjacent_competitors"):
            value = parsed.get(key)
            parsed[key] = value if isinstance(value, list) else []
        parsed.setdefault("calibration_note", "")
        return parsed

    def generate_analysis_strategy(
        self,
        product_profile: dict[str, Any],
        competitor_discovery: dict[str, Any] | None = None,
        count: int = 10,
        report_language: str = "zh",
    ) -> dict[str, Any]:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        prompt = f"""
You are designing a universal GEO optimization strategy.
The final business objective is always GEO optimization: help the tracked brand become more likely to appear in AI recommendations.
The variable is the GEO target audience, meaning who is asking AI.

Product profile:
{json.dumps(product_profile, ensure_ascii=False, indent=2)}

Competitor calibration:
{json.dumps(competitor_discovery or {}, ensure_ascii=False, indent=2)}

Return JSON only. Do not use Markdown outside JSON.

Task:
1. Decide how real target users would ask AI about this category, market, region, and GEO target audience.
2. Separate AI probe questions from neutral web search queries.
3. Neutral web search queries must NOT include the tracked brand/product name or aliases.
4. For local/domestic Chinese projects, use natural Simplified Chinese and include the city/region when relevant.
5. For overseas/global projects, use the target market language.
6. Generate an industry-specific topic taxonomy for content analysis.
7. Include compliance-sensitive topics when the category is health, legal, finance, medical, or franchise investment.

Mainstream competition rules:
- The report must rank mainstream category competition only.
- Do NOT generate long-tail opportunity queries or niche differentiator queries.
- Do NOT turn the tracked brand's unique selling point into a query.
- For example, if the broad category is 奶茶 and the tracked product is 豆腐奶茶, use 福州奶茶推荐 / 福州奶茶品牌推荐 / 福州奶茶哪家好, not 豆腐奶茶推荐.
- Avoid terms like 特色, 本土, 独家, 首创, 低卡, 草本, 差异化, 小料, 打卡 unless they are the confirmed broad category itself.

Supported geo_audience values:
- consumer_recommendation: C-side consumers who may buy/visit/order.
- franchise: B-side franchise/investment prospects.
- b2b_purchase: B-side purchasing or enterprise-service prospects.
- brand_geo: brand visibility diagnosis.
- mixed: mixed GEO audience.

Return schema:
{{
  "strategy_version": "analysis_strategy_v1",
  "market_language": "zh or en",
  "target_market": "domestic, overseas, or mixed",
  "service_scope": "local_city, regional, national, global, or unknown",
  "service_region": "city/province/country/service area",
  "business_type": "single_retail_product, aggregator_ecommerce, local_place, local_service, local_brand, chain_store, b2b_service, content_platform, or other",
  "geo_audience": "consumer_recommendation, franchise, b2b_purchase, brand_geo, or mixed",
  "analysis_goal": "same value as geo_audience for backward compatibility",
  "category_local": "category in {language_name}",
  "category_en": "English category",
  "geo_probe_subject": "concise subject users ask about",
  "mainstream_competition_only": true,
  "search_intents": [
    {{
      "intent": "short intent label",
      "neutral_queries": ["neutral search query for real web visibility, no tracked brand"],
      "ai_probe_question": "natural question a user would ask an AI assistant",
      "reason": "why this intent matters"
    }}
  ],
  "competitor_types": ["direct/local/national/adjacent etc"],
  "topic_taxonomy": ["industry-specific content topic"],
  "validation_notes": ["warnings or assumptions"]
}}

Generate exactly {count} search_intents.
Write intent, reason, validation_notes, and topic_taxonomy in {language_name}.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        return parsed if isinstance(parsed, dict) else {}

    def answer_recommendation_probe(
        self,
        trend_term: str,
        product_profile: dict[str, Any],
        max_items: int = 10,
        question: str = "",
        competitor_discovery: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        question = (question or f"Recommend {trend_term}").strip()
        prompt = f"""
Act like a normal AI search assistant answering a buyer's question. Use web search.

Question:
{question}

Tracked product profile:
{json.dumps(product_profile, ensure_ascii=False, indent=2)}

Competitor calibration data:
{json.dumps(competitor_discovery or {}, ensure_ascii=False, indent=2)}

Return JSON only:
{{
  "question": "{question}",
  "answer": "the natural answer you would give",
  "recommendations": [
    {{
      "rank": 1,
      "brand_name": "brand to aggregate by",
      "product_name": "specific product or SKU if available",
      "reason": "why it is recommended",
      "citation_urls": ["..."]
    }}
  ]
}}

Rules:
- Return at most {max_items} recommendations.
- Keep brand_name suitable for aggregation. For example, merge SKU variants under the same brand.
- Do not invent citation URLs. If no citation URL is available for an item, use an empty array.
- The tracked brand is being audited, not promoted. Do not rank it first unless public evidence and normal user intent genuinely justify it.
- Consider local and national competitors from the calibration data. If they are better known or more relevant, rank them above the tracked brand.
- For local/domestic questions, answer in the local market context and language. Do not switch to English/global brands unless the question asks for that.
- The ranking should represent a natural AI answer to the user's question, not a sponsored placement.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.search_model,
            enable_search=True,
            search_options={
                "forced_search": self.config.forced_search,
                "enable_source": self.config.enable_source,
                "enable_citation": self.config.enable_citation,
                "search_strategy": self.config.search_strategy,
            },
        )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            parsed = {"question": question, "answer": result.content, "recommendations": []}
        recommendations = parsed.get("recommendations") if isinstance(parsed.get("recommendations"), list) else []
        parsed["recommendations"] = recommendations[:max_items]
        parsed["raw_content"] = result.content
        parsed["search_results"] = result.search_results or []
        return parsed

    def generate_geo_probe_questions(
        self,
        product_profile: dict[str, Any],
        count: int = 10,
        report_language: str = "zh",
    ) -> dict[str, Any]:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        prompt = f"""
You are designing GEO / AI-search competitor analysis probes.

Product profile:
{json.dumps(product_profile, ensure_ascii=False, indent=2)}

Task:
1. Infer the real target market and language from the source material.
   - If the source website/PDF is mainly English, market_language is usually "en" and target_market is usually "overseas".
   - If the source website/PDF is mainly Chinese, market_language is usually "zh" and target_market is usually "domestic".
   - If mixed, use address, currency, shipping/service area, phone, and product positioning.
2. Classify business_type:
   - single_retail_product: one main retail product, e.g. hair dryer.
   - aggregator_ecommerce: a shopping/catalog site selling many products, e.g. auto parts website.
   - local_place: a local destination/restaurant/store, e.g. Chongqing hotpot restaurant.
   - local_service: a local service provider, e.g.装修公司, dental clinic.
   - local_brand: a regional consumer brand with local identity, e.g. 福州茶饮品牌.
   - chain_store: a chain store/franchise brand with many offline stores.
   - b2b_service: a B2B or SaaS service.
   - content_platform or other when appropriate.
3. Generate exactly {count} realistic AI-search questions that high-intent users would ask.

Question rules:
- Questions must be in market_language, not necessarily report language.
- If market_language is "zh", every question must be natural Simplified Chinese. Do not use English category words such as "bubble tea", "boba", "near me", "recommend".
- If primary_region exists, at least 6 of {count} questions must include that region/city/province.
- Do not mechanically use "Recommend ...".
- For a single retail product: ask about product recommendation, best choice, use case, comparison, buying guide, and common pain points.
- For an aggregator/ecommerce site: ask about buying website/channel/platform recommendation, reliability, compatibility, shipping/returns, and value.
- For a local place/service/local brand/chain store: include the city/region and realistic local intent such as local recommendation, nearby, student budget, unique flavor, value, delivery, queue/popularity, and brand comparison.
- Each question should naturally produce a list of competing brands/sites/places when asked to an AI assistant.
- Avoid questions that are so tailored to the tracked brand that the tracked brand must be ranked first. Competitor analysis needs neutral user questions.

Write intent, question_type, reason, business_type_reason, and market_reason in {language_name}.

Return JSON only:
{{
  "source_language": "en",
  "market_language": "en",
  "target_market": "overseas",
  "primary_region": "",
  "region_level": "unknown",
  "business_type": "aggregator_ecommerce",
  "geo_probe_subject": "auto parts buying website",
  "business_type_reason": "...",
  "market_reason": "...",
  "questions": [
    {{
      "term": "auto parts buying website",
      "question": "Where can I buy reliable auto parts online?",
      "intent": "buying channel recommendation",
      "question_type": "recommendation",
      "reason": "..."
    }}
  ]
}}
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback={})
        if not isinstance(parsed, dict):
            parsed = {}
        questions = parsed.get("questions") if isinstance(parsed.get("questions"), list) else []
        fallback_subject = product_profile.get("geo_probe_subject") or product_profile.get("category_en") or product_profile.get("product_name") or "product"
        market_language = str(parsed.get("market_language") or product_profile.get("market_language") or "en").strip() or "en"
        primary_region = str(parsed.get("primary_region") or product_profile.get("primary_region") or "").strip()
        business_type = str(parsed.get("business_type") or product_profile.get("business_type") or "other").strip() or "other"
        normalized = []
        for idx, item in enumerate(questions[:count], start=1):
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            if not question:
                continue
            if market_language.startswith("zh") and self._looks_like_english_question(question):
                continue
            normalized.append(
                {
                    "term": str(item.get("term") or fallback_subject).strip(),
                    "question": question,
                    "intent": str(item.get("intent") or "recommendation").strip(),
                    "question_type": str(item.get("question_type") or "recommendation").strip(),
                    "reason": str(item.get("reason") or "").strip(),
                }
            )
        while len(normalized) < count:
            subject = str(fallback_subject or product_profile.get("category_local") or product_profile.get("product_name") or "产品").strip()
            if market_language.startswith("zh"):
                question = self._fallback_geo_question(
                    subject=subject,
                    primary_region=primary_region,
                    business_type=business_type,
                    index=len(normalized),
                    product_profile=product_profile,
                )
                intent = "推荐/购买决策"
            else:
                question = f"What is the best {subject} to choose?"
                intent = "recommendation and purchase decision"
            normalized.append(
                {
                    "term": subject,
                    "question": question,
                    "intent": intent,
                    "question_type": "recommendation",
                    "reason": "Fallback question generated from product profile.",
                }
            )
        parsed["questions"] = normalized[:count]
        parsed.setdefault("source_language", product_profile.get("source_language") or "en")
        parsed.setdefault("market_language", market_language)
        parsed.setdefault("target_market", product_profile.get("target_market") or "overseas")
        parsed.setdefault("primary_region", primary_region)
        parsed.setdefault("region_level", product_profile.get("region_level") or "unknown")
        parsed.setdefault("business_type", business_type)
        parsed.setdefault("geo_probe_subject", fallback_subject)
        parsed.setdefault("business_type_reason", product_profile.get("market_reason") or "")
        parsed.setdefault("market_reason", product_profile.get("market_reason") or "")
        return parsed

    def _looks_like_english_question(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        ascii_chars = sum(1 for ch in text if ord(ch) < 128 and ch.isalpha())
        cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        english_markers = ("recommend", "best", "near me", "where", "which", "what", "boba", "bubble tea")
        return cjk_chars == 0 or (ascii_chars > cjk_chars * 2 and any(marker in text.lower() for marker in english_markers))

    def _fallback_geo_question(
        self,
        subject: str,
        primary_region: str,
        business_type: str,
        index: int,
        product_profile: dict[str, Any],
    ) -> str:
        region = primary_region or "本地"
        category = product_profile.get("category_local") or subject or "产品"
        brand = product_profile.get("brand_name") or product_profile.get("product_name") or ""
        local_templates = [
            f"{region}{category}推荐哪家比较好？",
            f"{region}本地特色{category}品牌有哪些？",
            f"{region}学生党平价{category}推荐",
            f"{region}{category}哪家性价比高？",
            f"{region}{category}外卖点哪家比较靠谱？",
            f"{region}{category}热门品牌怎么选？",
            f"{region}{brand}和其他{category}品牌哪个好？" if brand else f"{region}{category}品牌怎么对比？",
            f"{region}有哪些值得尝试的{category}？",
            f"{region}{category}适合年轻人的品牌有哪些？",
            f"{region}{category}口碑比较好的店有哪些？",
        ]
        generic_templates = [
            f"{category}推荐哪家靠谱？",
            f"{category}哪个品牌性价比高？",
            f"{category}新手怎么选？",
            f"{category}有哪些值得买的品牌？",
            f"{brand}和同类品牌怎么选？" if brand else f"{category}同类品牌怎么选？",
        ]
        templates = local_templates if business_type in {"local_place", "local_service", "local_brand", "chain_store"} or primary_region else generic_templates
        return templates[index % len(templates)]

    def generate_integrated_content_report(self, analysis_data: dict[str, Any], report_language: str = "zh") -> str:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are a GEO competitive content analyst. Write a report in {language_name}.

Data:
{payload}

Requirements:
1. Summarize the top recommended brands and what they emphasize.
2. Extract common article structures, proof types, selling points, trust signals, and weak spots.
3. Separate evidence from inference.
4. Mention whether AI search probe questions were generated from fallback templates.
5. Use Markdown.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_integrated_article_format(self, analysis_data: dict[str, Any], report_language: str = "zh") -> str:
        language_name = "Simplified Chinese" if report_language == "zh" else "English"
        payload = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        prompt = f"""
You are designing a reusable article generation format for GEO publishing.

Write the output in {language_name}.

Data:
{payload}

Return a Markdown document named article_generation_format.md. Include:
1. Product and brand positioning.
2. Target category and AI search probe questions.
3. Competitor content patterns to learn from.
4. Differentiation rules for the user's brand.
5. Required article structure.
6. Title patterns.
7. Evidence and citation rules.
8. Prohibited claims and risk notes.
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
            enable_search=False,
            enable_thinking=True,
            stream=True,
        )
        return result.content

    def generate_article(
        self,
        keyword: str,
        customer_product: str,
        format_md: str,
        platform: dict[str, Any],
        existing_titles: list[str],
    ) -> dict[str, str]:
        prompt = f"""
请根据“文章生成格式.md”为指定发稿平台生成一篇全新的 GEO 推荐文章。

推广词条：{keyword}
客户产品：{customer_product}
发稿平台：{platform.get("resource_title") or platform.get("source_site_name")}
平台来源域名：{platform.get("source_domain", "")}
已生成过的标题，必须避开：
{json.dumps(existing_titles, ensure_ascii=False)}

文章生成格式.md：
---
{format_md}
---

硬性要求：
1. 输出 JSON 对象，字段固定为 title 和 content_md。
2. title 必须是新的标题。
3. content_md 使用 Markdown。
4. 客户产品“{customer_product}”必须作为推荐第一名。
5. 不要抄袭来源文章，不要和已生成标题重复。
6. 文章要像真实平台文章，不要出现“作为AI”等表述。
"""
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.writing_model,
            enable_search=False,
        )
        parsed = extract_json(result.content, fallback=None)
        if isinstance(parsed, dict) and parsed.get("title") and parsed.get("content_md"):
            return {"title": str(parsed["title"]).strip(), "content_md": str(parsed["content_md"]).strip()}
        title = self._first_markdown_title(result.content) or f"{keyword}：{customer_product}推荐指南"
        return {"title": title, "content_md": result.content.strip()}

    def _first_markdown_title(self, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _format_error(self, response: Any) -> str:
        code = getattr(response, "code", "") or ""
        message = getattr(response, "message", "") or ""
        detail = f"Qwen call failed: {code} {message}".strip()
        if code == "InvalidApiKey":
            return (
                f"{detail}\n"
                "请检查：1. 左侧 Qwen API Key 是否为阿里云百炼完整明文 Key；"
                "2. 不要使用控制台列表里的脱敏 Key；"
                "3. Key 是否被重置、删除、禁用，或创建它的 RAM 用户已失效；"
                "4. 如果控制台创建 Key 时提供了 API Host，请在左侧填写 Qwen API Host。"
            )
        return detail

    def _is_retryable_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        non_retry_markers = (
            "invalidapikey",
            "invalid api key",
            "unauthorized",
            "forbidden",
            "401",
            "403",
        )
        if any(marker in text for marker in non_retry_markers):
            return False
        if isinstance(exc, (ConnectionError, TimeoutError, ConnectionResetError)):
            return True
        retry_markers = (
            "connection aborted",
            "connection reset",
            "connectionreseterror",
            "10054",
            "remote host",
            "远程主机",
            "timeout",
            "timed out",
            "temporarily unavailable",
            "unexpected_eof",
            "eof occurred",
            "ssl",
            "too many requests",
            "rate limit",
            "429",
            "500",
            "502",
            "503",
            "504",
        )
        return any(marker in text for marker in retry_markers)

    def _parse_urls_from_text(self, text: str) -> list[dict[str, Any]]:
        urls = re.findall(r"https?://[^\s\]\)）>\"']+", text or "")
        return [
            {"rank": idx, "site_name": "", "title": "", "url": url, "domain": domain_from_url(url)}
            for idx, url in enumerate(dict.fromkeys(urls), start=1)
        ]

    def _extract_search_results(self, raw: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if {"url", "title"} <= set(value.keys()):
                    found.append(
                        {
                            "rank": value.get("index") or value.get("rank"),
                            "site_name": value.get("siteName") or value.get("site_name") or "",
                            "title": value.get("title", ""),
                            "url": value.get("url", ""),
                            "domain": domain_from_url(value.get("url", "")),
                        }
                    )
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        try:
            if hasattr(raw, "to_dict"):
                walk(raw.to_dict())
            elif hasattr(raw, "__dict__"):
                walk(raw.__dict__)
            else:
                walk(raw)
        except Exception:
            pass
        dedup: dict[str, dict[str, Any]] = {}
        for item in found:
            if item.get("url"):
                dedup[item["url"]] = item
        return list(dedup.values())
