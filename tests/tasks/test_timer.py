from tests.base import ApiDBTestCase
from zou.app.models.timer import Timer
from zou.app.models.time_spent import TimeSpent
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
