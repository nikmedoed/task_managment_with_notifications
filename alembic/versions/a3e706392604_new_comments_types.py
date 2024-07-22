"""new comments types

Revision ID: a3e706392604
Revises: 327a69d42710
Create Date: 2024-07-22 05:56:42.119020

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3e706392604'
down_revision = '327a69d42710'
branch_labels = None
depends_on = None

def upgrade():
    # Alter the ENUM type in MySQL
    op.execute("ALTER TABLE comments MODIFY COLUMN type ENUM('error', 'comment', 'status_change', 'date_change', 'user_change') NOT NULL")

def downgrade():
    # Revert the ENUM type in MySQL
    op.execute("ALTER TABLE comments MODIFY COLUMN type ENUM('error', 'comment', 'status_change') NOT NULL")
