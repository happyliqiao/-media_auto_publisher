import argparse
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from content_generator import ContentGenerator
from publishers import PublisherManager
from reviewer import ContentReviewer
from scheduler import next_interval_seconds
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

    content = generator.generate(now)
    review = reviewer.review(content)
    saved = storage.save(content, now, review)

    publish_result = publishers.publish(content, saved, review)

    print(f"saved={saved}")
    print(f"review_passed={review['passed']}")
    if review["issues"]:
        print("review_issues=" + "; ".join(review["issues"]))
    print("publish=" + json.dumps(publish_result, ensure_ascii=False))


def daemon(config):
    tz = get_timezone(config)
    print("daemon_started=true")
    while True:
        run_once(config)
        now = datetime.now(tz)
        sleep_seconds = next_interval_seconds(config["start_date"], now)
        print(f"next_run_in_seconds={sleep_seconds}")
        time.sleep(sleep_seconds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run-once", "daemon", "next-interval"])
    args = parser.parse_args()

    config = load_config()
    if args.command == "run-once":
        run_once(config)
    elif args.command == "daemon":
        daemon(config)
    elif args.command == "next-interval":
        tz = get_timezone(config)
        print(next_interval_seconds(config["start_date"], datetime.now(tz)))


if __name__ == "__main__":
    main()
