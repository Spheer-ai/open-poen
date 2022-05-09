"""Added new fields to funder model and a foreign key to subproject for the verantwoordingsmodule.

Revision ID: 5a724787dd53
Revises: 86092566a210
Create Date: 2022-05-05 11:55:15.204082

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5a724787dd53"
down_revision = "86092566a210"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("funder", sa.Column("budget", sa.Integer(), nullable=True))
    op.add_column("funder", sa.Column("subproject_id", sa.Integer(), nullable=True))
    op.add_column("funder", sa.Column("subsidy", sa.String(length=120), nullable=True))
    op.add_column(
        "funder", sa.Column("subsidy_number", sa.String(length=120), nullable=True)
    )
    op.create_foreign_key(
        "funder_subproject_fkey",
        "funder",
        "subproject",
        ["subproject_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("funder_subproject_fkey", "funder", type_="foreignkey")
    op.drop_column("funder", "subsidy_number")
    op.drop_column("funder", "subsidy")
    op.drop_column("funder", "subproject_id")
    op.drop_column("funder", "budget")
    # ### end Alembic commands ###