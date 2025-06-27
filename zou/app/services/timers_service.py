from zou.app.models.timer import Timer
from zou.app.models.task import Task
from zou.app.models.time_spent import TimeSpent
from zou.app.utils import (
    events,
    date_helpers,
    query as query_utils,
    permissions,
)
from zou.app.services import persons_service, user_service
from zou.app.services.exception import TimerNotFoundException


class TimerAlreadyStopped(Exception):
    pass


def get_active_timer(person_id):
    return Timer.get_by(person_id=person_id, end_time=None)


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
    timer.save()
    duration = (timer.end_time - timer.start_time).total_seconds()
    time_spent = TimeSpent.create(
        task_id=timer.task_id,
        person_id=timer.person_id,
        date=timer.date,
        duration=duration,
        timer_id=timer.id,
    )
    task = Task.get(timer.task_id)
    task.duration = sum(
        ts.duration for ts in TimeSpent.get_all_by(task_id=timer.task_id)
    )
    task.save()
    events.emit(
        "time-spent:new",
        {"time_spent_id": str(time_spent.id)},
        project_id=str(task.project_id),
    )
    events.emit(
        "task:update",
        {"task_id": timer.task_id},
        project_id=str(task.project_id),
    )
    events.emit(
        "timer:end",
        {"timer_id": str(timer.id)},
        project_id=str(task.project_id),
    )
    return time_spent.serialize()


def discard_timer(timer_id=None):
    person_id = persons_service.get_current_user()["id"]
    timer = Timer.get(timer_id) if timer_id else get_active_timer(person_id)
    if timer is None:
        raise TimerNotFoundException()
    if str(timer.person_id) != person_id:
        raise permissions.PermissionDenied
    if timer.end_time is not None:
        # already ended, just remove
        pass
    task = Task.get(timer.task_id)
    project_id = str(task.project_id)
    timer.delete()
    events.emit(
        "timer:delete", {"timer_id": str(timer.id)}, project_id=project_id
    )


def update_start_time(timer_id, start_time):
    """Update the start time of a timer."""

    timer = Timer.get(timer_id)
    if timer is None:
        raise TimerNotFoundException()
    user_service.check_timer_access(timer_id)
    if timer.end_time is not None:
        raise TimerAlreadyStopped()
    timer.start_time = start_time
    timer.date = start_time.date()
    timer.save()
    task = Task.get(timer.task_id)
    events.emit(
        "timer:update",
        {"timer_id": str(timer.id)},
        project_id=str(task.project_id),
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
