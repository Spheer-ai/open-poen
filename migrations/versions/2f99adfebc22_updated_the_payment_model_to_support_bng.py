"""Updated the payment model to support BNG.

Revision ID: 2f99adfebc22
Revises: f448a03d2d85
Create Date: 2021-12-20 12:35:02.775241

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2f99adfebc22'
down_revision = 'f448a03d2d85'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('payment', sa.Column('booking_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('creditor_account_currency', sa.String(length=8), nullable=True))
    op.add_column('payment', sa.Column('creditor_account_iban', sa.String(length=22), nullable=True))
    op.add_column('payment', sa.Column('creditor_name', sa.String(length=128), nullable=True))
    op.add_column('payment', sa.Column('debtor_name', sa.String(length=128), nullable=True))
    op.add_column('payment', sa.Column('end_to_end_id', sa.String(length=32), nullable=True))
    op.add_column('payment', sa.Column('entry_reference', sa.String(length=32), nullable=True))
    op.add_column('payment', sa.Column('remittance_information_structured', sa.Text(), nullable=True))
    op.add_column('payment', sa.Column('remittance_information_unstructured', sa.Text(), nullable=True))
    op.add_column('payment', sa.Column('transaction_amount', sa.Float(), nullable=True))
    op.add_column('payment', sa.Column('transaction_currency', sa.String(length=8), nullable=True))
    op.add_column('payment', sa.Column('transaction_id', sa.String(length=64), nullable=True))
    op.drop_index('ix_payment_alias_value', table_name='payment')
    op.drop_index('ix_payment_counterparty_alias_value', table_name='payment')
    op.drop_index('ix_payment_monetary_account_id', table_name='payment')
    op.drop_constraint('payment_bank_payment_id_key', 'payment', type_='unique')
    op.create_unique_constraint(None, 'payment', ['transaction_id'])
    op.drop_constraint('payment_user_id_fkey', 'payment', type_='foreignkey')
    op.drop_column('payment', 'sub_type')
    op.drop_column('payment', 'counterparty_alias_type')
    op.drop_column('payment', 'flag_suspicious_count')
    op.drop_column('payment', 'counterparty_alias_value')
    op.drop_column('payment', 'description')
    op.drop_column('payment', 'alias_name')
    op.drop_column('payment', 'amount_value')
    op.drop_column('payment', 'type')
    op.drop_column('payment', 'balance_after_mutation_currency')
    op.drop_column('payment', 'user_id')
    op.drop_column('payment', 'monetary_account_id')
    op.drop_column('payment', 'alias_value')
    op.drop_column('payment', 'amount_currency')
    op.drop_column('payment', 'bank_payment_id')
    op.drop_column('payment', 'alias_type')
    op.drop_column('payment', 'counterparty_alias_name')
    op.drop_column('payment', 'balance_after_mutation_value')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('payment', sa.Column('balance_after_mutation_value', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('counterparty_alias_name', sa.VARCHAR(length=120), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('alias_type', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('bank_payment_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('amount_currency', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('alias_value', sa.VARCHAR(length=120), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('monetary_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('balance_after_mutation_currency', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('type', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('amount_value', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('alias_name', sa.VARCHAR(length=120), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('counterparty_alias_value', sa.VARCHAR(length=120), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('flag_suspicious_count', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('counterparty_alias_type', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.add_column('payment', sa.Column('sub_type', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.create_foreign_key('payment_user_id_fkey', 'payment', 'user', ['user_id'], ['id'])
    # Commented this out because it otherwise results in an error. Also, this column is removed anyways.
    # op.drop_constraint(None, 'payment', type_='unique')
    op.create_unique_constraint('payment_bank_payment_id_key', 'payment', ['bank_payment_id'])
    op.create_index('ix_payment_monetary_account_id', 'payment', ['monetary_account_id'], unique=False)
    op.create_index('ix_payment_counterparty_alias_value', 'payment', ['counterparty_alias_value'], unique=False)
    op.create_index('ix_payment_alias_value', 'payment', ['alias_value'], unique=False)
    op.drop_column('payment', 'transaction_id')
    op.drop_column('payment', 'transaction_currency')
    op.drop_column('payment', 'transaction_amount')
    op.drop_column('payment', 'remittance_information_unstructured')
    op.drop_column('payment', 'remittance_information_structured')
    op.drop_column('payment', 'entry_reference')
    op.drop_column('payment', 'end_to_end_id')
    op.drop_column('payment', 'debtor_name')
    op.drop_column('payment', 'creditor_name')
    op.drop_column('payment', 'creditor_account_iban')
    op.drop_column('payment', 'creditor_account_currency')
    op.drop_column('payment', 'booking_date')
    # ### end Alembic commands ###