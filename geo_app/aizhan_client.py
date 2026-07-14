from __future__ import annotations

from typing import Any

import requests

from .keyword_intelligence import KeywordMetric, SearchRankItem, normalize_aizhan_keyword_metric, normalize_aizhan_rank_item


class AizhanClient:
    BASE_URL = "https://apistore.aizhan.com"

    def __init__(self, api_key: str = "", base_url: str = BASE_URL, timeout_seconds: int = 30):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def related_words(self, word: str, page: int = 1, page_size: int = 20) -> list[KeywordMetric]:
        payload = self.request(
            "/word/related/{key}",
            {"word": word, "page": page, "pagesize": page_size},
        )
        rows = self._extract_rows(payload)
        return [normalize_aizhan_keyword_metric(item) for item in rows if isinstance(item, dict)]

    def keyword_index(self, words: list[str]) -> list[KeywordMetric]:
        payload = self.request("/baidu/index/{key}", {"words": ",".join(words)})
        rows = self._extract_rows(payload)
        return [normalize_aizhan_keyword_metric(item) for item in rows if isinstance(item, dict)]

    def submit_baidu_pc_rank(self, keywords: list[str], sites: list[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"keywords": ",".join(keywords)}
        if sites:
            data["sites"] = ",".join(sites)
        return self.request("/baidurank/pcaddtasks/{key}", data)

    def get_baidu_pc_rank(self, taskid: str) -> list[SearchRankItem]:
        payload = self.request("/baidurank/pctasksdata/{key}", {"taskid": taskid})
        result = []
        for row in self._extract_rows(payload):
            if not isinstance(row, dict):
                continue
            keyword = str(row.get("keyword") or "")
            ranks = row.get("ranks") if isinstance(row.get("ranks"), list) else None
            if ranks:
                for item in ranks:
                    if isinstance(item, dict):
                        result.append(normalize_aizhan_rank_item(keyword, item))
            else:
                result.append(normalize_aizhan_rank_item(keyword, row))
        return result

    def site_info(self, domain: str) -> dict[str, Any]:
        return self.request("/baidurank/siteinfos/{key}", {"domain": domain})

    def pc_export_keywords(self, domain: str, page: int = 1, page_size: int = 20) -> list[KeywordMetric]:
        payload = self.request("/baidurank/pcexport/{key}", {"domain": domain, "page": page, "pagesize": page_size})
        rows = self._extract_rows(payload)
        return [normalize_aizhan_keyword_metric(item) for item in rows if isinstance(item, dict)]

    def request(self, path_template: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Aizhan API key is not configured.")
        url = f"{self.base_url}{path_template.format(key=self.api_key)}"
        try:
            response = self.session.post(url, data=data, timeout=self.timeout_seconds)
            if response.status_code == 404:
                response = self.session.get(url, params=data, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Aizhan request failed: url={url}, reason={exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Aizhan response is not JSON: url={url}, body={response.text[:300]}") from exc
        if not self._is_success(payload):
            raise RuntimeError(f"Aizhan API error: {payload}")
        return payload

    def _is_success(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if "code" in payload:
            return str(payload.get("code")) in {"0", "1", "200", "200000"}
        if "status" in payload:
            return str(payload.get("status")).lower() in {"0", "1", "200", "success", "true"}
        return "data" in payload

    def _extract_rows(self, payload: dict[str, Any]) -> list[Any]:
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("list", "items", "words", "ranks", "rows", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            return [data]
        return []
