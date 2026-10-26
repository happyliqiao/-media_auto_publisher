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


ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "browser_state" / "toutiao"
CONFIG_PATH = ROOT / "config.json"
CREATOR_URL = "https://mp.toutiao.com/profile_v4/index"
PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"
CDP_PORT = 9223


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def edge_path():
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("未找到 Microsoft Edge")


def open_edge(url=CREATOR_URL):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        edge_path(),
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={STATE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=creationflags)
    print("edge_opened=true")
    print(f"debug_port={CDP_PORT}")
    print(f"profile={STATE_DIR}")


def connect():
    playwright = sync_playwright().start()
    last_error = None
    for _ in range(20):
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    else:
        playwright.stop()
        raise last_error
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    return playwright, browser, context


def authorize():
    open_edge(CREATOR_URL)
    print("请在打开的 Edge 窗口中完成今日头条登录/扫码/验证码。")
    print("登录成功并进入创作者后台后，保持这个浏览器窗口打开，再运行 publish-latest。")


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
        first = body.splitlines()[0] if body else "OpenAI Codex 和 Claude Code 使用指南"
        title = re.sub(r"^[#\s]+", "", first).strip()[:30]
    return title[:30], body


def fill_first_match(page, selectors, value, timeout=3000):
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


def type_first_match(page, selectors, value, timeout=3000):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            loc.press("Control+A")
            loc.type(value, delay=20)
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


def click_visible_button_text(page, text):
    buttons = page.locator("button")
    for i in range(buttons.count()):
        button = buttons.nth(i)
        data = button.evaluate(
            """e => {
                const r = e.getBoundingClientRect();
                return {
                    text: (e.innerText || e.textContent || '').trim(),
                    visible: r.width > 0 && r.height > 0
                };
            }"""
        )
        if data["visible"] and data["text"] == text:
            button.click(force=True)
            return True
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


DEFAULT_OPTIONS = {
    "cover": "无封面",
    "ads": "不投放广告",
    "location": "",
    "declaration": "个人观点，仅供参考",
    "sync_weitoutiao": False,
    "schedule_offset_hours": 1,
}


def toutiao_options(config):
    options = dict(DEFAULT_OPTIONS)
    options.update((config.get("platforms", {}).get("toutiao", {}) or {}).get("options", {}) or {})
    return options


def set_toutiao_options(page, options=None):
    options = options or DEFAULT_OPTIONS
    actions = []

    page.set_default_timeout(1500)

    cover = (options.get("cover") or "").strip()
    ads = (options.get("ads") or "").strip()
    declaration = (options.get("declaration") or "").strip()
    location = (options.get("location") or "").strip()

    steps = []
    if cover:
        steps.append((f"cover={cover}", lambda: try_click_text(page, cover)))
    if ads:
        steps.append(
            (
                f"ads={ads}",
                lambda: try_click_text(page, ads)
                or try_click_text(page, "不投放")
                or try_click_text(page, "暂不投放"),
            )
        )
    if options.get("sync_weitoutiao"):
        steps.append(
            (
                "weitoutiao=on",
                lambda: try_click_text(page, "同步发布微头条")
                or try_click_text(page, "发布微头条")
                or try_click_text(page, "同步到微头条")
                or try_click_text(page, "微头条"),
            )
        )
    if declaration:
        steps.append(("declaration=open", lambda: try_click_text(page, "作品声明")))
        for part in [p.strip() for p in declaration.replace("，", ",").split(",") if p.strip()]:
            steps.append((f"declaration={part}", lambda part=part: try_click_text(page, part)))

    for label, fn in steps:
        try:
            if fn():
                actions.append(label)
        except Exception as exc:
            actions.append(f"{label}:failed:{exc.__class__.__name__}")

    if location:
        try:
            location_opened = try_click_text(page, "添加位置") or try_click_text(page, "位置")
        except Exception:
            location_opened = None
        if location_opened:
            selector = type_first_match(
                page,
                [
                    "input[placeholder*='搜索']",
                    "input[placeholder*='位置']",
                    "input[placeholder*='地点']",
                    "input",
                ],
                location,
                timeout=2000,
            )
            page.wait_for_timeout(1500)
            try_click_text(page, location, timeout=2000)
            actions.append(f"location={location} selector={selector}")
    else:
        actions.append("location=skipped")

    offset = int(options.get("schedule_offset_hours", 1) or 0)
    if offset > 0:
        publish_time = datetime.now() + timedelta(hours=offset)
        publish_time = publish_time.replace(minute=0, second=0, microsecond=0)
        if try_click_text(page, "定时发布", timeout=1200):
            actions.append("schedule=open")
            time_text = publish_time.strftime("%Y-%m-%d %H:%M")
            selector = type_first_match(
                page,
                [
                    "input[placeholder*='时间']",
                    "input[placeholder*='日期']",
                    "input[class*='time']",
                    "input",
                ],
                time_text,
                timeout=2000,
            )
            actions.append(f"schedule_time={time_text} selector={selector}")

    return actions


def publish_latest(dry_run=True):
    config = load_config()
    options = toutiao_options(config)
    queue_path = latest_toutiao_queue(config)
    queue, content = read_content_from_queue(queue_path)
    title, body = split_title_body(content)

    print("stage=open_edge")
    open_edge(PUBLISH_URL)
    time.sleep(3)
    print("stage=connect")
    playwright, browser, context = connect()
    page = context.pages[-1] if context.pages else context.new_page()
    try:
        print("stage=goto_publish")
        page.goto(PUBLISH_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        if "login" in page.url.lower() or "sso" in page.url.lower():
            print("login_required=true")
            print("请在浏览器中完成登录后重新运行 publish-latest。")
            return 2

        print("stage=fill_title")
        title_selector = fill_first_match(
            page,
            [
                "textarea[placeholder*='标题']",
                "input[placeholder*='标题']",
                "[contenteditable='true'][data-placeholder*='标题']",
                "[contenteditable='true']:near(:text('标题'))",
            ],
            title,
        )
        print("stage=fill_body")
        body_selector = fill_first_match(
            page,
            [
                "div[contenteditable='true']",
                "textarea[placeholder*='正文']",
                "[contenteditable='true'][data-placeholder*='正文']",
            ],
            body,
        )

        if not title_selector or not body_selector:
            screenshot = ROOT / "logs" / "toutiao_publish_debug.png"
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            print(f"fill_failed=true screenshot={screenshot}")
            return 3

        if dry_run:
            print("stage=set_options")
            actions = set_toutiao_options(page, options)
            screenshot = ROOT / "logs" / "toutiao_publish_dry_run.png"
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            print("toutiao_publish_dry_run=true")
            print(f"title={title}")
            print(f"queue={queue_path}")
            print("actions=" + json.dumps(actions, ensure_ascii=False))
            print(f"screenshot={screenshot}")
            print("已填入页面但未点击发布。请在浏览器中检查内容。")
            return 0

        actions = set_toutiao_options(page, options)
        print("actions=" + json.dumps(actions, ensure_ascii=False))
        clicked = click_first_match(page, ["button:has-text('定时发布')"], timeout=5000)
        if clicked:
            page.wait_for_timeout(1200)
            confirm_clicked = click_first_match(page, ["button:has-text('预览并定时发布')"], timeout=5000)
            if not confirm_clicked:
                confirm_clicked = click_visible_button_text(page, "预览并定时发布")
            if not confirm_clicked:
                print("schedule_confirm_button_not_found=true")
                return 4
            page.wait_for_timeout(2000)
            # Today Toutiao shows a second warning when ads are disabled.
            click_visible_button_text(page, "确定")
        else:
            clicked = click_first_match(page, ["button:has-text('发布')", "text=发布", "button:has-text('发表')"], timeout=5000)

        if not clicked:
            print("publish_button_not_found=true")
            return 4

        page.wait_for_timeout(5000)
        screenshot = ROOT / "logs" / "toutiao_submit_result.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
        queue["status"] = "submitted"
        queue["submitted_at"] = time.strftime("%Y%m%d_%H%M%S")
        queue["consumed_at"] = queue["submitted_at"]
        queue["submit_screenshot"] = str(screenshot)
        queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
        print("toutiao_publish_submitted=true")
        print(f"screenshot={screenshot}")
        return 0
    except PlaywrightTimeoutError:
        print("timeout=true")
        return 5
    finally:
        if dry_run:
            print("浏览器会保持 15 秒，便于你检查页面。")
            time.sleep(15)
        browser.close()
        playwright.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["authorize", "publish-latest"])
    parser.add_argument("--submit", action="store_true", help="真实点击发布按钮")
    args = parser.parse_args()

    if args.command == "authorize":
        authorize()
    elif args.command == "publish-latest":
        sys.exit(publish_latest(dry_run=not args.submit))


if __name__ == "__main__":
    main()
