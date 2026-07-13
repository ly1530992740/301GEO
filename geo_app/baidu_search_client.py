from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_BAIDU_SEARCH_API_KEY = ""
DEFAULT_BAIDU_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"


class BaiduSearchClient:
    endpoint = DEFAULT_BAIDU_SEARCH_URL

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        endpoint: str | None = None,
        edition: str | None = None,
        search_source: str | None = None,
    ):
        self.api_key = (
            (api_key or "").strip()
            or os.getenv("BAIDU_API_KEY", "").strip()
            or os.getenv("BAIDU_QIANFAN_API_KEY", "").strip()
            or os.getenv("BAIDU_SEARCH_API_KEY", "").strip()
        )
        self.endpoint = (endpoint or os.getenv("BAIDU_SEARCH_API_URL", "") or DEFAULT_BAIDU_SEARCH_URL).strip()
        self.edition = (edition or os.getenv("BAIDU_SEARCH_EDITION", "") or "lite").strip()
        self.search_source = (search_source or os.getenv("BAIDU_SEARCH_SOURCE", "") or "baidu_search_v2").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _int_env("BAIDU_TIMEOUT_SECONDS", 45)

    def web_search(self, query: str, top_k: int = 50) -> dict[str, Any]:
        payload = {
            "messages": [{"content": query, "role": "user"}],
            "edition": self.edition,
            "search_source": self.search_source,
            "resource_type_filter": [{"type": "web", "top_k": min(max(int(top_k), 1), 50)}],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Appbuilder-Authorization": f"Bearer {self.api_key}",
        }
        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout_seconds)
        if response.status_code >= 400:
            raise RuntimeError(f"Baidu search HTTP {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Baidu search response is not JSON: {response.text[:300]}") from exc


def extract_baidu_results(raw: dict[str, Any]) -> list[dict[str, Any]]:
    references = raw.get("references")
    if isinstance(references, list):
        return [_normalize_reference(item, idx) for idx, item in enumerate(references, start=1) if isinstance(item, dict)]
    return []


def extract_baidu_total_count(raw: dict[str, Any]) -> int | None:
    """Best-effort extraction for all-web result counts.

    The Qianfan web_search response shape may vary by account/API version. If no
    total count is present, callers should fall back to top-k metrics and expose
    that limitation in the report.
    """
    paths = [
        ("total",),
        ("total_count",),
        ("result_count",),
        ("count",),
        ("data", "total"),
        ("data", "total_count"),
        ("data", "result_count"),
        ("search_info", "total"),
        ("search_info", "total_results"),
        ("searchInfo", "totalResults"),
        ("metadata", "total"),
    ]
    for path in paths:
        value: Any = raw
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        parsed = _parse_total_count(value)
        if parsed is not None:
            return parsed
    return _walk_for_total(raw)


def _normalize_reference(item: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": item.get("id") or rank,
        "title": item.get("title") or "",
        "snippet": item.get("content") or "",
        "url": item.get("url") or "",
        "source": item.get("website") or item.get("web_anchor") or "",
        "date": item.get("date") or "",
        "raw": item,
    }


def _parse_total_count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text:
        return None
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000
        text = text[:-1]
    try:
        return max(int(float(text) * multiplier), 0)
    except ValueError:
        return None


def _walk_for_total(value: Any) -> int | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            if key_l in {"total", "total_count", "totalcount", "result_count", "total_results", "totalresults"}:
                parsed = _parse_total_count(child)
                if parsed is not None:
                    return parsed
        for child in value.values():
            found = _walk_for_total(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _walk_for_total(child)
            if found is not None:
                return found
    return None


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
