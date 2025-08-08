from slugify import slugify
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from flask import abort

from zou.app.mixin import ArgsMixin
from zou.app.services import (
    persons_service,
    time_spents_service,
    tasks_service,
    user_service,
)
from zou.app.services.exception import WrongDateFormatException
from zou.app.utils import csv_utils, permissions


class PersonMonthTimeSpentsCsvExport(Resource, ArgsMixin):
    """Export aggregated time spents for a person and month as CSV."""

    def get_project_department_arguments(self, person_id):
        project_id = self.get_project_id()
        department_ids = None
        if not permissions.has_admin_permissions():
            if persons_service.get_current_user()["id"] != person_id:
                if (
                    permissions.has_manager_permissions()
                    or permissions.has_supervisor_permissions()
                ):
                    project_ids = [
                        project["id"] for project in user_service.get_projects()
                    ]
                    if project_id is None:
                        project_id = project_ids
                    elif project_id not in project_ids:
                        raise permissions.PermissionDenied
                    if permissions.has_supervisor_permissions():
                        department_ids = persons_service.get_current_user(
                            relations=True
                        )["departments"]
                else:
                    raise permissions.PermissionDenied
        return {"project_id": project_id, "department_ids": department_ids}

    @jwt_required()
    def get(self, person_id, year, month):
        """Export aggregated time spents for a person and month as CSV."""
        try:
            # Strip .csv extension
            user_service.check_person_is_not_bot(person_id)
            args = self.get_project_department_arguments(person_id)
            time_spents = time_spents_service.get_month_time_spents(
                person_id, year, month, **args
            )
        except permissions.PermissionDenied:
            abort(403)
        except WrongDateFormatException:
            abort(404)

        task_type_map = tasks_service.get_task_type_map()
        csv_content = []
        csv_content.append(
            [
                "Project",
                "Task Type",
                "Episode",
                "Sequence",
                "Entity Type",
                "Entity",
                "Duration",
            ]
        )
        for entry in time_spents:
            task_type = task_type_map.get(entry["task_type_id"], {}).get("name", "")
            csv_content.append(
                [
                    entry["project_name"],
                    task_type,
                    entry.get("episode_name", ""),
                    entry.get("sequence_name", ""),
                    entry["entity_type_name"],
                    entry["entity_name"],
                    entry["duration"],
                ]
            )

        person = persons_service.get_person(person_id)
        file_name = f"{person['full_name']} {year}-{str(month).zfill(2)} time spents"
        return csv_utils.build_csv_response(csv_content, slugify(file_name))
