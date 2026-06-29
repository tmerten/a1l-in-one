"""Add identity detail fields.

Revision ID: 20260626_120000
Revises: 20250513_100000
Create Date: 2026-06-26 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_120000"
down_revision: str | None = "20250513_100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("person_identities") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("profile_url", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("data", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("person_identities") as batch_op:
        batch_op.drop_column("data")
        batch_op.drop_column("profile_url")
        batch_op.drop_column("display_name")
