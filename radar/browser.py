"""用无头浏览器打开网页，同时记录页面加载过程中返回的所有 JSON 数据。

很多网站（MUSINSA、TikTok、Pinterest）的榜单是网页里的脚本再去请求接口拿到的，
直接下载 HTML 看不到数据。所以这里用真正的浏览器打开页面，把接口返回的 JSON
一并收集起来，交给各个采集器去解析。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

DEBUG_DIR = Path("debug")


class PageResult:
    def __init__(self, url: str, html: str, jsons: list[dict], final_url: str, error: str | None = None):
        self.url = url
        self.html = html
        self.jsons = jsons  # [{"url":..., "status":..., "body":...}]
        self.final_url = final_url
        self.error = error


class BrowserSession:
    """一次运行只启动一个浏览器，所有采集器共用。"""

    def __init__(self):
        self._pw = None
        self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        # 本地调试可设置 CHROME_PATH 使用已安装的 Chrome；GitHub Actions 上不需要
        chrome = os.environ.get("CHROME_PATH")
        args = ["--disable-blink-features=AutomationControlled"] + (["--no-sandbox"] if chrome else [])
        self._browser = self._pw.chromium.launch(headless=True, executable_path=chrome or None, args=args)
        return self

    def __exit__(self, *exc):
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def open(
        self,
        url: str,
        *,
        locale: str = "en-US",
        wait_ms: int = 6000,
        scrolls: int = 4,
        json_filter=None,
        debug_name: str | None = None,
    ) -> PageResult:
        ctx = self._browser.new_context(
            user_agent=UA,
            locale=locale,
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        jsons: list[dict] = []

        def on_response(resp):
            try:
                ctype = resp.headers.get("content-type", "")
                if "json" not in ctype:
                    return
                if json_filter and not json_filter(resp.url):
                    return
                jsons.append({"url": resp.url, "status": resp.status, "body": resp.json()})
            except Exception:
                pass

        page.on("response", on_response)
        html, final_url, error = "", url, None
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(wait_ms)
            for _ in range(scrolls):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)
            html = page.content()
            final_url = page.url
        except Exception as e:  # 超时、被拦截等
            error = f"{type(e).__name__}: {e}"[:500]
            try:
                html = page.content()
            except Exception:
                pass
        finally:
            ctx.close()

        result = PageResult(url, html, jsons, final_url, error)
        if debug_name:
            save_debug(debug_name, result)
        return result


def save_debug(name: str, result: PageResult) -> None:
    """保存原始数据，方便第一次运行后排查哪个数据源没采到。"""
    DEBUG_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w\-]+", "_", name)[:80]
    summary = {
        "requested_url": result.url,
        "final_url": result.final_url,
        "error": result.error,
        "html_length": len(result.html),
        "json_responses": [
            {"url": j["url"], "status": j["status"], "preview": json.dumps(j["body"], ensure_ascii=False)[:3000]}
            for j in result.jsons
        ],
    }
    (DEBUG_DIR / f"{safe}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / f"{safe}.html").write_text(result.html[:400_000], encoding="utf-8")
