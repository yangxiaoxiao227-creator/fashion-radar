"""生成每天的网页报告：docs/index.html（最新一期）+ docs/archive/日期.html（存档）。"""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

DOCS = Path("docs")
SRC_NAME = {"musinsa": "MUSINSA", "wear": "WEAR", "tiktok": "TikTok", "pinterest": "Pinterest"}

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--sub:#6b6b70;--line:#e6e4df;--accent:#2f5bd3;--good:#1f8a4c;--bad:#c2410c;--chip:#f0eee9}
@media (prefers-color-scheme: dark){:root{--bg:#141416;--card:#1d1d20;--ink:#ededef;--sub:#9a9aa1;--line:#2c2c31;--accent:#7aa2ff;--good:#4ade80;--bad:#fb923c;--chip:#2a2a2f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:24px;margin:8px 0 2px}h2{font-size:18px;margin:32px 0 10px}h3{font-size:15px;margin:18px 0 8px;color:var(--sub)}
.sub{color:var(--sub);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--sub);font-weight:500}td:nth-child(2),td:nth-child(3),th{white-space:nowrap}
.ok{color:var(--good);font-weight:600}.fail{color:var(--bad);font-weight:600}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 8px;margin:2px 4px 2px 0;font-size:12px;color:var(--sub)}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.term{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px dashed var(--line)}.term:last-child{border-bottom:0}
.term b{min-width:96px}.bar{flex:1;height:6px;background:var(--chip);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.num{font-variant-numeric:tabular-nums;color:var(--sub);font-size:12px;min-width:44px;text-align:right}
.ex{color:var(--sub);font-size:12px;margin:-2px 0 6px}
.items{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:12px;text-decoration:none;color:var(--ink)}
.item img{width:100%;aspect-ratio:3/4;object-fit:cover;background:var(--chip);display:block}.item div{padding:6px 8px}.item .r{color:var(--accent);font-weight:600}
.note{background:var(--chip);border-radius:8px;padding:8px 12px;color:var(--sub);font-size:13px}
a{color:var(--accent)}footer{margin-top:40px;color:var(--sub);font-size:12px}
"""


def _term_list(rows: list[dict], show_delta: bool = False) -> str:
    if not rows:
        return '<p class="sub">暂无</p>'
    top = max(r["heat"] for r in rows) or 1
    out = []
    for r in rows:
        srcs = "".join(f'<span class="chip">{SRC_NAME.get(s, s)}</span>' for s in r["sources"])
        extra = f' <span class="chip">+{r["delta"]}</span>' if show_delta else ""
        if r.get("streak", 1) >= 2:
            extra += f' <span class="chip">连续 {r["streak"]} 天</span>'
        out.append(
            f'<div class="term"><b>{escape(r["term"])}</b><span class="bar"><i style="width:{r["heat"] / top * 100:.0f}%"></i></span>'
            f'<span class="num">{r["heat"]}</span></div><div class="ex">{srcs}{extra} '
            f'{escape(" ／ ".join(r["examples"][:2]))}</div>'
        )
    return "".join(out)


def _status_table(results: list[dict]) -> str:
    rows = []
    for r in results:
        detail = "<br>".join(
            f'{escape(p["name"])}：{p["count"]} 条'
            + (f'（{escape(p["method"])}）' if p.get("method") else "")
            + (f' <span class="fail">{escape(str(p["error"])[:120])}</span>' if p.get("error") else "")
            for p in r.get("pages", [])
        )
        status = '<span class="ok">正常</span>' if r["ok"] else '<span class="fail">未采到</span>'
        if r.get("crash"):
            detail = f'<span class="fail">{escape(r["crash"][:300])}</span>'
        note = f'<div class="sub">{escape(r["note"])}</div>' if r.get("note") else ""
        rows.append(f"<tr><td>{escape(r['label'])}</td><td>{status}</td><td>{len(r.get('items', []))}</td><td>{detail}{note}</td></tr>")
    return "<table><tr><th>来源</th><th>状态</th><th>条数</th><th>明细</th></tr>" + "".join(rows) + "</table>"


def _item_grid(items: list[dict], n: int) -> str:
    cards = []
    for it in items[:n]:
        img = (
            f'<img loading="lazy" referrerpolicy="no-referrer" src="{escape(it["image"])}" alt="">'
            if it.get("image") else '<img alt="">'
        )
        brand = f'{escape(it["brand"])}<br>' if it.get("brand") else ""
        price = f' · ₩{it["price"]:,}' if it.get("price") else ""
        href = escape(it.get("url") or "#")
        cards.append(
            f'<a class="item" href="{href}" target="_blank" rel="noopener">{img}<div><span class="r">#{it.get("rank") or ""}</span>{price}<br>'
            f'{brand}{escape(it["title"][:60])}</div></a>'
        )
    return f'<div class="items">{"".join(cards)}</div>' if cards else '<p class="sub">暂无</p>'


def _source_sections(results: list[dict], wear_bd: dict) -> str:
    html = []
    for r in results:
        if not r.get("items"):
            continue
        html.append(f"<h2>{escape(r['label'])}</h2>")
        if r["source"] in ("musinsa", "wear"):
            lists: dict[str, list] = {}
            for it in r["items"]:
                if it.get("kind") in ("商品", "穿搭"):
                    lists.setdefault(it["list_name"], []).append(it)
            for name, its in lists.items():
                html.append(f"<h3>{escape(name)}（前 24）</h3>" + _item_grid(its, 24))
            if r["source"] == "wear" and wear_bd["categories"]:
                cats = "".join(f'<span class="chip">{escape(c)} {n}</span>' for c, n in wear_bd["categories"])
                cols = "".join(f'<span class="chip">{escape(c)} {n}</span>' for c, n in wear_bd["colors"])
                html.append(f'<h3>WEAR 排行里的品类和颜色（原文）</h3><div class="card">{cats}<br><br>{cols}</div>')
            kws = [it["title"] for it in r["items"] if it.get("kind") == "关键词"]
            if kws:
                html.append('<h3>话题与趋势关键词（原文）</h3><div class="card">' + "".join(f'<span class="chip">{escape(k)}</span>' for k in kws[:60]) + "</div>")
        else:
            shown = r["items"]
            if r["source"] == "pinterest":
                from .glossary import match_terms
                shown = [it for it in shown if match_terms(it["title"])]
                if not shown:
                    html.pop()  # 去掉刚加的标题
                    continue
            rows = "".join(
                f'<tr><td>{escape(it["list_name"])}</td><td>{it.get("rank") or ""}</td>'
                f'<td><a href="{escape(it.get("url") or "#")}" target="_blank" rel="noopener">{escape(it["title"])}</a></td>'
                f'<td>{it["views"]:,}</td></tr>' if it.get("views") else
                f'<tr><td>{escape(it["list_name"])}</td><td>{it.get("rank") or ""}</td>'
                f'<td>{escape(it["title"])}</td><td></td></tr>'
                for it in shown[:60]
            )
            html.append(f'<div class="card"><table><tr><th>榜单</th><th>排名</th><th>内容</th><th>播放</th></tr>{rows}</table></div>')
    return "".join(html)


def render(day: str, results: list[dict], scored: dict, wear_bd: dict, generated_at: datetime) -> str:
    baseline_note = (
        ""
        if scored["baseline_ready"]
        else f'<p class="note">"新上榜"和"持续上升"需要先积累 3 天历史，目前已有 {scored["history_days"]} 天，这两栏暂时为空属正常。</p>'
    )
    body = f"""
<h1>日韩穿搭趋势雷达</h1>
<div class="sub">{escape(day)} · 生成于 {generated_at.strftime('%H:%M')}（北京时间） · <a href="archive/index.html">往期</a></div>

<h2>数据源状态</h2>
<div class="card">{_status_table(results)}</div>

<h2>今日热度</h2>
<p class="sub">热度 = 该词在每个来源里出现的条数占比（%）之和，标签显示它出现在哪些来源。</p>
<div class="grid3">
  <div class="card"><h3 style="margin-top:0">单品</h3>{_term_list(scored['top_items'])}</div>
  <div class="card"><h3 style="margin-top:0">颜色</h3>{_term_list(scored['top_colors'])}</div>
  <div class="card"><h3 style="margin-top:0">材质 / 图案 / 风格</h3>{_term_list(scored['top_styles'])}</div>
</div>

<h2>多个来源同时出现</h2>
<p class="sub">同时出现在两个以上来源的词，比单一来源的信号更可信。</p>
<div class="card">{_term_list(scored['multi_source'])}</div>

<h2>新上榜 · 持续上升</h2>
{baseline_note}
<div class="grid3">
  <div class="card"><h3 style="margin-top:0">新上榜（历史上首次出现）</h3>{_term_list(scored['new'])}</div>
  <div class="card"><h3 style="margin-top:0">持续上升（连续 3 天以上且高于 7 天均值）</h3>{_term_list(scored['rising'], show_delta=True)}</div>
</div>

{_source_sections(results, wear_bd)}

<footer>数据来自各平台公开页面，每天采集一次，仅供选题参考。词典未收录的词不会进入热度统计，可在 radar/glossary.py 里补充。</footer>
"""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>日韩穿搭趋势雷达 · {escape(day)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>"""


def write(day: str, html: str) -> None:
    (DOCS / "archive").mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    # 存档页里的"往期"链接要指向同目录的 index.html
    (DOCS / "archive" / f"{day}.html").write_text(html.replace('href="archive/index.html"', 'href="index.html"'), encoding="utf-8")
    days = sorted((p.stem for p in (DOCS / "archive").glob("20*.html")), reverse=True)
    links = "".join(f'<li><a href="{d}.html">{d}</a></li>' for d in days)
    (DOCS / "archive" / "index.html").write_text(
        f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>往期报告</title><style>{CSS}</style></head><body><main><h1>往期报告</h1><p><a href="../index.html">回到最新一期</a></p>'
        f'<div class="card"><ul>{links}</ul></div></main></body></html>',
        encoding="utf-8",
    )
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
