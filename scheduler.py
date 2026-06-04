from datetime import datetime, time, timedelta


def interval_hours_for_date(start_date: str, now: datetime) -> int:
    start = datetime.fromisoformat(start_date).date()
    days = max((now.date() - start).days, 0)
    week = days // 7 + 1
    if week == 1:
        return 4
    if week == 2:
        return 3
    if week == 3:
        return 2
    return 1


def next_interval_seconds(start_date: str, now: datetime) -> int:
    hours = interval_hours_for_date(start_date, now)
    return hours * 60 * 60


def planned_slots_for_day(start_date: str, day: datetime):
    hours = interval_hours_for_date(start_date, day)
    current = datetime.combine(day.date(), time.min, tzinfo=day.tzinfo)
    slots = []
    while current.date() == day.date():
        slots.append(current)
        current = current + timedelta(hours=hours)
    return slots
