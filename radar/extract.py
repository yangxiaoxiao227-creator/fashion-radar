"""从任意结构的 JSON 里找出"像榜单"的数据。

网站的接口格式经常变，字段名也各不相同。这里不写死路径，而是遍历整个 JSON，
找出由多个字典组成、且字典里有名称类字段的列表，再按候选字段名去取值。
接口改版时，只要字段名还在候选范围里，就不用改代码。
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterable

NAME_KEYS = (
    "productname", "goodsname", "itemname", "hashtagname", "hashtag_name",
    "keyword", "term", "query", "title", "name", "displayname",
)
BRAND_KEYS = ("brandname", "brand_name", "brand")
RANK_KEYS = ("rank", "ranking", "currentrank", "position")
URL_KEYS = ("linkurl", "producturl", "goodsurl", "detailurl", "url", "link", "landingurl")
IMAGE_KEYS = ("imageurl", "thumbnail", "thumbnailurl", "image", "img", "imgurl", "cover", "coverurl")
PRICE_KEYS = ("finalprice", "saleprice", "price", "normalprice")
VIEW_KEYS = ("video_views", "videoviews", "views", "viewcount")
POST_KEYS = ("publish_cnt", "publishcnt", "posts", "postcount", "post_count")
GROWTH_KEYS = ("growth", "pctgrowth", "weeklychange", "wow", "monthlychange", "yoy", "rate")


def norm_text(s: Any) -> str:
    """统一全角半角、去掉多余空白。"""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s).strip()


def flatten(d: dict, prefix: str = "", depth: int = 0, out: dict | None = None) -> dict:
    """把嵌套字典拍平成 {"info.brandName": ...}，只展开两层，避免把整页数据拍进去。"""
    out = {} if out is None else out
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and depth < 2:
            flatten(v, key + ".", depth + 1, out)
        elif not isinstance(v, (list, dict)):
            out[key] = v
    return out


def pick(flat: dict, candidates: Iterable[str], exclude: Iterable[str] = ()):
    """按候选名取值：先找最后一段完全同名的键，再找结尾相同的键。

    exclude 用来排除容易混淆的键，例如找商品链接时排除 image.url。
    """
    keys = [(k, k.lower(), v) for k, v in flat.items() if v not in (None, "")]
    keys = [t for t in keys if not any(x in t[1] for x in exclude)]
    for c in candidates:
        for _, kl, v in keys:
            if kl.split(".")[-1] == c:
                return v
    for c in candidates:
        cc = c.replace("_", "")
        for _, kl, v in keys:
            if kl.replace(".", "").replace("_", "").endswith(cc):
                return v
    return None


def walk_lists(obj: Any, depth: int = 0):
    """遍历 JSON，产出所有"由字典组成"的列表。"""
    if depth > 12:
        return
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if len(dicts) >= 2:
            yield dicts
        for x in obj:
            yield from walk_lists(x, depth + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_lists(v, depth + 1)


def records_from_json(body: Any, *, min_len: int = 3, require_brand: bool = False) -> list[dict]:
    """返回最像榜单的那一组记录（名称字段覆盖率最高、条数最多）。"""
    best: list[dict] = []
    best_score = 0.0
    for lst in walk_lists(body):
        if len(lst) < min_len:
            continue
        rows = []
        for d in lst:
            flat = flatten(d)
            name = pick(flat, NAME_KEYS, exclude=("brand", "user", "author", "nick", "shop", "category", "seller"))
            if not isinstance(name, (str, int, float)) or not norm_text(name):
                continue
            brand = pick(flat, BRAND_KEYS)
            if require_brand and not brand:
                continue
            rows.append(
                {
                    "title": norm_text(name),
                    "brand": norm_text(brand) if isinstance(brand, (str, int)) else "",
                    "rank": _to_int(pick(flat, RANK_KEYS)),
                    "url": _str_or_empty(pick(flat, URL_KEYS, exclude=("image", "img", "thumb", "cover", "avatar", "icon", "video"))),
                    "image": _str_or_empty(pick(flat, IMAGE_KEYS)),
                    "price": _to_int(pick(flat, PRICE_KEYS)),
                    "views": _to_int(pick(flat, VIEW_KEYS)),
                    "posts": _to_int(pick(flat, POST_KEYS)),
                    "growth": _to_float(pick(flat, GROWTH_KEYS)),
                    "raw_keys": sorted(flat.keys())[:40],
                }
            )
        coverage = len(rows) / len(lst)
        score = coverage * len(rows)
        if coverage >= 0.6 and score > best_score:
            best, best_score = rows, score
    for i, r in enumerate(best, 1):
        if r["rank"] is None:
            r["rank"] = i
    return best


def next_data(html: str) -> Any:
    """取出 Next.js 页面里内嵌的 __NEXT_DATA__ JSON（MUSINSA 等网站用）。"""
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _to_int(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return None


def _to_float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except Exception:
        return None


def _str_or_empty(v) -> str:
    return v if isinstance(v, str) else ""
