"""Production access token seems to be longer, so I had to increase the size of that field.

Revision ID: 0bbc39e7fc80
Revises: b3d56718c251
Create Date: 2021-12-28 11:27:55.064355

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0bbc39e7fc80'
down_revision = 'b3d56718c251'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('bng_account', 'access_token',
               existing_type=sa.VARCHAR(length=496),
               type_=sa.String(length=2048),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('bng_account', 'access_token',
               existing_type=sa.String(length=2048),
               type_=sa.VARCHAR(length=496),
               existing_nullable=True)
    # ### end Alembic commands ###
