from tests.base import ApiDBTestCase

from zou.app.services import tasks_service


class PersonMonthTimeSpentsCsvExportTestCase(ApiDBTestCase):
    def setUp(self):
        super(PersonMonthTimeSpentsCsvExportTestCase, self).setUp()

        self.generate_fixture_project_status()
        self.project = self.generate_fixture_project()
        self.generate_fixture_asset_type()
        self.generate_fixture_department()
        self.generate_fixture_task_type()
        self.generate_fixture_task_status()
        self.generate_fixture_asset()
        self.person = self.generate_fixture_person()
        self.generate_fixture_assigner()
        self.task = self.generate_fixture_task()

        tasks_service.create_or_update_time_spent(
            str(self.task.id), str(self.person.id), "2023-03-04", 500
        )

    def test_export(self):
        csv_content = self.get_raw(
            f"/export/csv/persons/{self.person.id}/time-spents/month/2023/3.csv"
        )
        expected = """Project;Task Type;Episode;Sequence;Entity Type;Entity;Duration\r
Cosmos Landromat;Shaders;;;Props;Tree;500.0\r
"""
        self.assertEqual(csv_content, expected)
