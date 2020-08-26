"""Initial migration

Revision ID: 0c93a052495d
Revises: 
Create Date: 2020-08-26 15:45:52.223387

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c93a052495d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('file',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('mimetype', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_file_filename'), 'file', ['filename'], unique=False)
    op.create_table('project',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bank_name', sa.String(length=64), nullable=True),
    sa.Column('bunq_access_token', sa.String(length=64), nullable=True),
    sa.Column('iban', sa.String(length=34), nullable=True),
    sa.Column('iban_name', sa.String(length=120), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('hidden', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_bank_name'), 'project', ['bank_name'], unique=False)
    op.create_index(op.f('ix_project_iban'), 'project', ['iban'], unique=True)
    op.create_index(op.f('ix_project_iban_name'), 'project', ['iban_name'], unique=False)
    op.create_index(op.f('ix_project_name'), 'project', ['name'], unique=True)
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('admin', sa.Boolean(), nullable=True),
    sa.Column('first_name', sa.String(length=120), nullable=True),
    sa.Column('last_name', sa.String(length=120), nullable=True),
    sa.Column('biography', sa.String(length=1000), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_first_name'), 'user', ['first_name'], unique=False)
    op.create_index(op.f('ix_user_last_name'), 'user', ['last_name'], unique=False)
    op.create_table('user_story',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=240), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('text', sa.String(length=200), nullable=True),
    sa.Column('hidden', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_story_name'), 'user_story', ['name'], unique=False)
    op.create_table('IBAN',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('iban', sa.String(length=34), nullable=True),
    sa.Column('iban_name', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_IBAN_iban'), 'IBAN', ['iban'], unique=False)
    op.create_index(op.f('ix_IBAN_iban_name'), 'IBAN', ['iban_name'], unique=False)
    op.create_table('funder',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('url', sa.String(length=2000), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_funder_name'), 'funder', ['name'], unique=False)
    op.create_table('project_image',
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('project_id', 'file_id')
    )
    op.create_table('project_user',
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('project_id', 'user_id')
    )
    op.create_table('subproject',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('iban', sa.String(length=34), nullable=True),
    sa.Column('iban_name', sa.String(length=120), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('hidden', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subproject_iban'), 'subproject', ['iban'], unique=True)
    op.create_index(op.f('ix_subproject_iban_name'), 'subproject', ['iban_name'], unique=False)
    op.create_index(op.f('ix_subproject_name'), 'subproject', ['name'], unique=True)
    op.create_table('user_image',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'file_id')
    )
    op.create_table('userstory_image',
    sa.Column('user_story_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_story_id'], ['user_story.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_story_id', 'file_id')
    )
    op.create_table('debit_card',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('iban', sa.String(length=34), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('card_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['iban'], ['subproject.iban'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('funder_image',
    sa.Column('funder_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['funder_id'], ['funder.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('funder_id', 'file_id')
    )
    op.create_table('payment',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('subproject_id', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bank_payment_id', sa.Integer(), nullable=True),
    sa.Column('alias_name', sa.String(length=120), nullable=True),
    sa.Column('alias_type', sa.String(length=12), nullable=True),
    sa.Column('alias_value', sa.String(length=120), nullable=True),
    sa.Column('amount_currency', sa.String(length=12), nullable=True),
    sa.Column('amount_value', sa.Float(), nullable=True),
    sa.Column('balance_after_mutation_currency', sa.String(length=12), nullable=True),
    sa.Column('balance_after_mutation_value', sa.Float(), nullable=True),
    sa.Column('counterparty_alias_name', sa.String(length=120), nullable=True),
    sa.Column('counterparty_alias_type', sa.String(length=12), nullable=True),
    sa.Column('counterparty_alias_value', sa.String(length=120), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated', sa.DateTime(timezone=True), nullable=True),
    sa.Column('monetary_account_id', sa.Integer(), nullable=True),
    sa.Column('sub_type', sa.String(length=12), nullable=True),
    sa.Column('type', sa.String(length=12), nullable=True),
    sa.Column('short_user_description', sa.String(length=50), nullable=True),
    sa.Column('long_user_description', sa.String(length=1000), nullable=True),
    sa.Column('hidden', sa.Boolean(), nullable=True),
    sa.Column('flag_suspicious_count', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subproject_id'], ['subproject.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('bank_payment_id')
    )
    op.create_index(op.f('ix_payment_alias_value'), 'payment', ['alias_value'], unique=False)
    op.create_index(op.f('ix_payment_counterparty_alias_value'), 'payment', ['counterparty_alias_value'], unique=False)
    op.create_index(op.f('ix_payment_monetary_account_id'), 'payment', ['monetary_account_id'], unique=False)
    op.create_table('subproject_image',
    sa.Column('subproject_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subproject_id'], ['subproject.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('subproject_id', 'file_id')
    )
    op.create_table('subproject_user',
    sa.Column('subproject_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['subproject_id'], ['subproject.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('subproject_id', 'user_id')
    )
    op.create_table('payment_attachment',
    sa.Column('payment_id', sa.Integer(), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['payment_id'], ['payment.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('payment_id', 'file_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('payment_attachment')
    op.drop_table('subproject_user')
    op.drop_table('subproject_image')
    op.drop_index(op.f('ix_payment_monetary_account_id'), table_name='payment')
    op.drop_index(op.f('ix_payment_counterparty_alias_value'), table_name='payment')
    op.drop_index(op.f('ix_payment_alias_value'), table_name='payment')
    op.drop_table('payment')
    op.drop_table('funder_image')
    op.drop_table('debit_card')
    op.drop_table('userstory_image')
    op.drop_table('user_image')
    op.drop_index(op.f('ix_subproject_name'), table_name='subproject')
    op.drop_index(op.f('ix_subproject_iban_name'), table_name='subproject')
    op.drop_index(op.f('ix_subproject_iban'), table_name='subproject')
    op.drop_table('subproject')
    op.drop_table('project_user')
    op.drop_table('project_image')
    op.drop_index(op.f('ix_funder_name'), table_name='funder')
    op.drop_table('funder')
    op.drop_index(op.f('ix_IBAN_iban_name'), table_name='IBAN')
    op.drop_index(op.f('ix_IBAN_iban'), table_name='IBAN')
    op.drop_table('IBAN')
    op.drop_index(op.f('ix_user_story_name'), table_name='user_story')
    op.drop_table('user_story')
    op.drop_index(op.f('ix_user_last_name'), table_name='user')
    op.drop_index(op.f('ix_user_first_name'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_project_name'), table_name='project')
    op.drop_index(op.f('ix_project_iban_name'), table_name='project')
    op.drop_index(op.f('ix_project_iban'), table_name='project')
    op.drop_index(op.f('ix_project_bank_name'), table_name='project')
    op.drop_table('project')
    op.drop_index(op.f('ix_file_filename'), table_name='file')
    op.drop_table('file')
    # ### end Alembic commands ###
