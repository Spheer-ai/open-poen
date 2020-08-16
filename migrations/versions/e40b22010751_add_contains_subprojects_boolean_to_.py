"""add "contains_subprojects" boolean to project model

Revision ID: e40b22010751
Revises: 
Create Date: 2020-05-28 18:00:37.349682

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e40b22010751'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('project', sa.Column('contains_subprojects', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('project', 'contains_subprojects')
    # ### end Alembic commands ###