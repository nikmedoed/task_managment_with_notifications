"""add 'notified' status

Revision ID: 6c87b96b72d6
Revises: bc3f23288e1d
Create Date: 2024-08-20 16:06:40.988609

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6c87b96b72d6'
down_revision: Union[str, None] = 'bc3f23288e1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE comments MODIFY COLUMN type ENUM('error', 'comment', 'status_change', 'date_change', 'user_change', 'notified')")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE comments MODIFY COLUMN type ENUM('error', 'comment', 'status_change', 'date_change', 'user_change')")
