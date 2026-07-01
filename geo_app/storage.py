from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .config import DB_PATH, ensure_dirs
from .utils import parse_price, utc_now_iso


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        ensure_dirs()
        self.db_path = db_path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        with self._lock:
            self.conn.execute("pragma journal_mode=wal")
            self.conn.executescript(
                """
                create table if not exists tasks (
                    id text primary key,
                    keyword text not null,
                    customer_product text not null,
                    status text not null default 'draft',
                    search_count integer not null default 3,
                    links_per_search integer not null default 10,
                    query_templates text,
                    task_dir text,
                    format_md_path text,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists search_results (
                    id integer primary key autoincrement,
                    task_id text not null,
                    run_index integer not null,
                    query text not null,
                    rank integer,
                    site_name text,
                    title text,
                    url text,
                    domain text,
                    raw_json text,
                    created_at text not null
                );

                create table if not exists media_resources (
                    id integer primary key autoincrement,
                    resource_type text not null,
                    resource_id integer not null,
                    title text,
                    case_link text,
                    entrance_link text,
                    price_1 real default 0,
                    price_2 real default 0,
                    price_3 real default 0,
                    remarks text,
                    raw_json text,
                    fetched_at text not null,
                    unique(resource_type, resource_id)
                );

                create table if not exists platform_matches (
                    id integer primary key autoincrement,
                    task_id text not null,
                    source_site_name text,
                    source_domain text,
                    source_url text,
                    link_count integer not null default 1,
                    resource_type text,
                    resource_id integer,
                    resource_title text,
                    case_link text,
                    entrance_link text,
                    price_1 real default 0,
                    price_2 real default 0,
                    price_3 real default 0,
                    match_type text not null,
                    confidence real default 0,
                    confirmed integer not null default 0,
                    warning text,
                    raw_resource_json text,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists articles (
                    id integer primary key autoincrement,
                    task_id text not null,
                    platform_match_id integer,
                    resource_type text,
                    resource_id integer,
                    resource_title text,
                    title text,
                    content_md text,
                    content_html text,
                    file_path text,
                    article_id integer,
                    order_id text,
                    publish_status integer,
                    link text,
                    refund_info text,
                    rejection_info text,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists trend_reports (
                    id integer primary key autoincrement,
                    task_id text,
                    city text,
                    industry text,
                    seed_keyword text,
                    report_md text,
                    raw_json text,
                    file_path text,
                    created_at text not null
                );

                create table if not exists trend_keywords (
                    id integer primary key autoincrement,
                    task_id text,
                    keyword text not null,
                    trend_score real default 0,
                    growth_score real default 0,
                    commercial_score real default 0,
                    local_score real default 0,
                    final_score real default 0,
                    reason text,
                    raw_json text,
                    created_at text not null
                );
                """
            )
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def get_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def upsert_task(self, task: dict[str, Any]) -> None:
        now = utc_now_iso()
        self.execute(
            """
            insert into tasks (
                id, keyword, customer_product, status, search_count, links_per_search,
                query_templates, task_dir, format_md_path, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
                keyword=excluded.keyword,
                customer_product=excluded.customer_product,
                status=excluded.status,
                search_count=excluded.search_count,
                links_per_search=excluded.links_per_search,
                query_templates=excluded.query_templates,
                task_dir=excluded.task_dir,
                format_md_path=excluded.format_md_path,
                updated_at=excluded.updated_at
            """,
            (
                task["id"],
                task["keyword"],
                task["customer_product"],
                task.get("status", "draft"),
                task.get("search_count", 3),
                task.get("links_per_search", 10),
                task.get("query_templates", ""),
                task.get("task_dir", ""),
                task.get("format_md_path", ""),
                task.get("created_at", now),
                now,
            ),
        )

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{key}=?" for key in fields)
        self.execute(
            f"update tasks set {assignments} where id=?",
            tuple(fields.values()) + (task_id,),
        )

    def add_search_results(self, task_id: str, run_index: int, query: str, results: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        for item in results:
            self.execute(
                """
                insert into search_results (
                    task_id, run_index, query, rank, site_name, title, url, domain, raw_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    run_index,
                    query,
                    item.get("rank"),
                    item.get("site_name", ""),
                    item.get("title", ""),
                    item.get("url", ""),
                    item.get("domain", ""),
                    json.dumps(item, ensure_ascii=False),
                    now,
                ),
            )

    def clear_task_matches(self, task_id: str) -> None:
        self.execute("delete from platform_matches where task_id=?", (task_id,))

    def add_platform_match(self, item: dict[str, Any]) -> int:
        now = utc_now_iso()
        cur = self.execute(
            """
            insert into platform_matches (
                task_id, source_site_name, source_domain, source_url, link_count,
                resource_type, resource_id, resource_title, case_link, entrance_link,
                price_1, price_2, price_3, match_type, confidence, confirmed, warning,
                raw_resource_json, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["task_id"],
                item.get("source_site_name", ""),
                item.get("source_domain", ""),
                item.get("source_url", ""),
                item.get("link_count", 1),
                item.get("resource_type", ""),
                item.get("resource_id"),
                item.get("resource_title", ""),
                item.get("case_link", ""),
                item.get("entrance_link", ""),
                item.get("price_1", 0.0),
                item.get("price_2", 0.0),
                item.get("price_3", 0.0),
                item.get("match_type", "unmatched"),
                item.get("confidence", 0.0),
                1 if item.get("confirmed") else 0,
                item.get("warning", ""),
                json.dumps(item.get("raw_resource", {}), ensure_ascii=False),
                now,
                now,
            ),
        )
        return int(cur.lastrowid)

    def update_match_confirmation(self, match_ids: list[int], confirmed: bool) -> None:
        if not match_ids:
            return
        placeholders = ",".join("?" for _ in match_ids)
        self.execute(
            f"update platform_matches set confirmed=?, updated_at=? where id in ({placeholders})",
            (1 if confirmed else 0, utc_now_iso(), *match_ids),
        )

    def upsert_media_resources(self, resource_type: str, resources: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        for item in resources:
            self.execute(
                """
                insert into media_resources (
                    resource_type, resource_id, title, case_link, entrance_link,
                    price_1, price_2, price_3, remarks, raw_json, fetched_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(resource_type, resource_id) do update set
                    title=excluded.title,
                    case_link=excluded.case_link,
                    entrance_link=excluded.entrance_link,
                    price_1=excluded.price_1,
                    price_2=excluded.price_2,
                    price_3=excluded.price_3,
                    remarks=excluded.remarks,
                    raw_json=excluded.raw_json,
                    fetched_at=excluded.fetched_at
                """,
                (
                    resource_type,
                    item.get("resource_id"),
                    item.get("title", ""),
                    item.get("case_link", ""),
                    item.get("entrance_link", ""),
                    parse_price(item.get("price_1")),
                    parse_price(item.get("price_2")),
                    parse_price(item.get("price_3")),
                    item.get("remarks", ""),
                    json.dumps(item, ensure_ascii=False),
                    now,
                ),
            )

    def add_article(self, item: dict[str, Any]) -> int:
        now = utc_now_iso()
        cur = self.execute(
            """
            insert into articles (
                task_id, platform_match_id, resource_type, resource_id, resource_title,
                title, content_md, content_html, file_path, publish_status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["task_id"],
                item.get("platform_match_id"),
                item.get("resource_type", ""),
                item.get("resource_id"),
                item.get("resource_title", ""),
                item.get("title", ""),
                item.get("content_md", ""),
                item.get("content_html", ""),
                item.get("file_path", ""),
                item.get("publish_status"),
                now,
                now,
            ),
        )
        return int(cur.lastrowid)

    def update_article(self, row_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{key}=?" for key in fields)
        self.execute(
            f"update articles set {assignments} where id=?",
            tuple(fields.values()) + (row_id,),
        )

    def add_trend_report(self, item: dict[str, Any]) -> int:
        now = utc_now_iso()
        cur = self.execute(
            """
            insert into trend_reports (
                task_id, city, industry, seed_keyword, report_md, raw_json, file_path, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.get("task_id", ""),
                item.get("city", ""),
                item.get("industry", ""),
                item.get("seed_keyword", ""),
                item.get("report_md", ""),
                json.dumps(item.get("raw_json", {}), ensure_ascii=False),
                item.get("file_path", ""),
                now,
            ),
        )
        return int(cur.lastrowid)

    def replace_trend_keywords(self, task_id: str, items: list[dict[str, Any]]) -> None:
        self.execute("delete from trend_keywords where task_id=?", (task_id,))
        now = utc_now_iso()
        for item in items:
            self.execute(
                """
                insert into trend_keywords (
                    task_id, keyword, trend_score, growth_score, commercial_score,
                    local_score, final_score, reason, raw_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    item.get("keyword", ""),
                    item.get("trend_score", 0),
                    item.get("growth_score", 0),
                    item.get("commercial_score", 0),
                    item.get("local_score", 0),
                    item.get("final_score", 0),
                    item.get("reason", ""),
                    json.dumps(item, ensure_ascii=False),
                    now,
                ),
            )
