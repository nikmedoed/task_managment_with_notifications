"""roles in comments

Revision ID: eb71614ea35c
Revises: a3e706392604
Create Date: 2024-07-22 18:47:32.246198

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb71614ea35c'
down_revision: Union[str, None] = 'a3e706392604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('comment_userrole_association',
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.Column('author_role', sa.Enum('SUPPLIER', 'EXECUTOR', 'SUPERVISOR', 'GUEST', name='userrole'), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('time_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('time_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ),
    sa.PrimaryKeyConstraint('comment_id', 'author_role', 'id'),
    sa.UniqueConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('comment_userrole_association')
    # ### end Alembic commands ###
