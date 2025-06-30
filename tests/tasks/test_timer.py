from tests.base import ApiDBTestCase
from zou.app.models.timer import Timer
from zou.app.models.time_spent import TimeSpent
from zou.app.models.task import Task
from zou.app.utils import date_helpers
import datetime
import time


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
        time.sleep(1)
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
        self.assertGreaterEqual(ts.duration, 3600)

    def test_list_timers_paging(self):
        for _ in range(3):
            self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
            self.post("/actions/tasks/timer/end", {})

        result = self.get(f"/data/tasks/{self.task.id}/timers?page=1&limit=2")
        self.assertEqual(len(result["data"]), 2)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["nb_pages"], 2)

        result_page2 = self.get(
            f"/data/tasks/{self.task.id}/timers?page=2&limit=2"
        )
        self.assertEqual(len(result_page2["data"]), 1)

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
        result = self.get(f"/data/tasks/{self.task.id}/timers")
        self.assertEqual(result["total"], 0)

    def test_list_user_timers(self):
        second_task = self.generate_fixture_task(name="Second")

        for task in [self.task, second_task]:
            self.post(f"/actions/tasks/{task.id}/timer/start", {})
            self.post("/actions/tasks/timer/end", {})

        result = self.get("/data/timers?page=1&limit=1&embed_task=true")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["nb_pages"], 2)
        self.assertEqual(len(result["data"]), 1)
        self.assertIn("task", result["data"][0])

        result_page2 = self.get("/data/timers?page=2&limit=1")
        self.assertEqual(len(result_page2["data"]), 1)

    def test_update_timer_end_time(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        time.sleep(1)
        self.post("/actions/tasks/timer/end", {})
        timer = Timer.get(timer.id)

        new_end = timer.end_time + datetime.timedelta(hours=1)
        self.patch(
            f"/actions/tasks/timer/{timer.id}",
            {"end_time": date_helpers.get_date_string(new_end)},
        )

        ts = TimeSpent.get_by(timer_id=timer.id)
        timer = Timer.get(timer.id)
        self.assertAlmostEqual(
            ts.duration, (new_end - timer.start_time).total_seconds(), delta=1
        )
        task = Task.get(timer.task_id)
        self.assertAlmostEqual(task.duration, ts.duration, delta=1)

    def test_delete_timer(self):
        self.post(f"/actions/tasks/{self.task.id}/timer/start", {})
        timer = Timer.get_by(person_id=self.person.id, end_time=None)
        time.sleep(1)
        self.post("/actions/tasks/timer/end", {})
        ts = TimeSpent.get_by(timer_id=timer.id)
        task = Task.get(timer.task_id)
        self.assertGreater(task.duration, 0)

        self.delete(f"/actions/tasks/timer/{timer.id}")
        self.assertIsNone(Timer.get(timer.id))
        self.assertIsNone(TimeSpent.get(ts.id))
        self.assertEqual(Task.get(self.task.id).duration, 0)
