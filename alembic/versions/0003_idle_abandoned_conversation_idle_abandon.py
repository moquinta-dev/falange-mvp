"""conversation idle nudge and abandon timestamps

Revision ID: 0003_idle_abandoned
Revises: 0002_multi_tenant
Create Date: 2026-06-20 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_idle_abandoned"
down_revision: Union[str, Sequence[str], None] = "0002_multi_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("idle_nudge_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_column("abandoned_at")
        batch_op.drop_column("idle_nudge_sent_at")
