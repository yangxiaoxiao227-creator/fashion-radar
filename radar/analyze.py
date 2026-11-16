"""把各来源的原始条目变成"趋势词"，并和历史对比打分。

热度的算法：某个词在某个来源里出现的条数 ÷ 该来源当天总条数 × 100，
再把各来源加起来。这样 MUSINSA 一次采 180 条、TikTok 只有 12 条，
两边的信号也能放在一起比，不会被条数多的来源淹没。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from .glossary import GENERIC, TYPE_OF, match_terms

HISTORY_DIR = Path("data/history")
BASELINE_DAYS = 3  # 至少攒够几天历史，才开始判断"新上榜"


def term_stats(results: list[dict]) -> dict:
    """返回 {来源: {"total": 条数, "counts": {词: 次数}, "examples": {词: [原文…]}}}"""
    out = {}
    for res in results:
        src = res["source"]
        counts, examples = Counter(), defaultdict(list)
        usable = 0
        for it in res.get("items", []):
            terms = match_terms(it.get("text") or it.get("title", ""), loose=(src == "tiktok"))
            if src == "pinterest" and not terms:
                continue  # Pinterest 什么领域都有，对不上服饰词典的不算
            usable += 1
            for t in terms:
                counts[t] += 1
                if len(examples[t]) < 3:
                    examples[t].append((it.get("title") or "")[:60])
        out[src] = {"total": usable, "counts": dict(counts), "examples": dict(examples)}
    return out


def wear_breakdown(results: list[dict]) -> dict:
    """WEAR 图片文字里自带的品类和颜色，直接统计，不经过词典。"""
    cats, colors = Counter(), Counter()
    for res in results:
        if res["source"] != "wear":
            continue
        for it in res["items"]:
            for wi in it.get("wear_items", []):
                cats[wi["category"]] += 1
                colors[wi["color"]] += 1
    return {"categories": cats.most_common(20), "colors": colors.most_common(15)}


def load_history(today: date, days: int = 14) -> list[dict]:
    hist = []
    for i in range(days, 0, -1):
        f = HISTORY_DIR / f"{(today - timedelta(days=i)).isoformat()}.json"
        if f.exists():
            try:
                h = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            # 所有来源都失败的那天不算数，免得打断"连续上升"的天数
            if any(s.get("ok") for s in h.get("sources", {}).values()):
                hist.append(h)
    return hist


def save_history(today: date, stats: dict, results: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    target = HISTORY_DIR / f"{today.isoformat()}.json"
    # 当天手动重跑全部失败时，不覆盖之前成功的数据
    if target.exists() and not any(r["ok"] for r in results):
        return
    payload = {
        "date": today.isoformat(),
        "sources": {
            r["source"]: {
                "ok": r["ok"],
                "count": len(r["items"]),
                "total": stats[r["source"]]["total"],
                "counts": stats[r["source"]]["counts"],
            }
            for r in results
        },
    }
    (HISTORY_DIR / f"{today.isoformat()}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _heat(src_stats: dict) -> dict:
    """{词: {来源: 占比分}}"""
    heat = defaultdict(dict)
    for src, st in src_stats.items():
        total = st.get("total") or 0
        if not total:
            continue
        for t, c in st.get("counts", {}).items():
            heat[t][src] = round(c / total * 100, 1)
    return heat


def score(stats: dict, history: list[dict]) -> dict:
    today_heat = _heat(stats)
    past_heats = [_heat(h.get("sources", {})) for h in history]
    baseline_ready = len(history) >= BASELINE_DAYS

    rows = []
    for term, by_src in today_heat.items():
        total = round(sum(by_src.values()), 1)
        past_totals = [sum(ph.get(term, {}).values()) for ph in past_heats[-7:]]
        prev_avg = round(sum(past_totals) / len(past_totals), 1) if past_totals else 0.0
        streak = 1
        for ph in reversed(past_heats):
            if term in ph:
                streak += 1
            else:
                break
        seen_before = any(term in ph for ph in past_heats)
        examples = []
        for src in by_src:
            examples += stats[src]["examples"].get(term, [])
        rows.append(
            {
                "term": term,
                "type": TYPE_OF.get(term, "其他"),
                "heat": total,
                "sources": sorted(by_src, key=lambda s: -by_src[s]),
                "by_source": by_src,
                "prev_avg": prev_avg,
                "delta": round(total - prev_avg, 1),
                "streak": streak,
                "is_new": baseline_ready and not seen_before,
                "generic": term in GENERIC,
                "examples": examples[:4],
            }
        )

    specific = [r for r in rows if not r["generic"]]
    by_type = lambda t, n: sorted([r for r in specific if r["type"] == t], key=lambda r: -r["heat"])[:n]
    return {
        "baseline_ready": baseline_ready,
        "history_days": len(history),
        "top_items": by_type("单品", 12),
        "top_colors": by_type("颜色", 8),
        "top_styles": by_type("风格", 8),
        "multi_source": sorted(
            [r for r in specific if len(r["sources"]) >= 2],
            key=lambda r: (-len(r["sources"]), -r["heat"]),
        )[:12],
        "new": sorted([r for r in specific if r["is_new"]], key=lambda r: -r["heat"])[:10],
        "rising": sorted(
            [r for r in specific if r["streak"] >= 3 and r["delta"] > 0],
            key=lambda r: -r["delta"],
        )[:10],
    }
