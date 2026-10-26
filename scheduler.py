from datetime import datetime, time, timedelta


DEFAULT_STAGES = [
    {"until_week": 1, "interval_hours": 4},
    {"until_week": 2, "interval_hours": 3},
    {"until_week": 3, "interval_hours": 2},
    {"until_week": 0, "interval_hours": 1},
]

DEFAULT_PUBLISH_HOURS = [7, 23]


def _schedule_cfg(config):
    return config.get("schedule", {}) or {}


def start_date(config):
    return _schedule_cfg(config).get("start_date") or config.get("start_date")


def week_index(config, now):
    raw = start_date(config)
    if not raw:
        return 1
    start = datetime.fromisoformat(raw).date()
    days = max((now.date() - start).days, 0)
    return days // 7 + 1


def interval_hours_for_date(config, now):
    """按周递增发布频率；stages 中 until_week 为 0 表示兜底档位。"""
    stages = _schedule_cfg(config).get("stages") or DEFAULT_STAGES
    week = week_index(config, now)
    for stage in stages:
        until = int(stage.get("until_week", 0) or 0)
        if until == 0 or week <= until:
            return max(int(stage.get("interval_hours", 1)), 1)
    return max(int(stages[-1].get("interval_hours", 1)), 1)


def publish_window(config):
    hours = _schedule_cfg(config).get("publish_hours") or DEFAULT_PUBLISH_HOURS
    try:
        start_h, end_h = int(hours[0]), int(hours[1])
    except (TypeError, IndexError, ValueError):
        return 0, 24
    if not 0 <= start_h < end_h <= 24:
        return 0, 24
    return start_h, end_h


def clamp_to_window(config, target):
    """把发布时间推回允许的时段内，避免凌晨发稿。"""
    start_h, end_h = publish_window(config)
    if start_h <= target.hour < end_h:
        return target
    if target.hour < start_h:
        return target.replace(hour=start_h, minute=0, second=0, microsecond=0)
    return (target + timedelta(days=1)).replace(hour=start_h, minute=0, second=0, microsecond=0)


def next_run_at(config, now):
    interval = timedelta(hours=interval_hours_for_date(config, now))
    return clamp_to_window(config, now + interval)


def next_interval_seconds(config, now):
    return int(max((next_run_at(config, now) - now).total_seconds(), 60))


def planned_slots_for_day(config, day):
    """返回某一天在发布时段内的计划时间点，便于预览排期。"""
    hours = interval_hours_for_date(config, day)
    start_h, end_h = publish_window(config)
    current = datetime.combine(day.date(), time(hour=start_h), tzinfo=day.tzinfo)
    day_end = datetime.combine(day.date(), time.min, tzinfo=day.tzinfo) + timedelta(days=1)
    slots = []
    while current < day_end and current.hour < end_h:
        slots.append(current)
        current = current + timedelta(hours=hours)
    return slots
