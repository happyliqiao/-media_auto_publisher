import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "browser_state" / "toutiao"
QUEUE_DIR = Path(r"E:\AI_Content_AutoPublish\_publish_queue\toutiao")
PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"
CDP_URL = "http://127.0.0.1:9223"

WUHAN = "武汉"
NETWORK = "取材网络"
PERSONAL = "个人观点，仅供参考"
SCHEDULE = "定时发布"
CONFIRM_SCHEDULE = "预览并定时发布"
OK = "确定"
CONFIRM_SCHEDULE_CANDIDATES = ["预览并定时发布", "预览定时发布", "预览并发布"]
FINAL_CONFIRM_CANDIDATES = ["确认发布", "确定发布", "发布"]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def visible_buttons(page):
    buttons = page.locator("button")
    out = []
    for i in range(buttons.count()):
        data = buttons.nth(i).evaluate(
            """e => {
                const r = e.getBoundingClientRect();
                return {
                    text: (e.innerText || e.textContent || '').trim(),
                    visible: r.width > 0 && r.height > 0,
                    x: r.x,
                    y: r.y,
                    w: r.width,
                    h: r.height
                };
            }"""
        )
        if data["visible"]:
            out.append((i, data))
    return out


def click_button_text(page, text):
    for i, data in visible_buttons(page):
        if data["text"] == text:
            page.locator("button").nth(i).click(force=True)
            print(json.dumps({"clicked": text, "index": i}, ensure_ascii=False))
            return True
    print(json.dumps({"not_found": text}, ensure_ascii=False))
    return False


def click_any_button_text(page, texts):
    for text in texts:
        if click_button_text(page, text):
            return text
    return None


def click_text(page, text):
    for selector in [f"text={text}", f"label:has-text('{text}')", f"span:has-text('{text}')"]:
        try:
            loc = page.locator(selector).last
            loc.wait_for(state="visible", timeout=1500)
            loc.click(force=True)
            return selector
        except Exception:
            continue
    return None


def close_modal_if_open(page):
    for i, data in reversed(visible_buttons(page)):
        if data["text"] == "" and data["w"] >= 40 and data["h"] >= 40 and data["x"] > 850:
            page.locator("button").nth(i).click(force=True)
            page.wait_for_timeout(800)
            print(json.dumps({"modal_closed": i}, ensure_ascii=False))
            return True
    return False


def latest_queue_content():
    files = sorted(QUEUE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("no toutiao queue file")
    queue = files[0]
    obj = json.loads(queue.read_text(encoding="utf-8"))
    content_file = Path(obj["content_file"])
    markdown = content_file.read_text(encoding="utf-8")
    return queue, markdown


def split_title_body(markdown):
    lines = markdown.strip().splitlines()
    title = ""
    body = []
    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        body.append(line)
    if not title:
        title = "AI编程免费一个月怎么用"
    return title[:30], "\n".join(body).strip()


def fill_article(page, title, body):
    page.goto(PUBLISH_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    title_box = page.locator("textarea").first
    title_box.wait_for(state="visible", timeout=10000)
    title_box.click()
    title_box.fill(title)

    editor = page.locator(".ProseMirror").first
    editor.wait_for(state="visible", timeout=10000)
    editor.evaluate(
        """(el, text) => {
            el.innerText = text;
            el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        body,
    )
    page.wait_for_timeout(2000)
    print(json.dumps({"filled_title": title, "body_chars": len(body)}, ensure_ascii=False))


def click_label(page, text, desired_checked=True):
    locators = [
        page.locator(".byte-radio, .byte-checkbox"),
        page.locator("label"),
    ]
    for loc in locators:
        for i in range(loc.count()):
            data = loc.nth(i).evaluate(
            """e => {
                const input = e.querySelector('input');
                const inner = e.querySelector('.byte-radio-inner, .byte-checkbox-inner');
                return {
                    text:(e.innerText || e.textContent || '').trim(),
                    cls:String(e.className),
                    checked: (input ? input.checked : false) || String(e.className).includes('checked') || (inner ? String(inner.className).includes('checked') : false)
                };
            }"""
            )
            if data["text"] == text:
                is_checked = data["checked"]
                if is_checked != desired_checked:
                    loc.nth(i).scroll_into_view_if_needed(timeout=5000)
                    page.wait_for_timeout(300)
                    loc.nth(i).click(force=True)
                    page.wait_for_timeout(500)
                return True

    for loc in locators:
        for i in range(loc.count()):
            data = loc.nth(i).evaluate(
                "e => ({text:(e.innerText || e.textContent || '').trim()})"
            )
            if text in data["text"]:
                loc.nth(i).scroll_into_view_if_needed(timeout=5000)
                page.wait_for_timeout(300)
                loc.nth(i).click(force=True)
                page.wait_for_timeout(500)
                return True
    return bool(click_text(page, text))


def label_checked(page, text):
    loc = page.locator(".byte-radio, .byte-checkbox, label")
    for i in range(loc.count()):
        data = loc.nth(i).evaluate(
            """e => {
                const input = e.querySelector('input');
                const inner = e.querySelector('.byte-radio-inner, .byte-checkbox-inner');
                return {
                    text:(e.innerText || e.textContent || '').trim(),
                    cls:String(e.className),
                    checked: (input ? input.checked : false) || String(e.className).includes('checked') || (inner ? String(inner.className).includes('checked') : false)
                };
            }"""
        )
        if data["text"] == text:
            return data["checked"]
    return None


def ensure_option_checked(page, text, selector=".byte-radio, .byte-checkbox", timeout_ms=3000):
    option = page.locator(selector, has_text=text).first
    option.wait_for(state="visible", timeout=timeout_ms)
    for _ in range(3):
        checked = option.evaluate("e => !!e.querySelector('input')?.checked")
        if checked:
            return True
        option.scroll_into_view_if_needed(timeout=timeout_ms)
        option.click(force=True)
        page.wait_for_timeout(700)
    return option.evaluate("e => !!e.querySelector('input')?.checked")


def set_location(page):
    selector = page.locator(".position-select").first
    text = selector.inner_text(timeout=3000).strip()
    if WUHAN in text:
        print(json.dumps({"location": text}, ensure_ascii=False))
        return True

    selector.click(force=True)
    page.wait_for_timeout(500)
    page.keyboard.press("Control+A")
    page.keyboard.type(WUHAN, delay=80)
    page.wait_for_timeout(1800)

    candidates = [
        f".byte-select-option:has-text('{WUHAN}')",
        f"[class*='option']:has-text('{WUHAN}')",
        f"text={WUHAN}",
    ]
    for candidate in candidates:
        try:
            loc = page.locator(candidate).last
            loc.wait_for(state="visible", timeout=2000)
            loc.click(force=True)
            page.wait_for_timeout(800)
            break
        except Exception:
            continue

    text = selector.inner_text(timeout=3000).strip()
    print(json.dumps({"location": text}, ensure_ascii=False))
    return WUHAN in text


def set_statement(page):
    labels = page.locator("label")
    result = []
    for i in range(labels.count()):
        data = labels.nth(i).evaluate(
            "e => ({text:(e.innerText || e.textContent || '').trim(), cls:String(e.className)})"
        )
        if data["text"] == NETWORK and "checked" in data["cls"]:
            labels.nth(i).click(force=True)
            result.append({"unchecked": NETWORK, "index": i})
        if data["text"] == PERSONAL and "checked" not in data["cls"]:
            labels.nth(i).click(force=True)
            result.append({"checked": PERSONAL, "index": i})
    page.wait_for_timeout(800)
    print(json.dumps({"statement_actions": result}, ensure_ascii=False))


def submit_schedule(page):
    has_confirm = any(data["text"] in CONFIRM_SCHEDULE_CANDIDATES for _, data in visible_buttons(page))
    if not has_confirm:
        if not click_button_text(page, SCHEDULE):
            return False
        page.wait_for_timeout(1500)
    if not click_any_button_text(page, CONFIRM_SCHEDULE_CANDIDATES):
        return False
    page.wait_for_timeout(2500)
    click_any_button_text(page, FINAL_CONFIRM_CANDIDATES)
    page.wait_for_timeout(2500)
    click_button_text(page, OK)
    page.wait_for_timeout(12000)
    return True


def validate_required_options(page):
    checks = {
        "cover_none": label_checked(page, "无封面"),
        "no_ads": label_checked(page, "不投放广告"),
        "personal_statement": label_checked(page, "个人观点，仅供参考"),
    }
    print(json.dumps({"option_checks": checks}, ensure_ascii=False))
    return all(checks.values())


def update_latest_queue(status, scheduled_time=None):
    files = sorted(QUEUE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    q = files[0]
    try:
        obj = json.loads(q.read_text(encoding="utf-8"))
    except Exception:
        obj = {"platform": "toutiao"}
    obj["status"] = status
    obj["submitted_at"] = time.strftime("%Y%m%d_%H%M%S")
    if scheduled_time:
        obj["scheduled_publish_time"] = scheduled_time
    obj["toutiao_state"] = "reviewing" if status == "submitted" else status
    q.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(q)


def edge_path():
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def open_browser(playwright):
    try:
        browser = playwright.chromium.connect_over_cdp(CDP_URL, timeout=3000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[-1] if context.pages else context.new_page()
        return "cdp", browser, context, page
    except Exception:
        pass

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    launch_args = ["--no-first-run", "--no-default-browser-check"]
    kwargs = {
        "user_data_dir": str(STATE_DIR),
        "headless": False,
        "args": launch_args,
    }
    executable = edge_path()
    if executable:
        kwargs["executable_path"] = executable
        kwargs["channel"] = None
    context = playwright.chromium.launch_persistent_context(**kwargs)
    page = context.pages[-1] if context.pages else context.new_page()
    return "persistent", None, context, page


def close_browser(mode, browser, context):
    if mode == "cdp" and browser:
        browser.close()
    else:
        context.close()


def main():
    queue, markdown = latest_queue_content()
    title, body = split_title_body(markdown)
    p = sync_playwright().start()
    mode, browser, context, page = open_browser(p)
    print(json.dumps({"browser_mode": mode}, ensure_ascii=False))
    page.set_default_timeout(10000)

    close_modal_if_open(page)
    fill_article(page, title, body)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    print(json.dumps({"cover_none_checked": ensure_option_checked(page, "无封面", ".byte-radio")}, ensure_ascii=False))
    location_ok = set_location(page)
    click_label(page, "不投放广告", desired_checked=True)
    print(json.dumps({"no_ads_checked": label_checked(page, "不投放广告")}, ensure_ascii=False))
    click_label(page, "发布得更多收益", desired_checked=True)
    set_statement(page)
    if not validate_required_options(page):
        submitted = False
        print("required_options_not_ready=true")
    else:
        submitted = submit_schedule(page)

    body = page.locator("body").inner_text(timeout=5000)
    scheduled = None
    marker = "将于 "
    if marker in body and "发布" in body:
        start = body.find(marker) + len(marker)
        end = body.find(" 发布", start)
        if end > start:
            scheduled = body[start:end]
    queue = update_latest_queue("submitted" if submitted else "submit_failed", scheduled)
    result = {
        "submitted": submitted,
        "location_ok": location_ok,
        "url": page.url,
        "title": page.title(),
        "scheduled": scheduled,
        "queue": queue,
        "tail": body[-800:],
    }
    print(json.dumps(result, ensure_ascii=False))
    close_browser(mode, browser, context)
    p.stop()


if __name__ == "__main__":
    main()
