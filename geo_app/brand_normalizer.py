from __future__ import annotations

import re
from typing import Any


def brand_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def canonicalize_brand_name(name: Any, alias_map: dict[str, str] | None = None) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    aliases = alias_map or {}
    return aliases.get(brand_key(raw), raw)


def build_brand_alias_map(profile: dict[str, Any], competitor_discovery: dict[str, Any] | None = None) -> dict[str, str]:
    alias_map: dict[str, str] = {}

    def add_alias(alias: Any, canonical: Any) -> None:
        key = brand_key(alias)
        value = str(canonical or "").strip()
        if key and value:
            alias_map[key] = value

    own = profile.get("brand_name") or profile.get("product_name") or ""
    for alias in [own, profile.get("product_name"), *(profile.get("brand_aliases") or [])]:
        add_alias(alias, own)

    for item in profile.get("known_competitor_hints") or []:
        if isinstance(item, str):
            add_alias(item, item)

    for values in (competitor_discovery or {}).values():
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, str):
                add_alias(item, item)
            elif isinstance(item, dict):
                canonical = item.get("brand_name") or item.get("name") or ""
                add_alias(canonical, canonical)
                for alias in item.get("aliases") or []:
                    add_alias(alias, canonical)

    # Common high-impact variants observed in Chinese local brand data.
    known_pairs = [
        ("唐末茶兮", "唐沫茶兮"),
        ("唐沫茶兮", "唐沫茶兮"),
        ("KOI Thé", "KOI Thé"),
        ("KOI", "KOI Thé"),
        ("1点点", "1点点"),
        ("一点点", "1点点"),
    ]
    for alias, canonical in known_pairs:
        add_alias(alias, canonical)
    return alias_map


def merge_brand_rows(rows: list[dict[str, Any]], alias_map: dict[str, str], count_field: str = "mentioned_count") -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        brand = canonicalize_brand_name(row.get("brand_name"), alias_map)
        key = brand_key(brand)
        if not key:
            continue
        if key not in grouped:
            grouped[key] = {**row, "brand_name": brand, "brand_key": key}
            continue
        target = grouped[key]
        target[count_field] = int(target.get(count_field) or 0) + int(row.get(count_field) or 0)
        target["result_count"] = int(target.get("result_count") or 0) + int(row.get("result_count") or 0)
        target["queries"] = [*(target.get("queries") or []), *(row.get("queries") or [])]
        target["query"] = ", ".join(dict.fromkeys([*(str(target.get("query") or "").split(", ")), str(row.get("query") or "")]))
        target["is_user_brand"] = bool(target.get("is_user_brand") or row.get("is_user_brand"))
    return list(grouped.values())
