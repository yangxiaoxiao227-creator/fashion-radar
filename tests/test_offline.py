"""离线测试：用模拟的网页和接口数据检查解析、打分和报告生成。

运行：python -m pytest -q
不需要联网，也不需要安装浏览器。
"""
import json
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from radar import analyze, report
from radar.browser import PageResult
from radar.collectors import musinsa, pinterest, tiktok, wear
from radar.extract import records_from_json
from radar.glossary import match_terms

FIX = Path(__file__).parent / "fixtures"


class FakeSession:
    """按网址关键词返回预先准备好的页面，代替真实浏览器。"""

    def __init__(self, routes):
        self.routes = routes
        self.opened = []

    def open(self, url, **kw):
        self.opened.append(url)
        for key, (html, jsons) in self.routes.items():
            if key in url:
                return PageResult(url, html, jsons, url)
        return PageResult(url, "", [], url, error="TimeoutError: not in fixtures")


MUSINSA_JSON = {
    "data": {
        "modules": [
            {"type": "BANNER", "items": [{"title": "광고"}]},
            {
                "type": "PRODUCT_LIST",
                "items": [
                    {
                        "id": str(1000 + i),
                        "info": {"brandName": b, "productName": n, "finalPrice": p},
                        "image": {"url": f"https://image.msscdn.net/{i}.jpg"},
                        "onClick": {"url": f"https://www.musinsa.com/products/{1000 + i}"},
                    }
                    for i, (b, n, p) in enumerate(
                        [
                            ("마르디 메크르디", "울 블렌드 워크 재킷 차콜", 129000),
                            ("디미트리블랙", "와이드 데님 팬츠 블랙", 59000),
                            ("트래블", "레더 재킷 브라운", 189000),
                            ("무신사 스탠다드", "캐시미어 머플러 버건디", 39000),
                            ("드로우핏", "숏패딩 민트", 159000),
                            ("스파오", "부츠컷 데님 팬츠", 39900),
                        ]
                    )
                ],
            },
        ]
    }
}

TIKTOK_JSON = {
    "code": 0,
    "data": {
        "list": [
            {"hashtag_name": "韓国ファッション", "rank": 1, "publish_cnt": 1200, "video_views": 3400000},
            {"hashtag_name": "冬コーデ", "rank": 2, "publish_cnt": 900, "video_views": 2100000},
            {"hashtag_name": "leatherjacket", "rank": 3, "publish_cnt": 300, "video_views": 800000},
        ]
    },
}

PINTEREST_JSON = {
    "resource_response": {
        "data": [
            {"term": "leather jacket outfit", "pctGrowth": "+120%"},
            {"term": "christmas cookies", "pctGrowth": "+300%"},
            {"term": "burgundy scarf", "pctGrowth": "+80%"},
            {"term": "nail ideas", "pctGrowth": "+50%"},
            {"term": "wide leg jeans", "pctGrowth": "+40%"},
            {"term": "pasta recipe", "pctGrowth": "+10%"},
        ]
    }
}


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def wear_html():
    return (FIX / "wear_ranking.html").read_text(encoding="utf-8")


def all_results():
    s = FakeSession(
        {
            "musinsa.com": ("<html></html>", [{"url": "https://api.musinsa.com/x", "status": 200, "body": MUSINSA_JSON}]),
            "wear.jp/ranking": (wear_html(), []),
            "wear.jp/keyword": ((FIX / "wear_keywords.html").read_text(encoding="utf-8"), []),
            "wear.jp/": ((FIX / "wear_home.html").read_text(encoding="utf-8"), []),
            "tiktok.com": ("<html></html>", [{"url": "https://ads.tiktok.com/api/hashtag/list", "status": 200, "body": TIKTOK_JSON}]),
            "pinterest.com": ("<html></html>", [{"url": "https://trends.pinterest.com/api", "status": 200, "body": PINTEREST_JSON}]),
        }
    )
    cfg = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8"))["sources"]
    return [
        musinsa.collect(s, cfg["musinsa"]),
        wear.collect(s, cfg["wear"]),
        tiktok.collect(s, cfg["tiktok"]),
        pinterest.collect(s, cfg["pinterest"]),
    ]


def test_glossary_prefers_longer_words():
    assert match_terms("트렌치코트 베이지") == ["风衣", "米色/卡其"]
    assert "大衣（泛指）" not in match_terms("트렌치코트")
    assert match_terms("ワイドパンツ") == ["阔腿裤"]
    assert match_terms("wide leg jeans") == ["阔腿裤", "牛仔裤"]
    assert match_terms("capri pants") == ["七分裤/卡普里裤"]  # "cap" 不能误判成棒球帽
    assert match_terms("서울 여행") == []  # "울" 不能误判成羊毛


def test_records_from_json_picks_product_list():
    rows = records_from_json(MUSINSA_JSON, min_len=5, require_brand=True)
    assert len(rows) == 6
    assert rows[0]["brand"] == "마르디 메크르디"
    assert rows[0]["title"] == "울 블렌드 워크 재킷 차콜"
    assert rows[0]["url"].endswith("/products/1000")  # 不能把图片地址当商品链接
    assert rows[0]["image"].endswith("0.jpg")
    assert rows[0]["price"] == 129000


def test_wear_alt_parsing():
    alt = "「TOMORROWLAND （トゥモローランド）のウールギャバジン ダブルブレストジャケット（テーラードジャケット、ブルー系）」を使った、TOMORROWLAND SHOP WOMENさん（レディース・160cm）の冬コーディネート"
    info = wear.parse_alt(alt)
    assert info["items"] == [{"category": "テーラードジャケット", "color": "ブルー系"}]
    assert info["gender"] == "レディース" and info["height"] == 160 and info["season"] == "冬"
    assert info["brand"] == "TOMORROWLAND"
    assert wear.parse_alt("ロゴ画像") is None


def test_collectors_and_report(workdir):
    results = all_results()
    by = {r["source"]: r for r in results}
    assert by["musinsa"]["ok"] and len(by["musinsa"]["items"]) == 18  # 3 个榜单 × 6
    assert by["wear"]["ok"]
    wear_coords = [i for i in by["wear"]["items"] if i["kind"] == "穿搭"]
    assert len(wear_coords) == 4  # 排行页 3 条女装 + 女装排行页 1 条
    assert not any("MA-1" in i["text"] for i in wear_coords)  # 男装那条被过滤
    assert any(i["kind"] == "关键词" for i in by["wear"]["items"])
    assert by["tiktok"]["ok"] and by["tiktok"]["items"][0]["title"] == "#韓国ファッション"
    assert by["pinterest"]["ok"]

    stats = analyze.term_stats(results)
    assert stats["pinterest"]["total"] == 6  # 韩国、美国各留 3 个服饰词，食谱美甲被过滤
    assert "工装夹克" in stats["musinsa"]["counts"]
    assert "皮夹克" in stats["tiktok"]["counts"] or "皮革" in stats["tiktok"]["counts"]

    today = date(2026, 11, 16)
    scored = analyze.score(stats, analyze.load_history(today))
    assert not scored["baseline_ready"]
    terms = {r["term"] for r in scored["multi_source"]}
    assert "皮夹克" in terms or "酒红" in terms  # MUSINSA + Pinterest 都有

    analyze.save_history(today, stats, results)
    html = report.render(today.isoformat(), results, scored, analyze.wear_breakdown(results), datetime(2026, 11, 16, 6, 30))
    report.write(today.isoformat(), html)
    out = (workdir / "docs" / "index.html").read_text(encoding="utf-8")
    assert "日韩穿搭趋势雷达" in out and "工装夹克" in out and "テーラードジャケット" in out
    assert (workdir / "docs" / "archive" / "2026-11-16.html").exists()
    assert (workdir / "data" / "history" / "2026-11-16.json").exists()


def test_new_and_rising_after_baseline(workdir):
    results = all_results()
    stats = analyze.term_stats(results)
    start = date(2026, 11, 10)
    # 前 4 天只有"阔腿裤"，热度逐天上升；第 5 天出现一堆新词
    for i in range(4):
        d = start + timedelta(days=i)
        hist_stats = {"musinsa": {"total": 10, "counts": {"阔腿裤": 1 + i}, "examples": {}}}
        analyze.save_history(d, hist_stats, [{"source": "musinsa", "ok": True, "items": [0] * 10}])
    today = start + timedelta(days=4)
    scored = analyze.score(stats, analyze.load_history(today))
    assert scored["baseline_ready"]
    new_terms = {r["term"] for r in scored["new"]}
    assert "工装夹克" in new_terms and "阔腿裤" not in new_terms
    rising = {r["term"]: r for r in scored["rising"]}
    assert "阔腿裤" in rising and rising["阔腿裤"]["streak"] == 5


def test_failed_source_still_renders(workdir):
    s = FakeSession({})
    cfg = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8"))["sources"]
    results = [musinsa.collect(s, cfg["musinsa"]), wear.collect(s, cfg["wear"])]
    assert not any(r["ok"] for r in results)
    stats = analyze.term_stats(results)
    scored = analyze.score(stats, [])
    html = report.render("2026-11-16", results, scored, analyze.wear_breakdown(results), datetime.now())
    assert "未采到" in html and "TimeoutError" in html


def test_failed_day_does_not_break_history(workdir):
    ok = [{"source": "musinsa", "ok": True, "items": [0] * 10}]
    bad = [{"source": "musinsa", "ok": False, "items": []}]
    good_stats = {"musinsa": {"total": 10, "counts": {"阔腿裤": 2}, "examples": {}}}
    empty = {"musinsa": {"total": 0, "counts": {}, "examples": {}}}
    d = date(2026, 11, 10)
    analyze.save_history(d, good_stats, ok)
    analyze.save_history(d + timedelta(days=1), empty, bad)  # 全部失败的一天
    assert len(analyze.load_history(d + timedelta(days=2))) == 1
    analyze.save_history(d, empty, bad)  # 同一天重跑失败，不覆盖
    assert analyze.load_history(d + timedelta(days=1))[0]["sources"]["musinsa"]["counts"] == {"阔腿裤": 2}
