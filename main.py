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
    # 先取近期文章，既用于查重，也喂给生成器避免撞题
    recent = storage.recent_texts(compare_count)
    content = generator.generate(now, recent)
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


def _attach_daemon_log():
    """把 daemon 的 stdout/stderr 写到 logs/daemon.log。

    后台启动时不再依赖 PowerShell 的 Start-Process 重定向（那台机器的环境变量
    里有大小写重复键，Start-Process 会直接抛异常），由进程自己落盘更可靠。
    """
    log_dir = ROOT / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "daemon.log"
        if path.exists() and path.stat().st_size > 5 * 1024 * 1024:
            path.replace(log_dir / "daemon.log.1")
        handle = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return None
    sys.stdout = handle
    sys.stderr = handle
    return handle


def _pid_alive(pid):
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def acquire_daemon_lock():
    """同一时刻只允许一个 daemon 实例，避免看门狗把进程越拉越多。

    返回 (状态, 锁文件路径)，状态为 acquired / busy / error。
    """
    lock_path = ROOT / "storage" / "daemon.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.exists():
            try:
                pid = int(json.loads(lock_path.read_text(encoding="utf-8")).get("pid") or 0)
            except (ValueError, json.JSONDecodeError, OSError):
                pid = 0
            if pid and pid != os.getpid() and _pid_alive(pid):
                print(f"daemon_already_running=true pid={pid}")
                return "busy", lock_path
        lock_path.write_text(
            json.dumps(
                {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"daemon_lock_failed={exc}")
        return "error", lock_path
    return "acquired", lock_path


def release_daemon_lock(lock_path):
    try:
        if lock_path and lock_path.exists():
            lock_path.unlink()
    except OSError:
        pass


def daemon(config):
    tz = get_timezone(config)
    log_handle = _attach_daemon_log()
    status, lock_path = acquire_daemon_lock()
    if status == "busy":
        if log_handle:
            log_handle.flush()
        return 1

    try:
        print(f"daemon_started=true pid={os.getpid()} at={datetime.now(tz).isoformat(timespec='seconds')}")
        while True:
            try:
                passed = run_once(config)
            except Exception as exc:  # 单次失败不应中断守护进程
                print(f"run_failed={exc.__class__.__name__}: {exc}")
            else:
                # 只有过审并入队的稿子才去发布，未过审时不碰浏览器
                if passed:
                    publish_toutiao(config, submit=True)
                else:
                    print("publish_skipped=review_not_passed")
            now = datetime.now(tz)
            target = next_run_at(config, now)
            sleep_seconds = max(int((target - now).total_seconds()), 60)
            print(f"next_run_at={target.isoformat()} sleep_seconds={sleep_seconds}")
            time.sleep(sleep_seconds)
    finally:
        release_daemon_lock(lock_path)


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
