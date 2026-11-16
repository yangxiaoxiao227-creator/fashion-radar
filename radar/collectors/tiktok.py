"""TikTok Creative Center 热门话题（日本、韩国）。

限制：截至 2026 年下半年，Creative Center 对未登录访问者只公开每个榜单的前 3 名，
旧的数据接口对匿名请求返回"无权限"。所以这里能采到的话题很少，主要作为补充信号。
先尝试从页面接口 JSON 里取，取不到再从网页文字里找 # 开头的话题。
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..extract import norm_text, records_from_json

LABEL = "TikTok（日韩话题）"


def collect(session, cfg: dict) -> dict:
    items, pages = [], []
    for country in cfg.get("countries", []):
        for period in cfg.get("periods", [7]):
            rows, used_url, err, how = [], "", None, ""
            for tpl in cfg.get("page_templates", []):
                url = tpl.format(country=country, period=period)
                res = session.open(
                    url,
                    locale="en-US",
                    json_filter=lambda u: "tiktok" in u and ("hashtag" in u or "trend" in u),
                    debug_name=f"tiktok_{country}_{period}d_{len(pages)}",
                )
                used_url, err = url, res.error
                for j in res.jsons:
                    cand = records_from_json(j["body"], min_len=1)
                    cand = [c for c in cand if _looks_like_tag(c["title"])]
                    if len(cand) > len(rows):
                        rows, how = cand, "接口"
                if not rows and res.html:
                    rows = _tags_from_html(res.html)
                    how = "网页文字" if rows else ""
                if rows:
                    break
            for r in rows:
                tag = r["title"].lstrip("#")
                r.update(
                    title="#" + tag,
                    market=country,
                    list_name=f"{country} 近{period}天",
                    kind="话题",
                    url=r.get("url") or f"https://www.tiktok.com/tag/{tag}",
                    text=tag,
                )
            items.extend(rows)
            pages.append({"name": f"{country} 近{period}天", "url": used_url, "count": len(rows), "method": how, "error": err})

    return {
        "source": "tiktok",
        "label": LABEL,
        "ok": len(items) > 0,
        "items": items,
        "pages": pages,
        "note": "TikTok 匿名访问只公开每个榜单的前 3 名，条数少属正常。",
    }


def _looks_like_tag(s: str) -> bool:
    s = norm_text(s).lstrip("#")
    return 1 < len(s) <= 60 and " " not in s


def _tags_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")
    tags = []
    for m in re.finditer(r"#\s?([\w぀-ヿ一-鿿가-힯]{2,40})", text):
        t = m.group(1)
        if t not in tags:
            tags.append(t)
    return [
        {"title": t, "brand": "", "rank": i, "url": "", "image": "", "price": None,
         "views": None, "posts": None, "growth": None}
        for i, t in enumerate(tags[:20], 1)
    ]
