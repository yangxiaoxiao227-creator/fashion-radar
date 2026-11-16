"""每天运行一次：采集 → 归类打分 → 存历史 → 生成网页。

本地试跑：python run.py
只跑某几个来源：python run.py musinsa wear
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from radar import analyze, report
from radar.collectors import musinsa, pinterest, tiktok, wear

COLLECTORS = {"musinsa": musinsa, "wear": wear, "tiktok": tiktok, "pinterest": pinterest}


def main(only: list[str]) -> int:
    cfg = json.loads(open("config.json", encoding="utf-8").read())
    now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Shanghai")))
    today = now.date()

    from radar.browser import BrowserSession

    results = []
    with BrowserSession() as session:
        for name, mod in COLLECTORS.items():
            scfg = cfg["sources"].get(name, {})
            if not scfg.get("enabled") or (only and name not in only):
                continue
            print(f"[{name}] 开始采集…", flush=True)
            try:
                res = mod.collect(session, scfg)
            except Exception:
                res = {
                    "source": name, "label": getattr(mod, "LABEL", name), "ok": False,
                    "items": [], "pages": [], "crash": traceback.format_exc(limit=3),
                }
            print(f"[{name}] {'成功' if res['ok'] else '未采到'}，{len(res['items'])} 条", flush=True)
            for p in res.get("pages", []):
                print(f"    - {p['name']}: {p['count']} 条 {p.get('method') or ''} {p.get('error') or ''}", flush=True)
            results.append(res)

    stats = analyze.term_stats(results)
    history = analyze.load_history(today)
    scored = analyze.score(stats, history)
    analyze.save_history(today, stats, results)
    html = report.render(today.isoformat(), results, scored, analyze.wear_breakdown(results), now)
    report.write(today.isoformat(), html)
    print(f"报告已生成：docs/index.html（{sum(r['ok'] for r in results)}/{len(results)} 个来源正常）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
