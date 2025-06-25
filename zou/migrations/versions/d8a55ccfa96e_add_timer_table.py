"""Add timer table and link to time spent

Revision ID: d8a55ccfa96e
Revises: ffeed4956ab1
Create Date: 2024-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision = "d8a55ccfa96e"
down_revision = "ffeed4956ab1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "timer",
        sa.Column("id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("task_id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=True),
        sa.Column("person_id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_timer_task_id"), "timer", ["task_id"], unique=False)
    op.create_index(op.f("ix_timer_person_id"), "timer", ["person_id"], unique=False)

    with op.batch_alter_table("time_spent", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "timer_id",
                sqlalchemy_utils.types.uuid.UUIDType(binary=False),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(None, "timer", ["timer_id"], ["id"])
        batch_op.drop_constraint("time_spent_uc", type_="unique")
        batch_op.create_unique_constraint(
            "time_spent_uc", ["person_id", "task_id", "date", "timer_id"]
        )
        batch_op.create_index(
            batch_op.f("ix_time_spent_timer_id"), ["timer_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("time_spent", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_time_spent_timer_id"))
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_constraint("time_spent_uc", type_="unique")
        batch_op.drop_column("timer_id")
        batch_op.create_unique_constraint("time_spent_uc", ["person_id", "task_id", "date"])

    op.drop_index(op.f("ix_timer_person_id"), table_name="timer")
    op.drop_index(op.f("ix_timer_task_id"), table_name="timer")
    op.drop_table("timer")
