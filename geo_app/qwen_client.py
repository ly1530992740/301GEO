from __future__ import annotations

import json
import re
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
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "result_format": "message",
            "enable_search": enable_search,
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
        result = self._call(
            [{"role": "user", "content": prompt}],
            model=self.config.analysis_model,
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
   # GEO ?????????
   ## 1. ????
   ## 2. ??????
   ## 3. ?????
   ## 4. ??????
   ## 5. ???????
   ## 6. ?? GEO ????
   ## 7. ???????
6. Keyword opportunity scoring must be a Markdown table with: ???, ???, ????, ????, ???, ??.
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
