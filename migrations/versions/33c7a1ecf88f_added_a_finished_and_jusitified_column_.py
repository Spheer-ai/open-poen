"""Added a finished and jusitified column for subproject and project respectively.

Revision ID: 33c7a1ecf88f
Revises: 4552f8ac8df9
Create Date: 2022-05-12 09:52:42.451591

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '33c7a1ecf88f'
down_revision = '4552f8ac8df9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('project', sa.Column('justified', sa.Boolean(), nullable=True))
    op.add_column('subproject', sa.Column('finished', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('subproject', 'finished')
    op.drop_column('project', 'justified')
    # ### end Alembic commands ###