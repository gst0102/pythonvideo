"""
抖音视频下载工具

技术方案:
    Playwright 浏览器 (真实 Cookie + 页面渲染) -> 提取视频地址 -> 下载

用法:
    python download_video.py
    python download_video.py --url "https://www.douyin.com/jingxuan/food?modal_id=7638570561455179769"
    python download_video.py --url 7638570561455179769 --headless
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SCRIPT_DIR = Path(__file__).parent
DEFAULT_URL = "https://www.douyin.com/jingxuan/food?modal_id=7638570561455179769"
COOKIE_FILE = SCRIPT_DIR / "cookie.txt"
OUTPUT_DIR = SCRIPT_DIR / "downloads"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(SCRIPT_DIR / "pw_browsers"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


def extract_video_id(raw: str) -> str | None:
    if re.match(r"^\d{15,25}$", raw.strip()):
        return raw.strip()
    patterns = [
        r"/video/(\d{15,25})",
        r"modal_id=(\d{15,25})",
        r"aweme_id=(\d{15,25})",
        r"/note/(\d{15,25})",
    ]
    for p in patterns:
        m = re.search(p, raw)
        if m:
            return m.group(1)
    return None


def parse_netscape_cookies(filepath: Path) -> list[dict]:
    cookies = []
    if not filepath.exists():
        return cookies
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7 and parts[5]:
                cookies.append({
                    "name": parts[5],
                    "value": parts[6],
                    "domain": parts[0].lstrip("."),
                    "path": parts[2],
                    "secure": parts[3] == "TRUE",
                    "httpOnly": False,
                })
    return cookies


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "video"


def extract_video_data(page) -> dict | None:
    return page.evaluate("""
        () => {
            function try_extract(aweme) {
                if (!aweme) return null;
                const v = aweme.video || {};

                function pick_url(addr) {
                    const ul = addr.url_list || addr.urlList || [];
                    for (const u of ul) {
                        if (typeof u === 'string' && u.startsWith('http')) return u;
                    }
                    return '';
                }

                let videoUrl = (
                    pick_url(v.download_addr || v.downloadAddr || {}) ||
                    pick_url(v.play_addr || v.playAddr || {})
                );
                if (typeof videoUrl === 'object' && videoUrl) {
                    videoUrl = pick_url(videoUrl);
                }
                if (!videoUrl) {
                    const ul2 = v.url_list || v.urlList || [];
                    for (const u of ul2) {
                        if (typeof u === 'string' && u.startsWith('http')) return u;
                    }
                    if (ul2.length > 0) videoUrl = ul2[0];
                }
                return {
                    title: aweme.desc || '',
                    author: (aweme.author || {}).nickname || '',
                    videoUrl: typeof videoUrl === 'string' ? videoUrl : '',
                    duration: v.duration || 0,
                };
            }

            const el = document.getElementById('RENDER_DATA');
            if (el && el.textContent) {
                try {
                    const raw = el.textContent.trim();
                    const decoded = raw.startsWith('%') ? decodeURIComponent(raw) : raw;
                    const data = JSON.parse(decoded);
                    for (const key of ['app:video', 'app/video', 'app', 'aweme_detail']) {
                        const sub = data[key] || data;
                        for (const k of ['aweme', 'awemeDetail', 'aweme_detail', 'detail']) {
                            const r = try_extract(sub[k] || (sub.itemInfo || {}).itemStruct);
                            if (r) return r;
                        }
                    }
                } catch (e) {}
            }

            const ist = window.__INITIAL_STATE__;
            if (ist) {
                const r = try_extract(ist.awemeDetail || ist.aweme_detail || (ist.video || {}).awemeDetail);
                if (r) return r;
            }

            const rd = window._ROUTER_DATA;
            if (rd) {
                const r = try_extract(rd.awemeDetail || rd.aweme_detail);
                if (r) return r;
            }

            return null;
        }
    """)


def download_http(url: str, output_path: Path, referer: str):
    resp = requests.get(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": referer,
    }, stream=True, timeout=120)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                print(f"\r  Progress: {pct}%  {mb:.1f}/{total_mb:.1f} MB", end="")
    print()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[OK] Download completed! {size_mb:.2f} MB")
    print(f"  Saved to: {output_path}")


def download_blob(page, blob_url: str, output_path: Path):
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch({json.dumps(blob_url)});
            const blob = await resp.blob();
            const buf = await blob.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let binary = '';
            for (let i = 0; i < bytes.length; i++) {{
                binary += String.fromCharCode(bytes[i]);
            }}
            return btoa(binary);
        }}
    """)
    video_bytes = base64.b64decode(result)
    with open(output_path, "wb") as f:
        f.write(video_bytes)
    size_mb = len(video_bytes) / (1024 * 1024)
    print(f"[OK] Download completed! {size_mb:.2f} MB")
    print(f"  Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Douyin video downloader")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--cookies", default=str(COOKIE_FILE))
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"[ERROR] Cannot extract video ID from: {args.url}")
        sys.exit(1)

    video_url = f"https://www.douyin.com/video/{video_id}"
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Douyin Video Downloader")
    print("=" * 60)
    print(f"Video ID  : {video_id}")
    print(f"Video URL : {video_url}")
    print(f"Output    : {output_dir}")

    cookies = parse_netscape_cookies(Path(args.cookies))
    print(f"[Cookie] Loaded {len(cookies)} cookies")
    print()

    captured_network_urls = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1536, "height": 864},
        )
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        def on_response(response):
            url = response.url
            if "aweme/v1/web/aweme/detail/" in url:
                try:
                    body = response.json()
                    aweme = body.get("aweme_detail", body)
                    v = aweme.get("video", {})
                    for field in ("download_addr", "downloadAddr", "play_addr", "playAddr"):
                        addr = v.get(field, {})
                        urls = addr.get("url_list") or addr.get("urlList") or []
                        for u in urls:
                            if isinstance(u, str) and u.startswith("http"):
                                captured_network_urls.append(u)
                                return
                except Exception:
                    pass
            elif ".mp4" in url or ".m3u8" in url:
                excluded = ("douyinstatic.com", "/obj/", "/static/")
                if not any(e in url for e in excluded):
                    if "douyinvod" in url or "bytecdn" in url or "snssdk" in url:
                        captured_network_urls.append(url.split("?")[0])

        page.on("response", on_response)

        print("Visiting page...")
        try:
            page.goto(video_url, wait_until="domcontentloaded", timeout=60_000)
        except PlaywrightTimeout:
            print("[WARNING] Timeout, continuing...")

        print("Waiting for video data...")
        video_data = None
        for retry in range(30):
            time.sleep(1.0)
            video_data = extract_video_data(page)
            if video_data and video_data.get("videoUrl"):
                print(f"\n  [DOM] Data extracted")
                break
            if captured_network_urls:
                video_data = {
                    "title": "",
                    "author": "",
                    "videoUrl": captured_network_urls[0],
                    "duration": 0,
                }
                print(f"\n  [Network] Captured CDN URL")
                break
            if retry % 5 == 0 and retry > 0:
                print(f"  ... {retry}s")

        if not video_data or not video_data.get("videoUrl"):
            print(f"\n[FAIL] No video URL found")
            print(f"  Title: {page.title()}")
            browser.close()
            sys.exit(1)

        print(f"  Title    : {video_data['title'] or '(from network)'}")
        print(f"  Author   : {video_data['author'] or 'N/A'}")
        dl_url = video_data["videoUrl"]
        print(f"  URL      : {dl_url[:100]}...")

        safe_name = sanitize_filename(video_data["title"] or "douyin_video")
        output_path = output_dir / f"{safe_name}.mp4"

        if dl_url.startswith("blob:"):
            print("\n[Blob] Downloading via browser fetch...")
            download_blob(page, dl_url, output_path)
        else:
            print(f"\nDownloading to: {output_path}")
            try:
                download_http(dl_url, output_path, video_url)
            except Exception as e:
                print(f"[FAIL] {e}")

        browser.close()


if __name__ == "__main__":
    main()