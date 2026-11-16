"""Pinterest Trends 增长中的搜索词。

Pinterest 没有免登录的公开接口，这里打开趋势页面并记录页面加载时的 JSON。
日本目前很可能没有数据，韩国待验证，美国作为全球参照。
Pinterest 的词覆盖所有领域，只保留能对上服饰词典的词（在 analyze 里过滤）。
"""
from __future__ import annotations

from ..extract import records_from_json

LABEL = "Pinterest（趋势搜索词）"


def collect(session, cfg: dict) -> dict:
    items, pages = [], []
    for country in cfg.get("countries", []):
        url = cfg["page_template"].format(country=country)
        res = session.open(
            url,
            locale="en-US",
            wait_ms=8000,
            json_filter=lambda u: "pinterest" in u,
            debug_name=f"pinterest_{country}",
        )
        rows = []
        for j in res.jsons:
            cand = records_from_json(j["body"], min_len=5)
            if len(cand) > len(rows):
                rows = cand
        for r in rows:
            r.update(market=country, list_name=f"{country} 增长中", kind="搜索词", text=r["title"])
        items.extend(rows)
        note = ""
        if not rows and "login" in (res.final_url or "").lower():
            note = "被跳转到登录页"
        pages.append({"name": f"{country} 增长中", "url": url, "count": len(rows), "method": "接口" if rows else "", "error": res.error or note or None})

    return {
        "source": "pinterest",
        "label": LABEL,
        "ok": len(items) > 0,
        "items": items,
        "pages": pages,
        "note": "只保留服饰相关的词；未采到通常是 Pinterest 要求登录或该国家没有数据。",
    }
