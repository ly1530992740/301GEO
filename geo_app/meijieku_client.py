from __future__ import annotations

from typing import Any

import requests

from .config import MeijiekuConfig, normalize_meijieku_base_url


RESOURCE_ENDPOINTS = {
    "website": "/Resource/Website/list",
    "wemedia": "/Resource/Wemedia/list",
}

ARTICLE_ADD_ENDPOINTS = {
    "website": "/Article/Website/add",
    "wemedia": "/Article/Wemedia/add",
}

ARTICLE_LIST_ENDPOINTS = {
    "website": "/Article/Website/list",
    "wemedia": "/Article/Wemedia/list",
}


class MeijiekuClient:
    def __init__(self, config: MeijiekuConfig):
        self.config = config
        self.config.base_url = normalize_meijieku_base_url(config.base_url)
        self.session = requests.Session()
        self.token = config.token

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = self.token
        return headers

    def login(self) -> str:
        if self.token:
            return self.token
        if not self.config.mobile or not self.config.password:
            raise RuntimeError("Meijieku mobile/password are not configured.")
        payload = {"mobile": self.config.mobile, "password": self.config.password}
        data = self._post("/System/login_long_token", payload, auth=False)
        token = (data.get("data") or {}).get("token")
        if not token:
            raise RuntimeError(f"Meijieku login did not return token: {data}")
        self.token = token
        return token

    def list_resources(self, resource_type: str, page_size: int | None = None, max_pages: int | None = None) -> list[dict[str, Any]]:
        if resource_type not in RESOURCE_ENDPOINTS:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        self.login()
        page_size = page_size or self.config.resource_page_size
        max_pages = max_pages or self.config.resource_max_pages
        all_items: list[dict[str, Any]] = []
        for page_no in range(1, max_pages + 1):
            response = self._post(
                RESOURCE_ENDPOINTS[resource_type],
                {"pageNo": page_no, "pageSize": page_size},
            )
            data = response.get("data") or {}
            items = data.get("data") or []
            all_items.extend(items)
            last_page = int(data.get("last_page") or page_no)
            if page_no >= last_page or not items:
                break
        return all_items

    def submit_article(
        self,
        resource_type: str,
        title: str,
        content_html: str,
        resource_id: int,
        resource_name: str,
        customer: str,
        remark: str = "",
    ) -> dict[str, Any]:
        if resource_type not in ARTICLE_ADD_ENDPOINTS:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        self.login()
        payload = {
            "title_type": 0,
            "title": title,
            "content": content_html,
            "remark": remark,
            "customer": customer,
            "resource": [
                {
                    "resource_id": int(resource_id),
                    "name": resource_name,
                    "title": title,
                }
            ],
        }
        return self._post(ARTICLE_ADD_ENDPOINTS[resource_type], payload)

    def query_article(self, resource_type: str, order_id: str) -> dict[str, Any] | None:
        if resource_type not in ARTICLE_LIST_ENDPOINTS:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        self.login()
        response = self._post(
            ARTICLE_LIST_ENDPOINTS[resource_type],
            {"pageNo": 1, "pageSize": 10, "order_id": order_id},
        )
        items = ((response.get("data") or {}).get("data")) or []
        return items[0] if items else None

    def _post(self, path: str, payload: dict[str, Any], auth: bool = True) -> dict[str, Any]:
        if auth and not self.token:
            self.login()
        url = self._url(path)
        try:
            response = self.session.post(url, json=payload, headers=self._headers(), timeout=60)
            response.encoding = "utf-8"
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = ""
            if exc.response is not None:
                body = (exc.response.text or "")[:300]
            raise RuntimeError(
                f"Meijieku request failed: HTTP {status}, url={url}. "
                "Check the configured API base URL and endpoint path. "
                f"Response body: {body}"
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Meijieku connection failed: url={url}, reason={exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Meijieku response is not JSON: url={url}, body={response.text[:300]}") from exc
        status = data.get("status")
        if status not in (200, "200"):
            raise RuntimeError(f"Meijieku API error {status}: {data.get('msg') or data}")
        return data
