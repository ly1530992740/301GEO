from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geo_app.aizhan_client import AizhanClient
from geo_app.client_5118 import Client5118
from geo_app.toumei_geo_client import ToumeiGEOClient


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeResponse(self.payload)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return FakeResponse(self.payload)


def test_5118_longtail_decodes_and_normalizes() -> None:
    session = FakeSession(
        {
            "errcode": "0",
            "data": {
                "word": [
                    {
                        "keyword": "%E5%A5%B6%E8%8C%B6%E6%8E%A8%E8%8D%90",
                        "index": 123,
                        "mobile_index": 456,
                        "douyin_index": 7,
                        "bidword_pcpv": 8,
                        "bidword_wisepv": 9,
                    }
                ]
            },
        }
    )
    client = Client5118(api_key="k")
    client.session = session  # type: ignore[assignment]
    rows = client.longtail_keywords("奶茶")
    assert rows[0].keyword == "奶茶推荐"
    assert rows[0].pc_index == 123
    assert rows[0].mobile_index == 456
    assert session.calls[0]["url"].endswith("/keyword/word/v2")
    assert session.calls[0]["headers"]["Authorization"] == "k"


def test_5118_suggest_payload() -> None:
    session = FakeSession({"errcode": "0", "data": [{"word": "医美", "promote_word": "福州医美推荐", "platform": "baidu"}]})
    client = Client5118(api_key="k")
    client.session = session  # type: ignore[assignment]
    rows = client.suggest_words("医美", platform="baidu")
    assert rows[0].keyword == "福州医美推荐"
    assert session.calls[0]["data"] == {"word": "医美", "platform": "baidu"}


def test_5118_realtime_pc_rank_uses_morerank_endpoint() -> None:
    session = FakeSession({"errcode": "0", "data": {"taskid": 123}})
    client = Client5118(api_key="k")
    client.session = session  # type: ignore[assignment]
    taskid = client.submit_realtime_pc_rank("example.com", ["鍖荤編"], checkrow=50)
    assert taskid == "123"
    assert session.calls[0]["url"].endswith("/morerank/baidupc")
    assert session.calls[0]["data"] == {"url": "example.com", "keywords": "鍖荤編", "checkrow": 50}


def test_5118_realtime_pc_rank_normalizes_keywordmonitor() -> None:
    session = FakeSession(
        {
            "errcode": "0",
            "data": {
                "keywordmonitor": [
                    {
                        "keyword": "鍖荤編",
                        "ranks": [{"rank": 2, "page_title": "title", "page_url": "https://example.com/a"}],
                    }
                ]
            },
        }
    )
    client = Client5118(api_key="k")
    client.session = session  # type: ignore[assignment]
    rows = client.get_realtime_pc_rank("123")
    assert rows[0].keyword == "鍖荤編"
    assert rows[0].rank == 2
    assert session.calls[0]["url"].endswith("/morerank/baidupc")


def test_aizhan_related_words_url_and_normalize() -> None:
    session = FakeSession({"code": 200, "data": [{"related_word": "福州医美", "zhishu_pc": 10, "zhishu_wise": 20}]})
    client = AizhanClient(api_key="secret")
    client.session = session  # type: ignore[assignment]
    rows = client.related_words("医美")
    assert rows[0].keyword == "福州医美"
    assert rows[0].pc_index == 10
    assert rows[0].mobile_index == 20
    assert session.calls[0]["url"].endswith("/word/related/secret")
    assert session.calls[0]["data"]["word"] == "医美"


def test_aizhan_site_info_path() -> None:
    session = FakeSession({"code": 200, "data": {"domain": "example.com", "pc_br": 1}})
    client = AizhanClient(api_key="secret")
    client.session = session  # type: ignore[assignment]
    payload = client.site_info("example.com")
    assert payload["data"]["domain"] == "example.com"
    assert session.calls[0]["url"].endswith("/baidurank/siteinfos/secret")


def test_aizhan_accepts_200000_success_code() -> None:
    session = FakeSession({"code": 200000, "status": "success", "data": {"list": []}})
    client = AizhanClient(api_key="secret")
    client.session = session  # type: ignore[assignment]
    assert client.related_words("鍖荤編") == []


def test_toumei_signature_matches_document_example_shape() -> None:
    client = ToumeiGEOClient(secret_id="sid", secret_key="key")
    payload = {"a": 2, "c": 1, "b": 3, "secret_id": "sid", "timestamp": 1700000000}
    assert client.signature(payload) == "4531ACA31484A34BBED6C28F8F1E09B8"


def test_toumei_media_list_signed_payload() -> None:
    session = FakeSession({"code": 200, "msg": "ok", "data": []})
    client = ToumeiGEOClient(secret_id="sid", secret_key="key")
    client.session = session  # type: ignore[assignment]
    client.media_list(page=1, limit=20)
    call = session.calls[0]
    assert call["url"].endswith("/meijieapi/daili3/media_lst")
    assert call["data"]["secret_id"] == "sid"
    assert "timestamp" in call["data"]
    assert "signature" in call["data"]


if __name__ == "__main__":
    test_5118_longtail_decodes_and_normalizes()
    test_5118_suggest_payload()
    test_5118_realtime_pc_rank_uses_morerank_endpoint()
    test_5118_realtime_pc_rank_normalizes_keywordmonitor()
    test_aizhan_related_words_url_and_normalize()
    test_aizhan_site_info_path()
    test_aizhan_accepts_200000_success_code()
    test_toumei_signature_matches_document_example_shape()
    test_toumei_media_list_signed_payload()
    print("external client tests passed")
