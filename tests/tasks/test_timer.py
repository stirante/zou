import datetime
import time

from pytz import timezone

from tests.base import ApiDBTestCase
from zou.app import config
from zou.app.models.task import Task
from zou.app.models.time_spent import TimeSpent
from zou.app.models.timer import Timer
from zou.app.utils import date_helpers


class TimerTestCase(ApiDBTestCase):
    def setUp(self):
        super(TimerTestCase, self).setUp()
        self.generate_fixture_project_status()
        self.generate_fixture_project()
        self.generate_fixture_asset_type()
        self.generate_fixture_asset()
        self.generate_fixture_sequence()
        self.generate_fixture_shot()
        self.generate_fixture_department()
        self.generate_fixture_task_type()
        self.generate_fixture_task_status()
        self.generate_fixture_task_status_wip()
        self.generate_fixture_person()
        self.log_in(self.person.email)
        self.generate_fixture_assigner()
        self.generate_fixture_task()

    def test_start_end_timer(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        self.assertIsNotNone(timer)
        timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
        timer.save()
        self.post("/actions/tasks/timer/end", {})
        timer = Timer.get(timer.id)
        self.assertIsNotNone(timer.end_time)
        ts = TimeSpent.get_by(timer_id=timer.id)
        self.assertIsNotNone(ts)
        self.assertGreater(ts.duration, 0)

    def test_discard_timer(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        self.delete("/actions/tasks/timer/discard")
        timer_check = Timer.get(timer.id)
        self.assertIsNone(timer_check)

    def test_edit_timer_start_time(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        new_start = timer.start_time - datetime.timedelta(hours=1)
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {"start_time": date_helpers.get_date_string(new_start)},
        )
        timer = Timer.get(timer.id)
        self.assertAlmostEqual(
            timer.start_time, new_start, delta=datetime.timedelta(seconds=1)
        )
        self.post("/actions/tasks/timer/end", {})
        ts = TimeSpent.get_by(timer_id=timer.id)
        self.assertGreaterEqual(ts.duration, 60)

    def test_edit_timer_denied_for_other_user(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        self.log_in_admin()
        new_start = timer.start_time - datetime.timedelta(minutes=5)
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {"start_time": date_helpers.get_date_string(new_start)},
            403,
        )

    def test_list_user_timers(self):
        second_task = self.generate_fixture_task(name="Second")

        for task in [self.task, second_task]:
            self.post(f"/actions/tasks/{task.id}/timer/start", {})
            timer = Timer.get_by(person_id=self.person.id, end_time=None)
            timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
            timer.save()
            self.post("/actions/tasks/timer/end", {})

        first_timer = Timer.query.order_by(Timer.start_time).first()
        prev_day = (
            date_helpers.get_utc_now_datetime() - datetime.timedelta(days=1)
        ).replace(hour=23, minute=0, second=0, microsecond=0)
        self.patch(
            f"/actions/tasks/timer/{first_timer.id}",
            {
                "start_time": date_helpers.get_date_string(prev_day),
                "end_time": date_helpers.get_date_string(
                    prev_day + datetime.timedelta(minutes=1)
                ),
            },
        )

        tz = timezone(config.DEFAULT_TIMEZONE)
        query_date = (
            timezone("UTC")
            .localize(prev_day)
            .astimezone(tz)
            .date()
            .strftime("%Y-%m-%d")
        )

        result = self.get(f"/data/timers?date={query_date}&embed_task=true")
        self.assertEqual(len(result), 2)
        self.assertIn("task", result[0])

    def test_update_timer_end_time(self):
        # create a timer
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        # set start time in the past
        timer.start_time = (
            date_helpers.get_utc_now_datetime() - datetime.timedelta(hours=1)
        )
        timer.save()
        # stop the timer
        self.post("/actions/tasks/timer/end", {})
        timer = Timer.get(timer.id)

        new_end = date_helpers.get_utc_now_datetime() - datetime.timedelta(
            minutes=50
        )

        # patch
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {"end_time": date_helpers.get_date_string(new_end)},
        )

        # assertions
        ts = TimeSpent.get_by(timer_id=timer.id)
        timer = Timer.get(timer.id)

        self.assertAlmostEqual(
            ts.duration,
            round((new_end - timer.start_time).total_seconds() / 60),
            delta=1,
        )
        task = Task.get(timer.task_id)
        self.assertAlmostEqual(task.duration, ts.duration, delta=1)

    def test_delete_timer(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
        timer.save()
        self.post("/actions/tasks/timer/end", {})
        ts = TimeSpent.get_by(timer_id=timer.id)
        task = Task.get(timer.task_id)
        self.assertGreater(task.duration, 0)

        self.delete(f"/actions/tasks/timer/{timer.id}")
        self.assertIsNone(Timer.get(timer.id))
        self.assertIsNone(TimeSpent.get(ts.id))
        self.assertEqual(Task.get(self.task.id).duration, 0)

    def test_update_timer_inside_other_error(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer1 = Timer.get_by(person_id=self.person.id, end_time=None)
        timer1.start_time = timer1.start_time - datetime.timedelta(minutes=1)
        timer1.save()
        self.post("/actions/tasks/timer/end", {})

        start1 = datetime.datetime(2020, 1, 3, 10, 0, 0)
        end1 = datetime.datetime(2020, 1, 3, 12, 0, 0)
        self.patch(
            f"/actions/tasks/timer/{timer1.id}",
            {
                "start_time": date_helpers.get_date_string(start1),
                "end_time": date_helpers.get_date_string(end1),
            },
        )

        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer2 = Timer.get_by(person_id=self.person.id, end_time=None)
        timer2.start_time = timer2.start_time - datetime.timedelta(minutes=1)
        timer2.save()
        self.post("/actions/tasks/timer/end", {})

        start2 = datetime.datetime(2020, 1, 3, 10, 30, 0)
        end2 = datetime.datetime(2020, 1, 3, 11, 0, 0)
        self.patch(
            f"/actions/tasks/timer/{timer2.id}",
            {
                "start_time": date_helpers.get_date_string(start2),
                "end_time": date_helpers.get_date_string(end2),
            },
            400,
        )

    def test_update_timer_end_before_start_error(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
        timer.save()
        self.post("/actions/tasks/timer/end", {})

        start = datetime.datetime(2020, 1, 4, 10, 0, 0)
        end = datetime.datetime(2020, 1, 4, 9, 0, 0)
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {
                "start_time": date_helpers.get_date_string(start),
                "end_time": date_helpers.get_date_string(end),
            },
            400,
        )

    def test_update_timer_future_time_error(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
        timer.save()
        self.post("/actions/tasks/timer/end", {})

        future = date_helpers.get_utc_now_datetime() + datetime.timedelta(
            days=1
        )
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {"start_time": date_helpers.get_date_string(future)},
            400,
        )

    def test_update_timer_zero_duration_error(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        timer.start_time = timer.start_time - datetime.timedelta(minutes=1)
        timer.save()
        self.post("/actions/tasks/timer/end", {})

        start = datetime.datetime(2020, 1, 5, 10, 0, 0)
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {
                "start_time": date_helpers.get_date_string(start),
                "end_time": date_helpers.get_date_string(start),
            },
            400,
        )

    def test_running_timer_cannot_swallow_closed_timer(self):
        """
        Editing an *open* timer so that it would fully contain a closed
        timer must be rejected with 400.
        """

        # 1.  create a closed timer:  t_closed = [-60 s ... now-10 s]
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        t_closed = Timer.get_by(person_id=self.person.id, end_time=None)
        t_closed.start_time = t_closed.start_time - datetime.timedelta(minutes=1)
        t_closed.save()
        self.post("/actions/tasks/timer/end", {})  # close it

        # 2.  create a new *running* timer that starts after the closed one
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        t_open = Timer.get_by(person_id=self.person.id, end_time=None)

        # 3.  try to move the running timer's start_time *earlier* so it
        #     encloses the closed timer
        earlier = t_closed.start_time - datetime.timedelta(seconds=10)
        self.patch(
            f"/actions/tasks/timer/{t_open.id}",
            {"start_time": date_helpers.get_date_string(earlier)},
            400,  # <- MUST fail
        )

    def test_closed_timer_expansion_trims_running_timer(self):
        """
        Expanding a *closed* timer so it overtakes the start of the current
        running timer must succeed and automatically move the running
        timer's start forward (no overlap remains).
        """

        # 1.  past timer:      [-120 ... -60]
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        t_past = Timer.get_by(person_id=self.person.id, end_time=None)
        t_past.start_time = t_past.start_time - datetime.timedelta(minutes=3)
        t_past.save()
        self.post("/actions/tasks/timer/end", {})
        t_past.end_time = t_past.start_time - datetime.timedelta(minutes=2)
        t_past.save()

        # 2.  running timer:   [now ... )
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        t_run = Timer.get_by(person_id=self.person.id, end_time=None)
        t_run.start_time = t_run.start_time - datetime.timedelta(minutes=1)
        t_run.save()
        original_start = t_run.start_time

        # 3.  stretch *past* timer's end slightly into the running timer
        #     (1 s past the running timer's start but still *before* now)
        new_end = original_start + datetime.timedelta(seconds=1)

        self.patch(
            f"/actions/tasks/timer/{t_past.id}",
            {"end_time": date_helpers.get_date_string(new_end)},
        )

        # 4.  verify: running timer was trimmed to start == new_end
        t_run = Timer.get(t_run.id)
        t_past = Timer.get(t_past.id)

        self.assertAlmostEqual(
            t_run.start_time, new_end, delta=datetime.timedelta(seconds=1)
        )
        self.assertAlmostEqual(
            t_past.end_time, new_end, delta=datetime.timedelta(seconds=1)
        )

    def test_get_running_timer(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer_object = Timer.get_by(person_id=self.person.id, end_time=None)
        timer_object.start_time = timer_object.start_time - datetime.timedelta(
            minutes=1
        )
        timer_object.save()
        timer = self.get("/data/timers/current")
        self.assertIsNotNone(timer)
        self.post("/actions/tasks/timer/end", {})
        timer = self.get("/data/timers/current")
        self.assertIsNone(timer)
