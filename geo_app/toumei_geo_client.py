from __future__ import annotations

import hashlib
import time
from typing import Any

import requests


class ToumeiGEOClient:
    BASE_URL = "https://geo.toumeiw.cn"

    def __init__(
        self,
        secret_id: str = "",
        secret_key: str = "",
        base_url: str = BASE_URL,
        timeout_seconds: int = 60,
    ):
        self.secret_id = secret_id.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def user_info(self) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/userInfo", {})

    def recharge_log(self, page: int = 1, limit: int = 200) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/rechargelog", {"page": page, "limit": limit})

    def record_list(
        self,
        page: int = 1,
        limit: int = 200,
        start_date: str = "",
        end_date: str = "",
        order_no: str = "",
    ) -> dict[str, Any]:
        payload = {"page": page, "limit": limit}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if order_no:
            payload["order_no"] = order_no
        return self.post("/meijieapi/daili3/getRecordList", payload)

    def media_list(self, page: int = 1, limit: int = 200, uptime: int | None = None, media_id: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"page": page, "limit": limit}
        if uptime is not None:
            payload["uptime"] = uptime
        if media_id is not None:
            payload["id"] = media_id
        return self.post("/meijieapi/daili3/media_lst", payload)

    def wemedia_list(self, page: int = 1, limit: int = 200, uptime: int | None = None, media_id: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"page": page, "limit": limit}
        if uptime is not None:
            payload["uptime"] = uptime
        if media_id is not None:
            payload["id"] = media_id
        return self.post("/meijieapi/daili3/w/media_lst", payload)

    def create_media_order(
        self,
        title: str,
        content: str,
        media_id: int,
        order_no: str,
        saling_price: float,
        remark: str = "",
        published_at: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": title,
            "content": content,
            "mid": media_id,
            "no": order_no,
            "saling_price": saling_price,
        }
        if remark:
            payload["remark"] = remark
        if published_at:
            payload["published_at"] = published_at
        return self.post("/meijieapi/daili3/create_media_order", payload)

    def create_wemedia_order(
        self,
        title: str,
        content: str,
        media_id: int,
        order_no: str,
        saling_price: float,
        remark: str = "",
        published_at: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": title,
            "content": content,
            "mid": media_id,
            "no": order_no,
            "saling_price": saling_price,
        }
        if remark:
            payload["remark"] = remark
        if published_at:
            payload["published_at"] = published_at
        return self.post("/meijieapi/daili3/create_wmedia_order", payload)

    def query_media_order(self, order_numbers: list[str]) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/query_media_order", {"nostr": ",".join(order_numbers)})

    def query_wemedia_order(self, order_numbers: list[str]) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/query_wmedia_order", {"nostr": ",".join(order_numbers)})

    def active_ids(self, resource_type: int, status: int = 1) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/get_ids", {"status": status, "type": resource_type})

    def enums(self) -> dict[str, Any]:
        return self.post("/meijieapi/daili3/get_enum", {})

    def signed_payload(self, payload: dict[str, Any], timestamp: int | None = None) -> dict[str, Any]:
        if not self.secret_id or not self.secret_key:
            raise RuntimeError("Toumei GEO secret_id/secret_key are not configured.")
        result = {key: value for key, value in payload.items() if value not in (None, "")}
        result["secret_id"] = self.secret_id
        result["timestamp"] = int(timestamp or time.time())
        result["signature"] = self.signature(result)
        return result

    def signature(self, payload: dict[str, Any]) -> str:
        sign_items = []
        for key in sorted(payload):
            if key in {"signature", "sign"}:
                continue
            value = payload[key]
            if value in (None, "") or isinstance(value, (list, dict)):
                continue
            sign_items.append(f"{key}={value}")
        sign_string = "&".join(sign_items) + f"&key={self.secret_key}"
        return hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()

    def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        data = self.signed_payload(payload)
        try:
            response = self.session.post(url, data=data, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Toumei GEO request failed: url={url}, reason={exc}") from exc
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Toumei GEO response is not JSON: url={url}, body={response.text[:300]}") from exc
        code = str(result.get("code", ""))
        if code and code != "200":
            raise RuntimeError(f"Toumei GEO API error {code}: {result.get('msg') or result}")
        return result
