"""Modified unique constraint for category name to apply to only subproject scope.

Revision ID: 12aed8481bf5
Revises: 233a4bd6cd00
Create Date: 2022-05-23 10:50:51.571280

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "12aed8481bf5"
down_revision = "233a4bd6cd00"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "category_project_id_subproject_id_name_key", "category", type_="unique"
    )
    op.create_unique_constraint(
        "category_subproject_id_name_key", "category", ["subproject_id", "name"]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("category_subproject_id_name_key", "category", type_="unique")
    op.create_unique_constraint(
        "category_project_id_subproject_id_name_key",
        "category",
        ["project_id", "subproject_id", "name"],
    )
    # ### end Alembic commands ###
