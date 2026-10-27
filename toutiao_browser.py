"""今日头条发布自动化。

浏览器获取方式统一为 Playwright 持久化上下文：
浏览器进程的生命周期绑定在当前 Python 进程上，登录态落在 profile 目录，
重启后仍然有效，不依赖任何会被回收的独立进程。
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "browser_state" / "toutiao"
CONFIG_PATH = ROOT / "config.json"
CREATOR_URL = "https://mp.toutiao.com/profile_v4/index"
PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"
CDP_PORT = 9223
IS_WINDOWS = sys.platform == "win32"

LOG_DIR = ROOT / "logs"


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    example = ROOT / "config.example.json"
    return json.loads(example.read_text(encoding="utf-8"))


def edge_path():
    if not IS_WINDOWS:
        return None
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("未找到 Microsoft Edge")


# --------------------------------------------------------------------------
# 浏览器会话
# --------------------------------------------------------------------------


def _cdp_alive():
    """检测本机 9223 调试端口上是否已有可复用的 Edge。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        return sock.connect_ex(("127.0.0.1", CDP_PORT)) == 0


def open_session(playwright):
    """返回 (mode, browser, context, page)。

    mode = "cdp"       复用一个已经带调试端口启动的 Edge
    mode = "persistent" 由 Playwright 持有 Edge/Chromium 进程
    """
    if _cdp_alive():
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}", timeout=3000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[-1] if context.pages else context.new_page()
            return "cdp", browser, context, page
        except Exception as exc:
            print(f"cdp_connect_failed={exc.__class__.__name__}")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    launch_args = [
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=msEdgeSidebarV2,msEdgeFirstRunExperience",
        # 降内存：这台机器只有 5.9GB，跑不动完整渲染栈
        "--disable-gpu",
        "--renderer-process-limit=2",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--js-flags=--max-old-space-size=512",
    ]
    if not IS_WINDOWS:
        launch_args.append("--disable-dev-shm-usage")

    kwargs = {
        "user_data_dir": str(STATE_DIR),
        "headless": False,
        "args": launch_args,
        "viewport": {"width": 1440, "height": 900},
    }
    if IS_WINDOWS:
        kwargs["executable_path"] = edge_path()

    context = playwright.chromium.launch_persistent_context(**kwargs)
    page = context.pages[-1] if context.pages else context.new_page()
    return "persistent", None, context, page


def close_session(mode, browser, context):
    try:
        if mode == "cdp" and browser is not None:
            browser.close()
        elif context is not None:
            context.close()
    except Exception:
        pass


def open_edge(url=CREATOR_URL):
    """手动拉起一个带调试端口的独立 Edge（备用方案，通常不需要）。"""
    if not IS_WINDOWS:
        print("platform=linux")
        return None
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        edge_path(),
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={STATE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=creationflags)
    print("edge_opened=true")
    print(f"debug_port={CDP_PORT}")
    print(f"profile={STATE_DIR}")


# --------------------------------------------------------------------------
# 登录状态
# --------------------------------------------------------------------------

# 创作者后台登录后才出现的标志性元素（依据实际页面 DOM）
_BACKEND_MARKERS = [
    "text=作品管理",
    "text=创作灵感",
    "text=收益数据",
    "text=草稿箱",
    "text=发布文章",
    "text=粉丝数据",
]


def bring_window_to_front():
    """把 Edge 授权窗口切到前台，方便第一时间扫码（仅 Windows）。"""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        target = {"hwnd": None}

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if "Edge" in title and ("头条" in title or "toutiao" in title.lower() or "Microsoft" in title):
                target["hwnd"] = hwnd
                return False
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        hwnd = target["hwnd"]
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def cookies_indicate_login(context):
    """检查 profile 里是否已有登录态 cookie（作为页面判定的补充依据）。"""
    try:
        cookies = context.cookies()
    except Exception:
        return False
    names = {c.get("name", "") for c in cookies}
    for key in ("sessionid", "sessionid_ss", "sid_tt", "uid_tt"):
        if key in names:
            return True
    return False


def ensure_logged_in(page, context):
    """跳到创作者后台首页验证登录态，返回 (是否已登录, 判定理由)。

    发布页本身没有后台菜单标记，判定必须在后台首页做。
    """
    try:
        page.goto(CREATOR_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
    except Exception as exc:
        return False, f"goto_creator_failed={exc.__class__.__name__}"
    return is_logged_in(page, context)


def is_logged_in(page, context=None):
    """返回 (是否已登录, 判定理由)。"""
    url = (page.url or "").lower()
    for bad in ("login", "sso", "/auth/", "passport"):
        if bad in url:
            # URL 指向登录页，但 cookie 里可能已有有效登录态
            if context is not None and cookies_indicate_login(context):
                return True, "login_url_but_session_cookie_present"
            return False, f"url_points_to_login({page.url})"

    try:
        body = page.locator("body").inner_text(timeout=5000)
    except Exception:
        body = ""
    if "扫码登录" in body or "验证码登录" in body:
        return False, "page_shows_login_panel"

    hits = []
    for marker in _BACKEND_MARKERS:
        try:
            if page.locator(marker).count() > 0:
                hits.append(marker)
        except Exception:
            continue
    if len(hits) >= 2:
        return True, "backend_markers=" + "|".join(hits)
    if hits:
        return True, "backend_marker=" + hits[0]
    return False, "no_backend_marker"


# --------------------------------------------------------------------------
# 正文处理
# --------------------------------------------------------------------------


def body_to_plain(markdown):
    """把 Markdown 正文转成适合头条编辑器的纯文本。

    段落之间用单个换行分隔：头条的 ProseMirror 会把每个换行渲染成一个空段落，
    若沿用 Markdown 的空行会产生大量 <p><br></p>，页面看起来段落间距过大。
    """
    lines = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[-*_]{3,}", line):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "· ", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`(.+?)`", r"\1", line)
        lines.append(line)

    return "\n".join(lines).strip()


def split_title_body(markdown):
    lines = markdown.strip().splitlines()
    title = ""
    body_lines = []
    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not title:
        first = body.splitlines()[0] if body else ""
        title = re.sub(r"^[#\s]+", "", first).strip()[:30]
    return title[:30], body_to_plain(body)


# --------------------------------------------------------------------------
# 页面交互
# --------------------------------------------------------------------------


def fill_first_match(page, selectors, value, timeout=5000):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            loc.fill(value)
            return selector
        except Exception:
            continue
    return None


def click_first_match(page, selectors, timeout=3000):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return selector
        except Exception:
            continue
    return None


def visible_button_texts(page):
    """一次性取回所有可见按钮的文本与索引，避免逐个 evaluate 时页面重渲染导致卡死。"""
    try:
        return page.evaluate(
            """() => {
                const out = [];
                const buttons = document.querySelectorAll('button');
                for (let i = 0; i < buttons.length; i++) {
                    const el = buttons[i];
                    const r = el.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) continue;
                    out.push({
                        index: i,
                        text: (el.innerText || el.textContent || '').trim(),
                        cls: String(el.className)
                    });
                }
                return out;
            }"""
        )
    except Exception:
        return []


def click_visible_button_text(page, text, timeout=5000):
    """按可见按钮的精确文本点击，避免命中「预览并定时发布」这类长文本。"""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        for item in visible_button_texts(page):
            if item["text"] == text:
                try:
                    page.locator("button").nth(item["index"]).click(force=True, timeout=3000)
                    return True
                except Exception:
                    pass
        page.wait_for_timeout(400)
    return False


def try_click_text(page, text, timeout=1500):
    try:
        return click_first_match(
            page,
            [
                f"text={text}",
                f"button:has-text('{text}')",
                f"label:has-text('{text}')",
                f"span:has-text('{text}')",
            ],
            timeout=timeout,
        )
    except Exception:
        return None


def label_checked(page, text):
    """读取指定选项当前是否勾选（input.checked 为准）。

    一次性枚举所有 radio/checkbox，避免逐个 evaluate 时页面重渲染导致卡死。
    """
    try:
        items = page.evaluate(
            """() => {
                const out = {};
                const els = document.querySelectorAll('.byte-radio, .byte-checkbox, label');
                for (const el of els) {
                    const input = el.querySelector('input');
                    if (!input) continue;
                    const t = (el.innerText || el.textContent || '').trim();
                    if (!t || t in out) continue;
                    out[t] = input.checked;
                }
                return out;
            }"""
        )
    except Exception:
        return None
    if isinstance(items, dict) and text in items:
        return items[text]
    return None


def ensure_option_checked(page, text, selector=".byte-radio, .byte-checkbox", timeout_ms=4000):
    """把指定名称的 radio/checkbox 勾上，返回最终是否勾选。

    页面上「无封面」「不投放广告」是 .byte-radio，
    「个人观点，仅供参考」是 .byte-checkbox，两者共用的点击路径。
    """
    # 一次性枚举候选元素，避免逐个 evaluate 时页面重渲染导致卡死
    try:
        candidates = page.evaluate(
            """(args) => {
                const text = args.text;
                const sel = args.selector;
                const out = [];
                const els = document.querySelectorAll(sel);
                for (let i = 0; i < els.length; i++) {
                    const el = els[i];
                    const t = (el.innerText || el.textContent || '').trim();
                    if (t !== text && !t.includes(text)) continue;
                    const input = el.querySelector('input');
                    if (!input) continue;
                    const r = el.getBoundingClientRect();
                    out.push({
                        index: i,
                        checked: input.checked,
                        visible: r.width > 0 && r.height > 0,
                        exact: t === text
                    });
                }
                return out;
            }""",
            {"text": text, "selector": selector},
        )
    except Exception:
        return False

    if not candidates:
        return False

    # 优先精确匹配
    candidates.sort(key=lambda c: (not c["exact"], not c["visible"]))

    target = None
    for cand in candidates:
        if cand["checked"]:
            return True
        if target is None and cand["visible"]:
            target = cand
    if target is None:
        return False

    for _ in range(3):
        try:
            page.locator(selector).nth(target["index"]).click(force=True, timeout=3000)
        except Exception:
            return False
        page.wait_for_timeout(700)
        try:
            checked = page.evaluate(
                """(args) => {
                    const els = document.querySelectorAll(args.selector);
                    const el = els[args.index];
                    const input = el ? el.querySelector('input') : null;
                    return input ? input.checked : null;
                }""",
                {"selector": selector, "index": target["index"]},
            )
        except Exception:
            return False
        if checked:
            return True
    return False


def fill_article(page, title, body):
    """填标题和正文，返回 (标题选择器, 正文选择器)。

    依据实际 DOM：
      标题 = textarea[placeholder*='标题']（"请输入文章标题（2～30个字）"）
      正文 = .ProseMirror（页面上唯一的 contenteditable）
    """
    page.goto(PUBLISH_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    title_selector = fill_first_match(
        page,
        [
            "textarea[placeholder*='标题']",
            "textarea[placeholder*='文章标题']",
            "textarea",
        ],
        title,
    )

    body_selector = None
    editor = page.locator(".ProseMirror").first
    try:
        editor.wait_for(state="visible", timeout=8000)
        editor.click()
        page.wait_for_timeout(300)
        page.keyboard.insert_text(body)
        body_selector = ".ProseMirror"
    except Exception:
        body_selector = fill_first_match(
            page,
            [
                "div[contenteditable='true']",
                "textarea[placeholder*='正文']",
            ],
            body,
        )
    page.wait_for_timeout(1500)
    return title_selector, body_selector


# --------------------------------------------------------------------------
# 发布选项
# --------------------------------------------------------------------------

DEFAULT_OPTIONS = {
    "cover": "无封面",
    "ads": "不投放广告",
    "location": "",
    "declaration": "个人观点，仅供参考",
    "sync_weitoutiao": False,
    "schedule_offset_hours": 0,
}


def toutiao_options(config):
    options = dict(DEFAULT_OPTIONS)
    options.update((config.get("platforms", {}).get("toutiao", {}) or {}).get("options", {}) or {})
    return options


def set_toutiao_options(page, options):
    """按真实 DOM 设置发布选项。

    依据实际页面：
      封面   .byte-radio  「单图 / 三图 / 无封面」
      广告   .byte-radio  「投放广告赚收益 / 不投放广告」
      声明   .byte-checkbox，需先展开「作品声明」面板
    """
    actions = []
    page.set_default_timeout(4000)

    cover = (options.get("cover") or "").strip()
    ads = (options.get("ads") or "").strip()
    declaration = (options.get("declaration") or "").strip()
    location = (options.get("location") or "").strip()

    if cover:
        ok = ensure_option_checked(page, cover, ".byte-radio")
        actions.append(f"cover={cover} checked={ok}")

    if ads:
        ok = ensure_option_checked(page, ads, ".byte-radio")
        actions.append(f"ads={ads} checked={ok}")

    if options.get("sync_weitoutiao"):
        ok = ensure_option_checked(page, "同时发布微头条", ".byte-checkbox")
        actions.append(f"sync_weitoutiao={ok}")

    if declaration:
        # 「作品声明」是一个可展开的面板，展开后才会露出具体声明项
        opened = try_click_text(page, "作品声明")
        page.wait_for_timeout(1200)
        actions.append(f"declaration_panel_opened={bool(opened)}")
        # 页面上「个人观点，仅供参考」是单个 checkbox，
        # 因此先按完整文案匹配，匹配不到再按顿号/逗号拆分。
        parts = [declaration]
        if not ensure_option_checked(page, declaration, ".byte-checkbox"):
            parts = [p.strip() for p in declaration.replace("，", ",").split(",") if p.strip()]
            for part in parts:
                ok = ensure_option_checked(page, part, ".byte-checkbox")
                actions.append(f"declaration_part={part} checked={ok}")
        else:
            actions.append(f"declaration={declaration} checked=True")

    if location:
        ok = try_click_text(page, "添加位置")
        if ok:
            page.wait_for_timeout(1000)
            for selector in ("input[placeholder*='搜索']", "input[placeholder*='城市']", "input"):
                try:
                    loc = page.locator(selector).first
                    loc.wait_for(state="visible", timeout=2000)
                    loc.click()
                    loc.type(location, delay=60)
                    break
                except Exception:
                    continue
            page.wait_for_timeout(1800)
            picked = try_click_text(page, location, timeout=2500)
            actions.append(f"location={location} picked={bool(picked)}")
        else:
            actions.append(f"location={location} not_found")
    else:
        actions.append("location=skipped")

    return actions


def schedule_time_text(offset_hours):
    publish_time = datetime.now() + timedelta(hours=offset_hours)
    publish_time = publish_time.replace(minute=0, second=0, microsecond=0)
    return publish_time.strftime("%Y-%m-%d %H:%M")


def set_schedule(page, offset_hours):
    actions = []
    if not try_click_text(page, "定时发布", timeout=2000):
        actions.append("schedule_panel=not_found")
        return actions
    actions.append("schedule_panel=opened")
    time_text = schedule_time_text(offset_hours)
    for selector in (
        "input[placeholder*='时间']",
        "input[placeholder*='日期']",
        "input[class*='time']",
    ):
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=2500)
            loc.click()
            loc.press("Control+A")
            loc.type(time_text, delay=25)
            actions.append(f"schedule_time={time_text} selector={selector}")
            break
        except Exception:
            continue
    page.wait_for_timeout(800)
    return actions


def validate_required_options(page, options):
    checks = {}
    cover = (options.get("cover") or "").strip()
    ads = (options.get("ads") or "").strip()
    declaration = (options.get("declaration") or "").strip()
    if cover:
        checks["cover"] = label_checked(page, cover)
    if ads:
        checks["ads"] = label_checked(page, ads)
    if declaration:
        checks["declaration"] = label_checked(page, declaration)
    print("option_checks=" + json.dumps(checks, ensure_ascii=False))
    return all(v for v in checks.values()) if checks else True


# --------------------------------------------------------------------------
# 队列
# --------------------------------------------------------------------------


def latest_toutiao_queue(config):
    queue_dir = Path(config["storage_dir"]) / "_publish_queue" / "toutiao"
    files = sorted(queue_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError(f"未找到今日头条待发布队列：{queue_dir}")
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("consumed_at") or data.get("status") in {"submitted", "consumed"}:
            continue
        return path
    raise RuntimeError(f"今日头条队列中没有待发布内容（均已完成）：{queue_dir}")


def read_content_from_queue(queue_path):
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    content_file = Path(queue["content_file"])
    content = content_file.read_text(encoding="utf-8")
    return queue, content


PUBLISHED_LOG = ROOT / "storage" / "published_toutiao.json"


def published_fingerprint(title, body):
    """用标题+正文前段生成指纹，用于识别「同一篇是否已经发过」。"""
    import hashlib

    payload = f"{title}\n{body[:200]}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def load_published_log():
    if PUBLISHED_LOG.exists():
        try:
            return json.loads(PUBLISHED_LOG.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def record_published(fingerprint, title, pgc_id=None):
    """记录已发布指纹，防止同一篇内容被重复发布。"""
    data = load_published_log()
    data[fingerprint] = {
        "title": title,
        "pgc_id": pgc_id,
        "published_at": time.strftime("%Y%m%d_%H%M%S"),
    }
    PUBLISHED_LOG.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED_LOG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def already_published(fingerprint):
    return fingerprint in load_published_log()


# --------------------------------------------------------------------------
# 流程
# --------------------------------------------------------------------------


def authorize(timeout_seconds=900):
    """打开头条创作者后台，等待人工完成登录/扫码，检测到登录成功后自动收尾。"""
    playwright = sync_playwright().start()
    mode = browser = context = page = None
    try:
        mode, browser, context, page = open_session(playwright)
        print(f"browser_mode={mode}")
        print(f"profile={STATE_DIR}")
        page.goto(CREATOR_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        print("请在打开的浏览器窗口中完成今日头条登录（扫码 / 验证码）。")
        print("脚本会自动检测登录状态，成功后退出。")
        bring_window_to_front()

        deadline = time.time() + timeout_seconds
        last_reason = ""
        while time.time() < deadline:
            logged, reason = is_logged_in(page, context)
            if reason != last_reason:
                print(f"login_state={reason}")
                last_reason = reason
            if logged:
                print("login_ok=true")
                page.wait_for_timeout(2000)
                return 0
            page.wait_for_timeout(3000)
        print("login_ok=false reason=timeout")
        return 1
    except Exception as exc:
        print(f"authorize_failed={exc.__class__.__name__}: {exc}")
        return 2
    finally:
        close_session(mode, browser, context)
        playwright.stop()


def publish_latest(dry_run=True):
    config = load_config()
    options = toutiao_options(config)
    queue_path = latest_toutiao_queue(config)
    queue, content = read_content_from_queue(queue_path)
    title, body = split_title_body(content)

    print(f"title={title}")
    print(f"body_chars={len(body)}")
    print(f"queue={queue_path}")

    fingerprint = published_fingerprint(title, body)
    print(f"fingerprint={fingerprint}")
    if already_published(fingerprint):
        print("publish_skipped=already_published")
        print("该内容已发布过，跳过以避免重复投稿。")
        return 8

    playwright = sync_playwright().start()
    mode = browser = context = page = None
    publish_responses = []

    def on_response(resp):
        """捕获发布接口的响应，作为发布是否成功的权威判据。"""
        try:
            if resp.request.method != "POST":
                return
            url = resp.url
            if "/article/publish" not in url and "/article/submit" not in url:
                return
            try:
                payload = resp.text()
            except Exception:
                return
            if len(payload) > 4000:
                payload = payload[:4000]
            publish_responses.append({"url": url[:140], "status": resp.status, "body": payload})
        except Exception:
            pass

    try:
        mode, browser, context, page = open_session(playwright)
        print(f"browser_mode={mode}")
        # 页面繁忙时默认 30s 超时容易误判为失败，放宽到 60s
        page.set_default_timeout(60000)
        page.on("response", on_response)

        logged, reason = ensure_logged_in(page, context)
        print(f"login_state={reason}")
        if not logged:
            print("login_required=true")
            print("请先执行：python toutiao_browser.py authorize 完成一次人工登录")
            return 2

        title_selector, body_selector = fill_article(page, title, body)
        print(f"title_selector={title_selector}")
        print(f"body_selector={body_selector}")

        if not title_selector or not body_selector:
            screenshot = LOG_DIR / "toutiao_publish_debug.png"
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            print(f"fill_failed=true screenshot={screenshot}")
            return 3

        page.wait_for_timeout(800)

        actions = set_toutiao_options(page, options)
        print("actions=" + json.dumps(actions, ensure_ascii=False))

        offset = int(options.get("schedule_offset_hours", 0) or 0)
        if offset > 0:
            actions += set_schedule(page, offset)
            print("actions=" + json.dumps(actions, ensure_ascii=False))

        screenshot = LOG_DIR / ("toutiao_publish_dry_run.png" if dry_run else "toutiao_submit_result.png")
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(screenshot), full_page=True, timeout=20000)
        except Exception as exc:
            print(f"screenshot_failed={exc.__class__.__name__}")
        print(f"screenshot={screenshot}")

        if dry_run:
            print("toutiao_publish_dry_run=true")
            print("已填入页面但未点击发布。请在浏览器中检查内容。")
            return 0

        if not validate_required_options(page, options):
            print("required_options_not_ready=true")
            return 4

        if offset > 0:
            confirm_clicked = click_first_match(
                page,
                ["button:has-text('预览并定时发布')", "button:has-text('预览定时发布')"],
                timeout=6000,
            )
            if not confirm_clicked:
                confirm_clicked = click_visible_button_text(page, "预览并定时发布")
            if not confirm_clicked:
                print("schedule_confirm_button_not_found=true")
                return 4
            page.wait_for_timeout(2000)
            click_visible_button_text(page, "确定")
        else:
            # 头条的实际主按钮文案是「预览并发布」（primary 按钮），不是「发布」
            clicked = click_visible_button_text(page, "预览并发布")
            if not clicked:
                clicked = click_first_match(
                    page,
                    ["button:has-text('预览并发布')", "button:has-text('确认发布')"],
                    timeout=6000,
                )
            if not clicked:
                print("publish_button_not_found=true")
                return 4

            # 「预览并发布」会先弹出预览对话框，需要再点一次「确认发布」
            page.wait_for_timeout(3000)
            confirmed = click_visible_button_text(page, "确认发布")
            if not confirmed:
                confirmed = click_visible_button_text(page, "确定")
            if not confirmed:
                confirmed = click_first_match(
                    page,
                    ["button:has-text('确认发布')", "button:has-text('确定')"],
                    timeout=5000,
                )
            print(f"confirm_dialog_clicked={confirmed}")
            page.wait_for_timeout(2000)

        page.wait_for_timeout(10000)
        try:
            body_text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            body_text = ""

        # 权威判据：发布接口返回 code=0
        api_ok = False
        api_detail = ""
        for item in publish_responses:
            body = item["body"]
            try:
                data = json.loads(body)
                code = data.get("code")
            except Exception:
                continue
            payload = data.get("data") or {}
            pgc_id = payload.get("pgc_id")
            if code == 0 and str(pgc_id) not in ("0", "None"):
                api_ok = True
                api_detail = f"code=0 pgc_id={pgc_id}"
                break
            if code == 0 and "content" in payload:
                # 正式发布成功时 data 里回显完整正文
                api_ok = True
                api_detail = "code=0 content_echoed"
                break
            if code not in (0, None) and "7050" not in str(code):
                # 7050 是草稿自动保存失败，与正式发布无关
                api_detail = f"code={code} message={data.get('message')}"
        if not api_detail:
            api_detail = f"captured_responses={len(publish_responses)}"

        # 辅助判据：页面出现成功提示
        success_markers = ["发布成功", "提交成功", "已发布", "审核中", "内容管理", "作品管理"]
        page_success = any(marker in body_text for marker in success_markers)

        print(f"publish_api_ok={api_ok} detail={api_detail}")
        print(f"publish_page_success_detected={page_success}")
        print(f"page_url={page.url}")
        print("page_tail=" + json.dumps(body_text[-400:], ensure_ascii=False))

        page.screenshot(path=str(screenshot), full_page=True)

        if not (api_ok or page_success):
            print("publish_unconfirmed=true")
            print("未检测到发布成功标志，队列标记为待确认，不写入 consumed_at。")
            queue["status"] = "submit_unconfirmed"
            queue["submitted_at"] = time.strftime("%Y%m%d_%H%M%S")
            queue["submit_screenshot"] = str(screenshot)
            queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
            # 结果不确定时也记录指纹，避免重试造成重复投稿；
            # 若确认实际未发布，删除该指纹即可恢复。
            record_published(fingerprint, title, None)
            print(f"fingerprint_recorded_for_review={fingerprint}")
            return 7

        queue["status"] = "submitted"
        queue["submitted_at"] = time.strftime("%Y%m%d_%H%M%S")
        queue["consumed_at"] = queue["submitted_at"]
        queue["submit_screenshot"] = str(screenshot)
        queue["publish_api_detail"] = api_detail
        queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

        pgc_id = None
        for item in publish_responses:
            try:
                data = json.loads(item["body"])
                if data.get("code") == 0:
                    pgc_id = (data.get("data") or {}).get("pgc_id")
                    if pgc_id:
                        break
            except Exception:
                continue
        record_published(fingerprint, title, pgc_id)

        print("toutiao_publish_submitted=true")
        print(f"screenshot={screenshot}")
        return 0
    except PlaywrightTimeoutError:
        print("timeout=true")
        return 5
    except Exception as exc:
        print(f"publish_failed={exc.__class__.__name__}: {exc}")
        return 6
    finally:
        if dry_run:
            print("浏览器保持 20 秒，便于检查页面。")
            time.sleep(20)
        close_session(mode, browser, context)
        playwright.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["authorize", "publish-latest"])
    parser.add_argument("--submit", action="store_true", help="真实点击发布按钮")
    parser.add_argument("--timeout", type=int, default=900, help="authorize 等待登录的秒数")
    args = parser.parse_args()

    if args.command == "authorize":
        sys.exit(authorize(timeout_seconds=args.timeout))
    elif args.command == "publish-latest":
        try:
            sys.exit(publish_latest(dry_run=not args.submit))
        except RuntimeError as exc:
            print(f"publish_skipped={exc}")
            sys.exit(0)


if __name__ == "__main__":
    main()
