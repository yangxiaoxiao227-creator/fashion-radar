"""韩国 MUSINSA 女装榜单。

优先从页面加载时的接口 JSON 里取商品列表；取不到时，再从页面内嵌的
__NEXT_DATA__ 里找；最后退回到直接解析商品链接。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..extract import next_data, norm_text, records_from_json

LABEL = "MUSINSA（韩国）"


def collect(session, cfg: dict) -> dict:
    items, pages = [], []
    for p in cfg.get("pages", []):
        res = session.open(
            p["url"],
            locale="ko-KR",
            json_filter=lambda u: "musinsa" in u,
            debug_name=f"musinsa_{p['name']}",
        )
        rows, how = [], ""
        # 1) 接口 JSON：取条数最多、带品牌的那组
        for j in res.jsons:
            cand = records_from_json(j["body"], min_len=5, require_brand=True)
            if len(cand) > len(rows):
                rows, how = cand, "接口"
        # 2) 页面内嵌数据
        if not rows:
            nd = next_data(res.html)
            if nd:
                rows = records_from_json(nd, min_len=5, require_brand=True)
                how = "页面内嵌数据" if rows else how
        # 3) 直接解析商品链接
        if not rows and res.html:
            rows = _parse_links(res.html, res.final_url)
            how = "网页链接" if rows else how

        rows = rows[: cfg.get("max_items_per_page", 60)]
        for r in rows:
            r.update(
                market="KR",
                list_name=p["name"],
                kind="商品",
                url=urljoin("https://www.musinsa.com/", r["url"]) if r.get("url") else "",
                text=f"{r.get('brand', '')} {r['title']}",
            )
            if r.get("image", "").startswith("//"):
                r["image"] = "https:" + r["image"]
        items.extend(rows)
        pages.append({"name": p["name"], "url": p["url"], "count": len(rows), "method": how, "error": res.error})

    return {
        "source": "musinsa",
        "label": LABEL,
        "ok": len(items) > 0,
        "items": items,
        "pages": pages,
    }


def _parse_links(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()
    for a in soup.select('a[href*="/products/"], a[href*="/app/goods/"]'):
        href = a.get("href", "")
        m = re.search(r"/(?:products|goods)/(\d+)", href)
        if not m or m.group(1) in seen:
            continue
        text = norm_text(a.get_text(" "))
        img = a.find("img")
        alt = norm_text(img.get("alt")) if img else ""
        title = alt or text
        if len(title) < 3:
            continue
        seen.add(m.group(1))
        rows.append(
            {
                "title": title[:120],
                "brand": "",
                "rank": len(rows) + 1,
                "url": urljoin(base, href),
                "image": (img.get("src") or img.get("data-src") or "") if img else "",
                "price": None, "views": None, "posts": None, "growth": None,
            }
        )
    return rows
