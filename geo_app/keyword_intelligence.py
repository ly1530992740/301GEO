from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KeywordMetric:
    keyword: str
    source: str
    pc_index: int = 0
    mobile_index: int = 0
    so360_index: int = 0
    douyin_index: int = 0
    toutiao_index: int = 0
    google_index: int = 0
    daily_pc_search: int = 0
    daily_mobile_search: int = 0
    longtail_count: int = 0
    bid_company_count: int = 0
    sem_price: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordSuggestion:
    keyword: str
    source: str
    platform: str = ""
    parent_keyword: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchRankItem:
    keyword: str
    source: str
    rank: int
    title: str = ""
    url: str = ""
    site_url: str = ""
    site_weight: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value or "").replace(",", "").strip() or default))
    except Exception:
        return default


def normalize_5118_keyword_metric(item: dict[str, Any], source: str = "5118") -> KeywordMetric:
    return KeywordMetric(
        keyword=str(item.get("keyword") or ""),
        source=source,
        pc_index=safe_int(item.get("index")),
        mobile_index=safe_int(item.get("mobile_index")),
        so360_index=safe_int(item.get("haosou_index")),
        douyin_index=safe_int(item.get("douyin_index")),
        toutiao_index=safe_int(item.get("toutiao_index")),
        google_index=safe_int(item.get("google_index")),
        daily_pc_search=safe_int(item.get("bidword_pcpv")),
        daily_mobile_search=safe_int(item.get("bidword_wisepv")),
        longtail_count=safe_int(item.get("long_keyword_count")),
        bid_company_count=safe_int(item.get("bidword_company_count")),
        sem_price=str(item.get("sem_price") or item.get("bidword_price") or ""),
        raw=item,
    )


def normalize_aizhan_keyword_metric(item: dict[str, Any], source: str = "aizhan") -> KeywordMetric:
    return KeywordMetric(
        keyword=str(item.get("related_word") or item.get("keyword") or item.get("word") or ""),
        source=source,
        pc_index=safe_int(item.get("zhishu_pc") or item.get("pc_index")),
        mobile_index=safe_int(item.get("zhishu_wise") or item.get("mobile_index")),
        raw=item,
    )


def normalize_5118_rank_item(keyword: str, item: dict[str, Any], source: str = "5118") -> SearchRankItem:
    return SearchRankItem(
        keyword=keyword,
        source=source,
        rank=safe_int(item.get("rank")),
        title=str(item.get("page_title") or ""),
        url=str(item.get("page_url") or ""),
        site_url=str(item.get("site_url") or ""),
        site_weight=safe_int(item.get("site_weight")),
        raw=item,
    )


def normalize_aizhan_rank_item(keyword: str, item: dict[str, Any], source: str = "aizhan") -> SearchRankItem:
    return SearchRankItem(
        keyword=keyword,
        source=source,
        rank=safe_int(item.get("rank") or item.get("ranking")),
        title=str(item.get("title") or item.get("page_title") or ""),
        url=str(item.get("url") or item.get("page_url") or ""),
        site_url=str(item.get("domain") or item.get("site_url") or ""),
        raw=item,
    )
