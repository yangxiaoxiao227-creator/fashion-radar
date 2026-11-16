"""日本 WEAR（ZOZO）穿搭排行和趋势关键词。

WEAR 每张穿搭图的替代文字里写明了单品信息，格式类似：
「BRAND(ブランド)のアイテム名(カテゴリ、カラー系)」を使った、○○さん(レディース・160cm)の冬コーディネート
所以不需要识别图片，直接从文字里就能取出品类、颜色和季节。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..extract import norm_text

LABEL = "WEAR（日本）"

# 统一成半角括号后匹配：(カテゴリ、カラー系)
ITEM_RE = re.compile(r"\(([^()、]{1,30})、([^()]{1,20}?系)\)")
GENDER_RE = re.compile(r"\((レディース|メンズ|キッズ)(?:・(\d{2,3})cm)?\)")
SEASON_RE = re.compile(r"の(春|夏|秋|冬)コーディネート")
BRAND_RE = re.compile(r"^「?([^「」()]+?)(?:\([^()]*\))?の")


def parse_alt(alt: str) -> dict | None:
    """解析一条穿搭图替代文字。不是穿搭描述就返回 None。"""
    alt = norm_text(alt)
    if "コーディネート" not in alt and "を使った" not in alt:
        return None
    items = [{"category": c.strip(), "color": col.strip()} for c, col in ITEM_RE.findall(alt)]
    g = GENDER_RE.search(alt)
    s = SEASON_RE.search(alt)
    b = BRAND_RE.search(alt.lstrip("「"))
    return {
        "items": items,
        "gender": g.group(1) if g else "",
        "height": int(g.group(2)) if g and g.group(2) else None,
        "season": s.group(1) if s else "",
        "brand": norm_text(b.group(1)) if b else "",
    }


def parse_page(html: str, base: str, women_only: bool = True) -> tuple[list[dict], list[str]]:
    """返回（穿搭记录, 页面上的话题/关键词）。"""
    soup = BeautifulSoup(html, "lxml")
    coords, seen = [], set()
    for img in soup.find_all("img"):
        alt = img.get("alt") or ""
        info = parse_alt(alt)
        if not info:
            continue
        if women_only and info["gender"] and info["gender"] != "レディース":
            continue
        a = img.find_parent("a")
        href = urljoin(base, a.get("href")) if a and a.get("href") else ""
        key = href or alt
        if key in seen:
            continue
        seen.add(key)
        cats = "、".join(f"{i['category']}({i['color']})" for i in info["items"])
        coords.append(
            {
                "title": cats or norm_text(alt)[:80],
                "brand": info["brand"],
                "rank": len(coords) + 1,
                "url": href,
                "image": img.get("src") or img.get("data-src") or "",
                "price": None, "views": None, "posts": None, "growth": None,
                "season": info["season"],
                "height": info["height"],
                "wear_items": info["items"],
                "text": norm_text(alt),
            }
        )
    tags = []
    for el in soup.find_all(["a", "span", "h2", "h3"]):
        t = norm_text(el.get_text(" "))
        if t.startswith("#") and 2 <= len(t) <= 30 and t not in tags:
            tags.append(t)
    return coords, tags


def find_links(html: str, base: str) -> dict:
    """从首页导航里找"排行"和"趋势关键词"页面的地址，避免把网址写死。"""
    soup = BeautifulSoup(html, "lxml")
    ranking, keyword = [], []
    for a in soup.find_all("a", href=True):
        text = norm_text(a.get_text(" "))
        href = urljoin(base, a["href"])
        if "wear.jp" not in href:
            continue
        if "ランキング" in text or "/ranking" in href:
            ranking.append(href)
        if "トレンドキーワード" in text or "/keyword" in href:
            keyword.append(href)
    women_first = sorted(set(ranking), key=lambda u: (("women" not in u.lower()), len(u)))
    return {"ranking": women_first, "keyword": sorted(set(keyword), key=len)}


def parse_keyword_page(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    words = []
    for a in soup.find_all("a", href=True):
        if "/keyword" not in a["href"]:
            continue
        t = norm_text(a.get_text(" ")).lstrip("#")
        if 1 < len(t) <= 30 and t not in words and "キーワード" not in t:
            words.append(t)
    return words


def collect(session, cfg: dict) -> dict:
    pages, items = [], []
    home = session.open(cfg["home"], locale="ja-JP", scrolls=2, debug_name="wear_home")
    links = find_links(home.html, home.final_url) if home.html else {"ranking": [], "keyword": []}

    ranking_urls = []
    for u in cfg.get("extra_pages", []) + links["ranking"]:
        if u not in ranking_urls:
            ranking_urls.append(u)
    ranking_urls = ranking_urls[: cfg.get("max_ranking_pages", 3)]

    all_tags: list[str] = []
    for i, url in enumerate(ranking_urls):
        res = session.open(url, locale="ja-JP", debug_name=f"wear_ranking_{i}")
        coords, tags = parse_page(res.html, res.final_url, cfg.get("women_only", True)) if res.html else ([], [])
        for c in coords:
            c.update(market="JP", list_name="穿搭排行", kind="穿搭")
        items.extend(coords)
        all_tags += [t for t in tags if t not in all_tags]
        pages.append({"name": f"排行页 {i + 1}", "url": url, "count": len(coords), "method": "图片文字", "error": res.error})

    # 首页本身也有推荐穿搭，排行页都失败时用它兜底
    if not items and home.html:
        coords, tags = parse_page(home.html, home.final_url, cfg.get("women_only", True))
        for c in coords:
            c.update(market="JP", list_name="首页推荐", kind="穿搭")
        items.extend(coords)
        all_tags += [t for t in tags if t not in all_tags]
        pages.append({"name": "首页推荐（兜底）", "url": cfg["home"], "count": len(coords), "method": "图片文字", "error": home.error})

    keywords: list[str] = []
    if links["keyword"]:
        res = session.open(links["keyword"][0], locale="ja-JP", scrolls=1, debug_name="wear_keywords")
        keywords = parse_keyword_page(res.html) if res.html else []
        pages.append({"name": "趋势关键词", "url": links["keyword"][0], "count": len(keywords), "method": "关键词链接", "error": res.error})

    for t in all_tags + keywords:
        items.append(
            {
                "title": t.lstrip("#"), "brand": "", "rank": None, "url": "", "image": "",
                "price": None, "views": None, "posts": None, "growth": None,
                "market": "JP", "list_name": "话题与关键词", "kind": "关键词", "text": t,
            }
        )

    return {
        "source": "wear",
        "label": LABEL,
        "ok": any(i["kind"] == "穿搭" for i in items),
        "items": items,
        "pages": pages,
    }
