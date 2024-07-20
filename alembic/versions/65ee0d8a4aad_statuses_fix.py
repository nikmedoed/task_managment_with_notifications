"""
statuses fix

Revision ID: 65ee0d8a4aad
Revises: 4a8902dba4ba
Create Date: 2024-07-20 13:13:13.303458

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = '65ee0d8a4aad'
down_revision: Union[str, None] = '4a8902dba4ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    foreign_keys = inspector.get_foreign_keys('tasks')
    fk_names = [fk['name'] for fk in foreign_keys]
    if 'tasks_ibfk_3' in fk_names:
        op.drop_constraint('tasks_ibfk_3', 'tasks', type_='foreignkey')

    if 'status_id' in [col['name'] for col in inspector.get_columns('tasks')]:
        op.drop_column('tasks', 'status_id')

    if 'status' in [col['name'] for col in inspector.get_columns('tasks')]:
        op.drop_column('tasks', 'status')
    op.add_column('tasks', sa.Column('status',
                                     sa.Enum('DRAFT', 'PLANNING', 'ACCEPTED', 'REJECTED', 'REVIEW', 'CANCELED',
                                             'REWORK', 'DONE', name='statuses'), nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if 'status' in [col['name'] for col in inspector.get_columns('tasks')]:
        op.drop_column('tasks', 'status')
    if 'status_id' not in [col['name'] for col in inspector.get_columns('tasks')]:
        op.add_column('tasks',
                      sa.Column('status_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False))
    foreign_keys = inspector.get_foreign_keys('tasks')
    fk_names = [fk['name'] for fk in foreign_keys]
    if 'tasks_ibfk_3' not in fk_names:
        op.create_foreign_key('tasks_ibfk_3', 'tasks', 'statuses', ['status_id'], ['id'])
