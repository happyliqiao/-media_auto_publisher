import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from content_generator import ContentGenerator
from publishers import PublisherManager
from reviewer import ContentReviewer
from scheduler import next_run_at, planned_slots_for_day, publish_window
from storage import ContentStorage


# 后台运行时 stdout 会被重定向到日志文件，Python 默认块缓冲会让日志长时间为空
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_CONFIG_PATH = ROOT / "config.example.json"


def load_config():
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    # 云端（GitHub Actions / Linux 服务器）用环境变量覆盖本地路径，
    # 这样同一份 config.example.json 可以在 Windows 和 Linux 上复用。
    storage_dir = os.getenv("MAP_STORAGE_DIR")
    if storage_dir:
        config["storage_dir"] = storage_dir
    dry_run = os.getenv("MAP_DRY_RUN")
    if dry_run is not None:
        config["dry_run"] = dry_run.strip().lower() in {"1", "true", "yes", "on"}
    timezone_name = os.getenv("MAP_TIMEZONE")
    if timezone_name:
        config["timezone"] = timezone_name
    publish_hours = os.getenv("MAP_PUBLISH_HOURS")
    if publish_hours:
        try:
            start_h, end_h = [int(x) for x in publish_hours.split(",")[:2]]
            config.setdefault("schedule", {})["publish_hours"] = [start_h, end_h]
        except ValueError:
            print(f"warning=invalid MAP_PUBLISH_HOURS value={publish_hours}")
    return config


def get_timezone(config):
    name = config.get("timezone", "Asia/Shanghai")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name in {"Asia/Shanghai", "Asia/Chongqing", "Asia/Harbin"}:
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        return timezone.utc


def run_once(config):
    tz = get_timezone(config)
    now = datetime.now(tz)

    generator = ContentGenerator(config)
    reviewer = ContentReviewer(config)
    storage = ContentStorage(config)
    publishers = PublisherManager(config)

    compare_count = int(config.get("review", {}).get("recent_compare_count", 20))
    content = generator.generate(now)
    recent = storage.recent_texts(compare_count)
    review = reviewer.review(content, recent)
    # 未通过审核（例如与近期内容重复）的稿件不进入正式存档和查重基线
    saved = storage.save(content, now, review, rejected=not review["passed"])

    publish_result = publishers.publish(content, saved, review)

    print(f"title={review.get('title', '')}")
    print(f"saved={saved}")
    print(f"review_passed={review['passed']}")
    print(f"char_count={review['char_count']}")
    if review["issues"]:
        print("review_issues=" + "; ".join(review["issues"]))
    print("publish=" + json.dumps(publish_result, ensure_ascii=False))
    return review["passed"]


def publish_toutiao(config, submit=True):
    """驱动浏览器把队列里最新的一篇发到今日头条。

    缺依赖、需要人工登录、遇到风控等情况都只记录日志，不抛出异常，
    保证 daemon 不会因为发布失败而中断。
    """
    toutiao_cfg = (config.get("platforms", {}) or {}).get("toutiao", {}) or {}
    if not toutiao_cfg.get("enabled", False):
        print("publish_skipped=platform_disabled")
        return None
    if config.get("dry_run", True):
        print("publish_skipped=dry_run")
        return None

    # 只在约定的发布时段内真正发稿，避免开机瞬间在凌晨也发出去
    tz = get_timezone(config)
    now = datetime.now(tz)
    start_h, end_h = publish_window(config)
    if not start_h <= now.hour < end_h:
        print(f"publish_skipped=outside_window now={now.strftime('%H:%M')} window=[{start_h},{end_h})")
        return None

    try:
        import toutiao_browser
    except ImportError as exc:
        print(f"publish_skipped=playwright_missing ({exc})")
        print("    提示：执行 pip install -r requirements.txt 安装浏览器自动化依赖")
        return None

    try:
        return toutiao_browser.publish_latest(dry_run=not submit)
    except Exception as exc:
        print(f"publish_failed={exc.__class__.__name__}: {exc}")
        return None


def daemon(config):
    tz = get_timezone(config)
    print("daemon_started=true")
    while True:
        try:
            run_once(config)
        except Exception as exc:  # 单次失败不应中断守护进程
            print(f"run_failed={exc.__class__.__name__}: {exc}")
        else:
            # 生成通过审核并入队后，立刻尝试发布，发布时刻≈本轮排期时间
            publish_toutiao(config, submit=True)
        now = datetime.now(tz)
        target = next_run_at(config, now)
        sleep_seconds = max(int((target - now).total_seconds()), 60)
        print(f"next_run_at={target.isoformat()} sleep_seconds={sleep_seconds}")
        time.sleep(sleep_seconds)


def plan(config):
    tz = get_timezone(config)
    now = datetime.now(tz)
    slots = planned_slots_for_day(config, now)
    print(f"date={now.date().isoformat()}")
    print(f"slots={len(slots)}")
    for slot in slots:
        print(slot.strftime("%Y-%m-%d %H:%M"))
    print(f"next_run_at={next_run_at(config, now).isoformat()}")


def toggle_publish(enable):
    """一键开关真实发布：同时改 dry_run 与 platforms.toutiao.enabled。"""
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["dry_run"] = not enable
    cfg.setdefault("platforms", {}).setdefault("toutiao", {})["enabled"] = enable
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"config={path}")
    print(f"dry_run={cfg['dry_run']}")
    print(f"toutiao.enabled={cfg['platforms']['toutiao']['enabled']}")
    if enable:
        print("下一步：先执行 python toutiao_browser.py authorize 完成一次人工登录")
    else:
        print("已回到「只生成不发布」模式")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "run-once",
            "daemon",
            "next-interval",
            "plan",
            "publish-now",
            "publish-dry-run",
            "enable-publish",
            "disable-publish",
        ],
    )
    parser.add_argument("--submit", action="store_true", help="publish-now 默认只填页面不点发布")
    args = parser.parse_args()

    config = load_config()
    if args.command == "run-once":
        run_once(config)
    elif args.command == "daemon":
        daemon(config)
    elif args.command == "next-interval":
        tz = get_timezone(config)
        now = datetime.now(tz)
        target = next_run_at(config, now)
        print(f"next_run_at={target.isoformat()}")
        print(f"sleep_seconds={max(int((target - now).total_seconds()), 60)}")
    elif args.command == "plan":
        plan(config)
    elif args.command == "publish-now":
        publish_toutiao(config, submit=args.submit)
    elif args.command == "publish-dry-run":
        publish_toutiao(config, submit=False)
    elif args.command == "enable-publish":
        toggle_publish(True)
    elif args.command == "disable-publish":
        toggle_publish(False)


if __name__ == "__main__":
    main()
