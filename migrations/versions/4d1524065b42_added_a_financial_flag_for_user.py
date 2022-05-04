"""Added a financial flag for user.

Revision ID: 4d1524065b42
Revises: 16de43fe48eb
Create Date: 2022-04-28 15:30:51.686031

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d1524065b42'
down_revision = '16de43fe48eb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('financial', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'financial')
    # ### end Alembic commands ###