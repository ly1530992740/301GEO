from __future__ import annotations

from typing import Any

import requests

from .config import SerpApiConfig


class SerpApiClient:
    base_url = "https://serpapi.com/search"

    def __init__(self, config: SerpApiConfig):
        self.config = config
        if not config.api_key:
            raise RuntimeError("请先配置 SerpApi API Key。")

    def google_search(
        self,
        query: str,
        location: str = "",
        num: int = 10,
        gl: str | None = None,
        hl: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "num": num,
            "gl": gl or self.config.default_gl,
            "hl": hl or self.config.default_hl,
            "api_key": self.config.api_key,
        }
        if location:
            params["location"] = location
        return self._get(params)

    def trends_timeseries(
        self,
        keywords: list[str],
        geo: str | None = None,
        date: str = "today 12-m",
        hl: str | None = None,
    ) -> dict[str, Any]:
        return self._google_trends(
            keywords=keywords,
            data_type="TIMESERIES",
            geo=geo,
            date=date,
            hl=hl,
        )

    def trends_related_queries(
        self,
        keyword: str,
        geo: str | None = None,
        date: str = "today 12-m",
        hl: str | None = None,
    ) -> dict[str, Any]:
        return self._google_trends(
            keywords=[keyword],
            data_type="RELATED_QUERIES",
            geo=geo,
            date=date,
            hl=hl,
        )

    def trends_geo_map(
        self,
        keyword: str,
        geo: str | None = None,
        date: str = "today 12-m",
        hl: str | None = None,
    ) -> dict[str, Any]:
        return self._google_trends(
            keywords=[keyword],
            data_type="GEO_MAP",
            geo=geo,
            date=date,
            hl=hl,
        )

    def _google_trends(
        self,
        keywords: list[str],
        data_type: str,
        geo: str | None,
        date: str,
        hl: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": "google_trends",
            "q": ",".join(keyword.strip() for keyword in keywords if keyword.strip()),
            "data_type": data_type,
            "date": date,
            "geo": geo or self.config.default_geo,
            "hl": hl or self.config.default_hl,
            "api_key": self.config.api_key,
        }
        return self._get(params)

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(self.base_url, params=params, timeout=self.config.timeout_seconds)
        if response.status_code >= 400:
            raise RuntimeError(f"SerpApi HTTP {response.status_code}：{response.text[:500]}")
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"SerpApi 请求失败：{data['error']}")
        return data
