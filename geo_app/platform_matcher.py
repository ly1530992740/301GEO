from __future__ import annotations

import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

from .qwen_client import QwenClient
from .utils import domain_from_url, normalize_text, parse_price


def group_sources(search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], dict[str, Any]] = {}
    for item in search_results:
        site = item.get("site_name") or item.get("title") or item.get("domain") or ""
        domain = item.get("domain") or domain_from_url(item.get("url", ""))
        key = (site, domain)
        counter[key] += 1
        examples.setdefault(key, item)
    grouped = []
    for (site, domain), count in counter.most_common():
        example = examples[(site, domain)]
        grouped.append(
            {
                "source_site_name": site,
                "source_domain": domain,
                "source_url": example.get("url", ""),
                "link_count": count,
            }
        )
    return grouped


class PlatformMatcher:
    def __init__(self, qwen: QwenClient | None = None):
        self.qwen = qwen

    def match(self, sources: list[dict[str, Any]], resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped_sources = group_sources(sources)
        by_domain: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        resources_prepared = [self._prepare_resource(item) for item in resources]
        for resource in resources_prepared:
            for url_field in ("case_link", "entrance_link"):
                domain = domain_from_url(resource.get(url_field, ""))
                if domain:
                    by_domain[domain].append(resource)

        matches = []
        for source in grouped_sources:
            exact = self._find_exact(source, resources_prepared, by_domain)
            if exact:
                matches.append(self._build_match(source, exact, "exact", 1.0, True, ""))
                continue
            fuzzy = self._find_fuzzy(source, resources_prepared)
            if self.qwen and fuzzy:
                fuzzy = self._apply_ai_suggestion(source, fuzzy) or fuzzy
            if fuzzy:
                top = fuzzy[0]
                matches.append(
                    self._build_match(
                        source,
                        top,
                        "fuzzy",
                        float(top.get("_score", 0.0)),
                        False,
                        "未找到完全匹配，需确认相似平台后才可发布",
                    )
                )
            else:
                matches.append(
                    {
                        **source,
                        "match_type": "unmatched",
                        "confidence": 0.0,
                        "confirmed": False,
                        "warning": "媒介库未找到可用平台",
                    }
                )
        return matches

    def _prepare_resource(self, item: dict[str, Any]) -> dict[str, Any]:
        raw = item.get("raw_resource") or item
        prepared = {
            **item,
            "resource_title": item.get("resource_title") or item.get("title", ""),
            "price_1": parse_price(item.get("price_1")),
            "price_2": parse_price(item.get("price_2")),
            "price_3": parse_price(item.get("price_3")),
            "raw_resource": raw,
        }
        return prepared

    def _find_exact(
        self,
        source: dict[str, Any],
        resources: list[dict[str, Any]],
        by_domain: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any] | None:
        source_name = normalize_text(source.get("source_site_name", ""))
        source_domain = source.get("source_domain", "")
        if source_domain and by_domain.get(source_domain):
            return by_domain[source_domain][0]
        for resource in resources:
            if source_name and normalize_text(resource.get("resource_title", "")) == source_name:
                return resource
        return None

    def _find_fuzzy(self, source: dict[str, Any], resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        source_name = normalize_text(source.get("source_site_name", ""))
        source_domain = normalize_text(source.get("source_domain", ""))
        scored = []
        for resource in resources:
            title_score = SequenceMatcher(None, source_name, normalize_text(resource.get("resource_title", ""))).ratio()
            case_domain = normalize_text(domain_from_url(resource.get("case_link", "")))
            entrance_domain = normalize_text(domain_from_url(resource.get("entrance_link", "")))
            domain_score = max(
                SequenceMatcher(None, source_domain, case_domain).ratio() if source_domain and case_domain else 0,
                SequenceMatcher(None, source_domain, entrance_domain).ratio() if source_domain and entrance_domain else 0,
            )
            score = max(title_score, domain_score)
            if score >= 0.45:
                scored.append({**resource, "_score": score})
        return sorted(scored, key=lambda item: item["_score"], reverse=True)[:8]

    def _apply_ai_suggestion(self, source: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact_candidates = [
            {
                "resource_type": item.get("resource_type"),
                "resource_id": item.get("resource_id"),
                "resource_title": item.get("resource_title"),
                "case_link": item.get("case_link"),
                "entrance_link": item.get("entrance_link"),
                "score": item.get("_score"),
            }
            for item in candidates
        ]
        try:
            suggestions = self.qwen.suggest_fuzzy_matches(source, compact_candidates) if self.qwen else []
        except Exception:
            return candidates
        if not suggestions:
            return candidates
        by_id = {(item.get("resource_type"), int(item.get("resource_id") or 0)): item for item in candidates}
        reranked = []
        for suggestion in suggestions:
            key = (suggestion.get("resource_type"), int(suggestion.get("resource_id") or 0))
            item = by_id.get(key)
            if item:
                confidence = float(suggestion.get("confidence") or item.get("_score") or 0)
                reranked.append({**item, "_score": confidence, "_ai_reason": suggestion.get("reason", "")})
        return reranked or candidates

    def _build_match(
        self,
        source: dict[str, Any],
        resource: dict[str, Any],
        match_type: str,
        confidence: float,
        confirmed: bool,
        warning: str,
    ) -> dict[str, Any]:
        raw = resource.get("raw_resource") or resource
        return {
            **source,
            "resource_type": resource.get("resource_type", ""),
            "resource_id": resource.get("resource_id"),
            "resource_title": resource.get("resource_title") or resource.get("title", ""),
            "case_link": resource.get("case_link", ""),
            "entrance_link": resource.get("entrance_link", ""),
            "price_1": resource.get("price_1", 0.0),
            "price_2": resource.get("price_2", 0.0),
            "price_3": resource.get("price_3", 0.0),
            "match_type": match_type,
            "confidence": confidence,
            "confirmed": confirmed,
            "warning": warning or resource.get("_ai_reason", ""),
            "raw_resource": json.loads(json.dumps(raw, ensure_ascii=False, default=str)),
        }

