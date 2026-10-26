import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from content_generator import ContentGenerator
from publishers import PublisherManager
from reviewer import ContentReviewer
from scheduler import next_run_at, planned_slots_for_day
from storage import ContentStorage


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_CONFIG_PATH = ROOT / "config.example.json"


def load_config():
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    saved = storage.save(content, now, review)

    publish_result = publishers.publish(content, saved, review)

    print(f"title={review.get('title', '')}")
    print(f"saved={saved}")
    print(f"review_passed={review['passed']}")
    print(f"char_count={review['char_count']}")
    if review["issues"]:
        print("review_issues=" + "; ".join(review["issues"]))
    print("publish=" + json.dumps(publish_result, ensure_ascii=False))
    return review["passed"]


def daemon(config):
    tz = get_timezone(config)
    print("daemon_started=true")
    while True:
        try:
            run_once(config)
        except Exception as exc:  # 单次失败不应中断守护进程
            print(f"run_failed={exc.__class__.__name__}: {exc}")
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run-once", "daemon", "next-interval", "plan"])
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


if __name__ == "__main__":
    main()
