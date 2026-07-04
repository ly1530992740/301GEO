from __future__ import annotations

import csv
import html
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import markdown_to_html, write_text


COLOR_PALETTE = ["#4285F4", "#DB4437", "#F4B400", "#0F9D58", "#AB47BC"]


def render_trend_outputs(
    trend_dir: Path,
    analysis_data: dict[str, Any],
    timeseries_raw: dict[str, Any],
    report_md: str,
) -> dict[str, str]:
    trend_dir.mkdir(parents=True, exist_ok=True)
    visual_data = build_visual_data(analysis_data, timeseries_raw)
    report_html = build_trend_html(analysis_data, visual_data, report_md)

    report_html_path = trend_dir / "trend_report.html"
    print_html_path = trend_dir / "trend_report_print.html"
    interest_csv_path = trend_dir / "interest_over_time.csv"
    monthly_csv_path = trend_dir / "monthly_interest.csv"
    related_csv_path = trend_dir / "related_queries.csv"
    geo_csv_path = trend_dir / "geo_interest.csv"
    visual_json_path = trend_dir / "visual_data.json"
    pdf_path = trend_dir / "trend_report.pdf"
    screenshot_path = trend_dir / "trend_report.png"

    write_text(report_html_path, report_html)
    write_text(print_html_path, report_html)
    write_text(visual_json_path, json.dumps(visual_data, ensure_ascii=False, indent=2))
    _write_csv(interest_csv_path, visual_data["interest_over_time"], ["date", "timestamp", "keyword", "value"])
    _write_csv(monthly_csv_path, visual_data["monthly_interest"], ["month", "keyword", "avg_value", "max_value", "points"])
    _write_csv(
        related_csv_path,
        visual_data["related_queries"],
        ["source_keyword", "query", "type", "value", "extracted_value"],
    )
    _write_csv(geo_csv_path, visual_data["geo_interest"], ["location", "keyword", "value", "extracted_value"])

    pdf_status = _try_export_browser_artifacts(report_html_path, pdf_path, screenshot_path)
    write_text(trend_dir / "pdf_export_status.json", json.dumps(pdf_status, ensure_ascii=False, indent=2))

    return {
        "report_html_path": str(report_html_path),
        "print_html_path": str(print_html_path),
        "visual_json_path": str(visual_json_path),
        "interest_csv_path": str(interest_csv_path),
        "monthly_csv_path": str(monthly_csv_path),
        "related_csv_path": str(related_csv_path),
        "geo_csv_path": str(geo_csv_path),
        "pdf_path": str(pdf_path) if pdf_path.exists() else "",
        "screenshot_path": str(screenshot_path) if screenshot_path.exists() else "",
        "pdf_status_path": str(trend_dir / "pdf_export_status.json"),
    }


def build_visual_data(analysis_data: dict[str, Any], timeseries_raw: dict[str, Any]) -> dict[str, Any]:
    interest_rows = normalize_interest_over_time(timeseries_raw)
    related_rows = normalize_related_queries(analysis_data.get("related_queries") or {})
    geo_rows = normalize_geo_interest(analysis_data.get("geo_map") or {})
    monthly_rows = build_monthly_interest(interest_rows)
    comparison_cards = build_comparison_cards(analysis_data, interest_rows, related_rows)
    return {
        "interest_over_time": interest_rows,
        "monthly_interest": monthly_rows,
        "related_queries": related_rows,
        "geo_interest": geo_rows,
        "comparison_cards": comparison_cards,
        "keyword_scores": analysis_data.get("keyword_scores") or [],
    }


def normalize_interest_over_time(timeseries_raw: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = (
        (timeseries_raw or {}).get("interest_over_time", {}).get("timeline_data")
        or (timeseries_raw or {}).get("timeline_data")
        or []
    )
    rows: list[dict[str, Any]] = []
    for point in timeline:
        date_label = str(point.get("date") or point.get("formattedTime") or "")
        timestamp = point.get("timestamp") or point.get("time") or ""
        for item in point.get("values") or []:
            keyword = str(item.get("query") or item.get("keyword") or item.get("name") or "").strip()
            value = item.get("extracted_value")
            if value is None:
                value = item.get("value")
            value = _to_number(value)
            if keyword and value is not None:
                rows.append(
                    {
                        "date": date_label,
                        "timestamp": str(timestamp),
                        "keyword": keyword,
                        "value": value,
                    }
                )
    return rows


def normalize_related_queries(related_queries: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_keyword, value in (related_queries or {}).items():
        if isinstance(value, list):
            for item in value:
                rows.append(
                    {
                        "source_keyword": source_keyword,
                        "query": item.get("query", ""),
                        "type": item.get("type", ""),
                        "value": item.get("value", ""),
                        "extracted_value": _to_number(item.get("extracted_value")),
                    }
                )
        elif isinstance(value, dict) and not value.get("error"):
            for group_name in ("rising", "top"):
                for item in value.get(group_name) or []:
                    rows.append(
                        {
                            "source_keyword": source_keyword,
                            "query": item.get("query") or item.get("title") or "",
                            "type": group_name,
                            "value": item.get("value", ""),
                            "extracted_value": _to_number(item.get("extracted_value")),
                        }
                    )
    return [row for row in rows if row.get("query")]


def normalize_geo_interest(geo_map: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(geo_map, dict) or geo_map.get("error"):
        return []
    candidates = (
        geo_map.get("compared_breakdown_by_region")
        or geo_map.get("interest_by_region")
        or geo_map.get("geo_map")
        or geo_map.get("regions")
        or []
    )
    rows: list[dict[str, Any]] = []
    for item in candidates:
        location = (
            item.get("location")
            or item.get("geo")
            or item.get("name")
            or item.get("region")
            or item.get("title")
            or ""
        )
        values = item.get("values")
        if isinstance(values, list):
            for value_item in values:
                rows.append(
                    {
                        "location": location,
                        "keyword": value_item.get("query") or value_item.get("keyword") or "",
                        "value": value_item.get("value", ""),
                        "extracted_value": _to_number(value_item.get("extracted_value")),
                    }
                )
        else:
            rows.append(
                {
                    "location": location,
                    "keyword": item.get("query") or item.get("keyword") or "",
                    "value": item.get("value", ""),
                    "extracted_value": _to_number(item.get("extracted_value") or item.get("value")),
                }
            )
    return [row for row in rows if row.get("location")]


def build_monthly_interest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        month = _month_from_row(row)
        value = _to_number(row.get("value"))
        if month and value is not None:
            buckets[(month, row["keyword"])].append(float(value))
    result = []
    for (month, keyword), values in sorted(buckets.items()):
        result.append(
            {
                "month": month,
                "keyword": keyword,
                "avg_value": round(sum(values) / len(values), 2),
                "max_value": max(values),
                "points": len(values),
            }
        )
    return result


def build_comparison_cards(
    analysis_data: dict[str, Any],
    interest_rows: list[dict[str, Any]],
    related_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    recent_grouped: dict[str, list[float]] = defaultdict(list)
    by_keyword_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in interest_rows:
        value = _to_number(row.get("value"))
        if value is None:
            continue
        grouped[row["keyword"]].append(float(value))
        by_keyword_rows[row["keyword"]].append(row)
    for keyword, rows in by_keyword_rows.items():
        for row in rows[-4:]:
            value = _to_number(row.get("value"))
            if value is not None:
                recent_grouped[keyword].append(float(value))

    related_counts = defaultdict(int)
    for row in related_rows:
        related_counts[row.get("source_keyword", "")] += 1

    cards = []
    for keyword in analysis_data.get("trend_keywords") or grouped.keys():
        values = grouped.get(keyword, [])
        recent = recent_grouped.get(keyword, [])
        cards.append(
            {
                "keyword": keyword,
                "avg_heat": round(sum(values) / len(values), 2) if values else 0,
                "peak_heat": max(values) if values else 0,
                "recent_heat": round(sum(recent) / len(recent), 2) if recent else 0,
                "related_query_count": related_counts.get(keyword, 0),
            }
        )
    return cards


def build_trend_html(analysis_data: dict[str, Any], visual_data: dict[str, Any], report_md: str) -> str:
    input_data = analysis_data.get("input") or {}
    title = f"{input_data.get('seed_keyword', 'Trend Report')} - Google Trends 可视化报告"
    plotly_script = _plotly_script_tag()
    interest_json = json.dumps(visual_data["interest_over_time"], ensure_ascii=False)
    related_json = json.dumps(visual_data["related_queries"], ensure_ascii=False)
    geo_json = json.dumps(visual_data["geo_interest"], ensure_ascii=False)
    monthly_json = json.dumps(visual_data["monthly_interest"], ensure_ascii=False)
    cards_html = _comparison_cards_html(visual_data["comparison_cards"])
    related_top_html = _related_table_html(visual_data["related_queries"], "top")
    related_rising_html = _related_table_html(visual_data["related_queries"], "rising")
    geo_table_html = _geo_table_html(visual_data["geo_interest"])
    keyword_scores_html = _keyword_scores_html(visual_data["keyword_scores"])
    search_queries_html = "".join(f"<li>{html.escape(item)}</li>" for item in analysis_data.get("search_queries") or [])
    report_html = markdown_to_html(report_md)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  {plotly_script}
  <style>
    :root {{
      --bg: #f8fafc;
      --panel: #ffffff;
      --border: #e5e7eb;
      --text: #111827;
      --muted: #6b7280;
      --blue: #2563eb;
      --green: #059669;
      --amber: #d97706;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, "Microsoft YaHei", sans-serif;
      color: var(--text);
      background: var(--bg);
    }}
    .page {{ max-width: 1200px; margin: 0 auto; padding: 28px; }}
    .hero {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 20px; }}
    h1 {{ font-size: 30px; margin: 0 0 10px; letter-spacing: 0; }}
    h2 {{ font-size: 20px; margin: 0 0 14px; }}
    .sub {{ color: var(--muted); line-height: 1.6; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .btn {{
      border: 1px solid var(--border);
      background: white;
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--text);
      text-decoration: none;
      cursor: pointer;
      font-size: 14px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .card .label {{ color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    .card .value {{ font-size: 24px; font-weight: 700; }}
    .card .hint {{ color: var(--muted); font-size: 12px; margin-top: 8px; }}
    .panel {{ margin-top: 14px; }}
    .chart {{ width: 100%; height: 430px; }}
    .chart.small {{ height: 360px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; background: #f9fafb; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 3px 8px; background: #eef2ff; color: #3730a3; font-size: 12px; }}
    .note {{ color: var(--muted); font-size: 13px; line-height: 1.7; }}
    .md-body {{ line-height: 1.72; }}
    .md-body table {{ margin: 12px 0; }}
    .empty {{ color: var(--muted); padding: 18px; border: 1px dashed var(--border); border-radius: 8px; }}
    @media (max-width: 900px) {{ .grid, .two-col {{ grid-template-columns: 1fr; }} .hero {{ display: block; }} }}
    @media print {{
      body {{ background: white; }}
      .actions {{ display: none; }}
      .page {{ max-width: none; padding: 16px; }}
      .panel, .card {{ box-shadow: none; break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <h1>Google Trends 可视化报告</h1>
        <div class="sub">
          <strong>{html.escape(str(input_data.get("seed_keyword", "")))}</strong><br>
          地区：{html.escape(str(input_data.get("city", "")))} / {html.escape(str(input_data.get("trend_date", "")))}<br>
          行业：{html.escape(str(input_data.get("industry", "")))}　客户：{html.escape(str(input_data.get("customer_product", "")))}
        </div>
      </div>
      <div class="actions">
        <button class="btn" onclick="window.print()">打印 / 导出 PDF</button>
        <a class="btn" href="interest_over_time.csv">热度 CSV</a>
        <a class="btn" href="related_queries.csv">相关查询 CSV</a>
        <a class="btn" href="monthly_interest.csv">月度 CSV</a>
        <a class="btn" href="trend_data.json">完整 JSON</a>
      </div>
    </div>

    <div class="grid">{cards_html}</div>

    <section class="panel">
      <h2>热度随时间变化</h2>
      <div id="interestChart" class="chart"></div>
      <p class="note">数值为 Google Trends 相对热度，0-100 表示指定地区和时间范围内的相对搜索兴趣，不等于真实搜索量。</p>
    </section>

    <section class="panel">
      <h2>月度趋势对比</h2>
      <div id="monthlyChart" class="chart small"></div>
    </section>

    <section class="panel">
      <h2>搜索这个词的用户还搜索了这些查询内容</h2>
      <div class="two-col">
        <div>
          <h3>热门查询 Top queries</h3>
          {related_top_html}
        </div>
        <div>
          <h3>上升查询 Rising queries</h3>
          {related_rising_html}
        </div>
      </div>
      <div id="relatedChart" class="chart small"></div>
    </section>

    <section class="panel">
      <h2>地域热度</h2>
      <div id="geoChart" class="chart small"></div>
      {geo_table_html}
    </section>

    <section class="panel">
      <h2>关键词机会评分</h2>
      {keyword_scores_html}
    </section>

    <section class="panel">
      <h2>本次用于 SERP 分析的搜索查询</h2>
      <ul>{search_queries_html}</ul>
    </section>

    <section class="panel">
      <h2>策略摘要</h2>
      <div class="md-body">{report_html}</div>
    </section>
  </div>

  <script>
    const interestRows = {interest_json};
    const relatedRows = {related_json};
    const geoRows = {geo_json};
    const monthlyRows = {monthly_json};
    const colors = {json.dumps(COLOR_PALETTE)};

    function grouped(rows, key) {{
      return rows.reduce((acc, row) => {{
        const k = row[key] || "";
        if (!acc[k]) acc[k] = [];
        acc[k].push(row);
        return acc;
      }}, {{}});
    }}

    function renderInterest() {{
      const byKeyword = grouped(interestRows, "keyword");
      const traces = Object.entries(byKeyword).map(([keyword, rows], idx) => ({{
        x: rows.map(r => r.date || r.timestamp),
        y: rows.map(r => r.value),
        mode: "lines",
        name: keyword,
        line: {{ width: 3, color: colors[idx % colors.length] }},
        hovertemplate: "%{{x}}<br>" + keyword + ": %{{y}}<extra></extra>"
      }}));
      Plotly.newPlot("interestChart", traces, {{
        margin: {{ l: 48, r: 20, t: 18, b: 42 }},
        yaxis: {{ range: [0, 100], title: "Search interest" }},
        xaxis: {{ title: "" }},
        legend: {{ orientation: "h" }},
        paper_bgcolor: "white",
        plot_bgcolor: "white"
      }}, {{ responsive: true, displaylogo: false }});
    }}

    function renderMonthly() {{
      const byKeyword = grouped(monthlyRows, "keyword");
      const traces = Object.entries(byKeyword).map(([keyword, rows], idx) => ({{
        x: rows.map(r => r.month),
        y: rows.map(r => r.avg_value),
        type: "bar",
        name: keyword,
        marker: {{ color: colors[idx % colors.length] }},
        hovertemplate: "%{{x}}<br>" + keyword + ": %{{y}}<extra></extra>"
      }}));
      Plotly.newPlot("monthlyChart", traces, {{
        barmode: "group",
        margin: {{ l: 48, r: 20, t: 18, b: 42 }},
        yaxis: {{ range: [0, 100], title: "Monthly avg" }},
        paper_bgcolor: "white",
        plot_bgcolor: "white"
      }}, {{ responsive: true, displaylogo: false }});
    }}

    function renderRelated() {{
      const rows = relatedRows.filter(r => typeof r.extracted_value === "number").slice(0, 20);
      const y = rows.map(r => r.query).reverse();
      const x = rows.map(r => r.extracted_value).reverse();
      const text = rows.map(r => r.source_keyword).reverse();
      Plotly.newPlot("relatedChart", [{{
        x, y, text,
        type: "bar",
        orientation: "h",
        marker: {{ color: "#4285F4" }},
        hovertemplate: "%{{y}}<br>Value: %{{x}}<br>%{{text}}<extra></extra>"
      }}], {{
        margin: {{ l: 180, r: 20, t: 18, b: 42 }},
        xaxis: {{ title: "Relative value / growth" }},
        paper_bgcolor: "white",
        plot_bgcolor: "white"
      }}, {{ responsive: true, displaylogo: false }});
    }}

    function renderGeo() {{
      const rows = geoRows.filter(r => typeof r.extracted_value === "number").slice(0, 20);
      Plotly.newPlot("geoChart", [{{
        x: rows.map(r => r.extracted_value),
        y: rows.map(r => r.location).reverse(),
        type: "bar",
        orientation: "h",
        marker: {{ color: "#0F9D58" }},
        hovertemplate: "%{{y}}<br>Value: %{{x}}<extra></extra>"
      }}], {{
        margin: {{ l: 160, r: 20, t: 18, b: 42 }},
        xaxis: {{ range: [0, 100], title: "Regional interest" }},
        paper_bgcolor: "white",
        plot_bgcolor: "white"
      }}, {{ responsive: true, displaylogo: false }});
    }}

    if (interestRows.length) renderInterest(); else document.getElementById("interestChart").innerHTML = '<div class="empty">暂无热度随时间变化数据。</div>';
    if (monthlyRows.length) renderMonthly(); else document.getElementById("monthlyChart").innerHTML = '<div class="empty">暂无月度趋势数据。</div>';
    if (relatedRows.length) renderRelated(); else document.getElementById("relatedChart").innerHTML = '<div class="empty">暂无相关查询图表数据。</div>';
    if (geoRows.length) renderGeo(); else document.getElementById("geoChart").innerHTML = '<div class="empty">暂无地域热度数据。</div>';
  </script>
</body>
</html>"""


def _plotly_script_tag() -> str:
    try:
        from plotly.offline import get_plotlyjs

        return f"<script>{get_plotlyjs()}</script>"
    except Exception:
        return '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'


def _comparison_cards_html(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return '<div class="card"><div class="label">关键词</div><div class="value">暂无数据</div></div>'
    html_parts = []
    for card in cards[:5]:
        html_parts.append(
            f"""
<div class="card">
  <div class="label">{html.escape(str(card.get("keyword", "")))}</div>
  <div class="value">{card.get("avg_heat", 0)}</div>
  <div class="hint">平均热度 / 峰值 {card.get("peak_heat", 0)} / 相关查询 {card.get("related_query_count", 0)}</div>
</div>"""
        )
    return "\n".join(html_parts)


def _related_table_html(rows: list[dict[str, Any]], row_type: str) -> str:
    filtered = [row for row in rows if row.get("type") == row_type][:15]
    if not filtered:
        return '<div class="empty">暂无数据</div>'
    body = []
    for idx, row in enumerate(filtered, start=1):
        body.append(
            f"<tr><td>{idx}</td><td>{html.escape(str(row.get('query', '')))}</td>"
            f"<td>{html.escape(str(row.get('value', '') or row.get('extracted_value', '')))}</td>"
            f"<td>{html.escape(str(row.get('source_keyword', '')))}</td></tr>"
        )
    return "<table><thead><tr><th>#</th><th>查询</th><th>热度/涨幅</th><th>来源词</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _geo_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">暂无地域热度表格数据</div>'
    body = []
    for idx, row in enumerate(rows[:20], start=1):
        body.append(
            f"<tr><td>{idx}</td><td>{html.escape(str(row.get('location', '')))}</td>"
            f"<td>{html.escape(str(row.get('keyword', '')))}</td>"
            f"<td>{html.escape(str(row.get('value', '') or row.get('extracted_value', '')))}</td></tr>"
        )
    return "<table><thead><tr><th>#</th><th>地区</th><th>关键词</th><th>热度</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _keyword_scores_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">暂无关键词评分数据</div>'
    body = []
    for row in rows[:20]:
        body.append(
            f"<tr><td>{html.escape(str(row.get('keyword', '')))}</td>"
            f"<td>{row.get('trend_score', '')}</td><td>{row.get('growth_score', '')}</td>"
            f"<td>{row.get('commercial_score', '')}</td><td>{row.get('local_score', '')}</td>"
            f"<td>{row.get('final_score', '')}</td><td>{html.escape(str(row.get('reason', '')))}</td></tr>"
        )
    return "<table><thead><tr><th>关键词</th><th>趋势分</th><th>增长</th><th>商业</th><th>本地</th><th>综合</th><th>说明</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _try_export_browser_artifacts(html_path: Path, pdf_path: Path, screenshot_path: Path) -> dict[str, Any]:
    browser = _find_browser_executable()
    if browser:
        try:
            uri = html_path.resolve().as_uri()
            subprocess.run(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--print-to-pdf={pdf_path.resolve()}",
                    uri,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            subprocess.run(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--window-size=1440,1400",
                    f"--screenshot={screenshot_path.resolve()}",
                    uri,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            return {
                "ok": True,
                "method": "system_browser_headless",
                "browser": browser,
                "pdf_path": str(pdf_path) if pdf_path.exists() else "",
                "screenshot_path": str(screenshot_path) if screenshot_path.exists() else "",
            }
        except Exception as exc:
            browser_error = str(exc)
    else:
        browser_error = "No Edge/Chrome executable found."

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
        return {
            "ok": True,
            "method": "python_playwright",
            "pdf_path": str(pdf_path) if pdf_path.exists() else "",
            "screenshot_path": str(screenshot_path) if screenshot_path.exists() else "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": str(exc),
            "system_browser_error": browser_error,
            "note": "未安装 Python Playwright 或浏览器时会跳过自动 PDF。可直接打开 trend_report.html 后使用浏览器打印为 PDF。",
        }


def _find_browser_executable() -> str:
    candidates = [
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("chromium"),
        shutil.which("chromium.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return ""


def _month_from_row(row: dict[str, Any]) -> str:
    timestamp = str(row.get("timestamp") or "")
    if timestamp.isdigit():
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m")
    date_label = str(row.get("date") or "")
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_label, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    if len(date_label) >= 7 and date_label[4] in {"-", "/"}:
        return date_label[:7].replace("/", "-")
    return date_label[:7]


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "").replace("+", "")
    if not text:
        return None
    if text.lower() == "breakout":
        return 5000.0
    try:
        return float(text)
    except ValueError:
        return None
