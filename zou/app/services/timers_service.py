import datetime

from pytz import UTC
from pytz import timezone as pytz_timezone
from sqlalchemy import or_

from zou.app.models.task import Task
from zou.app.models.time_spent import TimeSpent
from zou.app.models.timer import Timer
from zou.app.services import persons_service, tasks_service, user_service
from zou.app.services.exception import (
    TimerNotFoundException,
    WrongParameterException,
)
from zou.app.utils import date_helpers, events, fields
from zou.app.utils import query as query_utils


class TimerAlreadyStopped(Exception):
    pass


def get_active_timer(person_id):
    return Timer.get_by(person_id=person_id, end_time=None)


def get_running_timer(person_id):
    """Return the current running timer for given person if any."""

    timer = get_active_timer(person_id)
    if timer is not None:
        return timer.serialize()
    return None


def start_timer(task_id, person_id):
    active = get_active_timer(person_id)
    if active is not None:
        end_timer(active.id)
    now = date_helpers.get_utc_now_datetime()
    timer = Timer.create(
        task_id=task_id,
        person_id=person_id,
        date=now.date(),
        start_time=now,
    )
    task = Task.get(task_id)
    events.emit(
        "timer:new",
        {"timer_id": str(timer.id)},
        project_id=str(task.project_id),
    )
    return timer.serialize()


def end_timer(timer_id=None):
    person_id = persons_service.get_current_user()["id"]
    timer = Timer.get(timer_id) if timer_id else get_active_timer(person_id)
    if timer is None:
        raise TimerNotFoundException()
    if timer.end_time is not None:
        raise TimerAlreadyStopped()
    now = date_helpers.get_utc_now_datetime()
    timer.end_time = now
    duration = round((timer.end_time - timer.start_time).total_seconds() / 60)
    if duration <= 0:
        delete_timer(timer.id)
        raise WrongParameterException("Timer too short")
    timer.save()
    task = Task.get(timer.task_id)
    _sync_timer_time_spents(timer, str(task.project_id))
    events.emit(
        "timer:end",
        {"timer_id": str(timer.id)},
        project_id=str(task.project_id),
    )
    time_spents = TimeSpent.get_all_by(timer_id=timer.id)
    latest_time_spent = max(time_spents, key=lambda time_spent: time_spent.date)
    return latest_time_spent.serialize()


def discard_timer():
    """Discard the current active timer for the logged user."""
    person_id = persons_service.get_current_user()["id"]
    timer = get_active_timer(person_id)
    if timer is None:
        raise TimerNotFoundException()
    return delete_timer(timer.id)


def delete_timer(timer_id):
    """Remove a timer and its related time spent if any."""

    timer = Timer.get(timer_id)
    if timer is None:
        raise TimerNotFoundException()
    user_service.check_timer_access(timer_id, allow_admin=True)

    task = Task.get(timer.task_id)
    project_id = str(task.project_id)

    time_spents = TimeSpent.get_all_by(timer_id=timer.id)
    for time_spent in time_spents:
        time_spent.delete()
        events.emit(
            "time-spent:delete",
            {"time_spent_id": str(time_spent.id)},
            project_id=project_id,
        )

    timer.delete()
    events.emit(
        "timer:delete", {"timer_id": str(timer.id)}, project_id=project_id
    )

    task.duration = sum(
        ts.duration for ts in TimeSpent.get_all_by(task_id=timer.task_id)
    )
    task.save()
    events.emit(
        "task:update", {"task_id": str(task.id)}, project_id=project_id
    )


def update_timer(timer_id, start_time=None, end_time=None):
    """Update start and/or end time of a timer."""

    timer = Timer.get(timer_id)
    if timer is None:
        raise TimerNotFoundException()
    user_service.check_timer_access(timer_id)

    new_start = start_time if start_time is not None else timer.start_time
    new_end = end_time if end_time is not None else timer.end_time

    #  is the NEW interval entirely inside an existing timer?
    container_q = Timer.query.filter(
        Timer.person_id == timer.person_id, Timer.id != timer.id
    ).filter(Timer.start_time <= new_start)
    if new_end is None:
        # this timer is still open -> any other still-open timer that started earlier encloses it
        container_q = container_q.filter(Timer.end_time.is_(None))
    else:
        # other timer must end at/after the new end
        container_q = container_q.filter(
            (Timer.end_time.is_(None)) | (Timer.end_time >= new_end)
        )

    if container_q.first() is not None:
        raise WrongParameterException("Timer cannot be inside another timer")

    now = date_helpers.get_utc_now_datetime()
    if new_start > now or (new_end is not None and new_end > now):
        raise WrongParameterException("Timer cannot be set in the future")

    if new_end is not None and new_end <= new_start:
        raise WrongParameterException("End time must be after start time")

    # Check if other timers are inside the new start and end times
    contained = _find_timers_inside(
        timer.person_id, new_start, new_end, timer.id
    )
    if contained:
        raise WrongParameterException("Timer cannot be inside another timer")

    # Adjust other timers if the new start or end time overlaps with them
    if start_time is not None:
        overlapping = (
            Timer.query.filter(Timer.person_id == timer.person_id)
            .filter(Timer.id != timer.id)
            .filter(Timer.start_time < start_time)
            .filter((Timer.end_time == None) | (Timer.end_time > start_time))
            .all()
        )
        for other in overlapping:
            update_timer(other.id, end_time=start_time)

    if end_time is not None:
        overlapping = (
            Timer.query.filter(Timer.person_id == timer.person_id)
            .filter(Timer.id != timer.id)
            .filter(Timer.start_time < end_time)
            .filter((Timer.end_time == None) | (Timer.end_time > end_time))
            .all()
        )
        for other in overlapping:
            update_timer(other.id, start_time=end_time)

    if start_time is not None:
        timer.start_time = start_time
        timer.date = start_time.date()

    if end_time is not None:
        timer.end_time = end_time

    timer.save()

    project_id = str(Task.get(timer.task_id).project_id)

    if timer.end_time is not None:
        _sync_timer_time_spents(timer, project_id)

    events.emit(
        "timer:update", {"timer_id": str(timer.id)}, project_id=project_id
    )
    return timer.serialize()


def get_timers_for_task(task_id, page=0, limit=None):
    """Return timers for a given task with optional pagination."""

    person_id = persons_service.get_current_user()["id"]
    query = (
        Timer.query.filter(Timer.task_id == task_id)
        .filter(Timer.person_id == person_id)
        .order_by(Timer.start_time.desc())
    )
    return query_utils.get_paginated_results(query, page, limit)


def get_timers_for_user(person_id, date=None, embed_task=False):
    """Return timers for a given user filtered by day.

    Timers are ordered by start time descending. When ``embed_task`` is True,
    each timer dict includes a ``task`` field containing the serialized task it
    is related to.
    """

    query = Timer.query.filter(Timer.person_id == person_id)

    if date is not None:
        day = date_helpers.get_date_from_string(date)
        tz = pytz_timezone(str(user_service.get_timezone()))
        start_local = tz.localize(
            datetime.datetime.combine(day, datetime.time.min)
        )
        end_local = start_local + datetime.timedelta(days=1)
        start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_local.astimezone(UTC).replace(tzinfo=None)
        query = query.filter(
            Timer.start_time < end_utc,
            or_(Timer.end_time.is_(None), Timer.end_time > start_utc),
        )

    query = query.order_by(Timer.start_time.desc())
    timers = fields.serialize_models(query.all())

    if embed_task:
        cache = {}
        for timer in timers:
            task_id = timer["task_id"]
            if task_id not in cache:
                cache[task_id] = tasks_service.get_task(task_id)
            timer["task"] = cache[task_id]

    return timers


def _find_timers_inside(person_id, outer_start, outer_end, exclude_id):
    """
    Return any timers (except *exclude_id*) that are fully contained
    inside the interval [outer_start, outer_end].

    If *outer_end* is None the interval is considered still running,
    so we must look for:
      * other running timers   (end_time is NULL)   OR
      * past timers that have already finished      (end_time <= now)
    """

    q = Timer.query.filter(
        Timer.person_id == person_id,
        Timer.id != exclude_id,
        Timer.start_time >= outer_start,  # starts after / at outer_start
    )

    if outer_end is None:  # edited timer is still running
        now = date_helpers.get_utc_now_datetime()
        q = q.filter(
            (Timer.end_time.is_(None))  # running
            | (Timer.end_time <= now)  # closed before "now"
        )
    else:
        q = q.filter(
            Timer.end_time.isnot(None),
            Timer.end_time <= outer_end,  # finishes before / at outer_end
        )

    return q.all()


def _get_timer_timezone(timer):
    person = persons_service.get_person_raw(timer.person_id)
    return pytz_timezone(str(person.timezone or user_service.get_timezone()))


def _get_timer_day_durations(timer):
    if timer.end_time is None:
        return {}

    total_minutes = round(
        (timer.end_time - timer.start_time).total_seconds() / 60
    )
    if total_minutes <= 0:
        return {}

    timezone = _get_timer_timezone(timer)
    start_utc = UTC.localize(timer.start_time)
    end_utc = UTC.localize(timer.end_time)
    start_local = start_utc.astimezone(timezone)
    end_local = end_utc.astimezone(timezone)

    current_day = start_local.date()
    last_day = end_local.date()
    segments = []
    while current_day <= last_day:
        day_start = timezone.localize(
            datetime.datetime.combine(current_day, datetime.time.min)
        )
        next_day = timezone.localize(
            datetime.datetime.combine(
                current_day + datetime.timedelta(days=1),
                datetime.time.min,
            )
        )
        overlap_start = max(start_local, day_start)
        overlap_end = min(end_local, next_day)
        if overlap_end > overlap_start:
            raw_minutes = (overlap_end - overlap_start).total_seconds() / 60
            whole_minutes = int(raw_minutes)
            segments.append(
                {
                    "date": current_day,
                    "minutes": whole_minutes,
                    "fraction": raw_minutes - whole_minutes,
                }
            )
        current_day += datetime.timedelta(days=1)

    distributed_minutes = sum(segment["minutes"] for segment in segments)
    remainder = max(total_minutes - distributed_minutes, 0)
    for segment in sorted(
        segments, key=lambda value: value["fraction"], reverse=True
    )[:remainder]:
        segment["minutes"] += 1

    return {
        segment["date"]: segment["minutes"]
        for segment in segments
        if segment["minutes"] > 0
    }


def _sync_timer_time_spents(timer, project_id):
    desired = _get_timer_day_durations(timer)
    existing = {
        time_spent.date: time_spent
        for time_spent in TimeSpent.get_all_by(timer_id=timer.id)
    }

    for date, time_spent in existing.items():
        if date not in desired:
            time_spent.delete()
            events.emit(
                "time-spent:delete",
                {"time_spent_id": str(time_spent.id)},
                project_id=project_id,
            )

    for date, duration in desired.items():
        time_spent = existing.get(date)
        if time_spent is None:
            time_spent = TimeSpent.create(
                task_id=timer.task_id,
                person_id=timer.person_id,
                date=date,
                duration=duration,
                timer_id=timer.id,
            )
            events.emit(
                "time-spent:new",
                {"time_spent_id": str(time_spent.id)},
                project_id=project_id,
            )
        elif time_spent.duration != duration:
            time_spent.duration = duration
            time_spent.save()
            events.emit(
                "time-spent:update",
                {"time_spent_id": str(time_spent.id)},
                project_id=project_id,
            )

    task = Task.get(timer.task_id)
    task.duration = sum(
        time_spent.duration
        for time_spent in TimeSpent.get_all_by(task_id=timer.task_id)
    )
    task.save()
    tasks_service.clear_task_cache(str(task.id))
    events.emit(
        "task:update", {"task_id": str(task.id)}, project_id=project_id
    )
