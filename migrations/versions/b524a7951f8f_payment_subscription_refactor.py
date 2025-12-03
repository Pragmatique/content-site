"""payment_subscription_refactor

Revision ID: b524a7951f8f
Revises: 4b229703b1ae
Create Date: 2025-11-11 02:19:37.058864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b524a7951f8f'
down_revision: Union[str, None] = '4b229703b1ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем новые столбцы с nullable=True где нужно
    op.add_column('payments', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('payments', sa.Column('purpose', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('level', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('client_payment_id', sa.String(), nullable=True))

    # Обновляем данные
    op.execute('UPDATE payments SET user_id = (SELECT user_id FROM subscriptions WHERE subscriptions.id = payments.subscription_id)')
    op.execute("UPDATE payments SET purpose = 'subscription'")
    # level оставляем null для legacy
    op.execute('UPDATE payments SET client_payment_id = payment_id')

    # Делаем NOT NULL где нужно
    op.alter_column('payments', 'user_id', nullable=False)
    op.alter_column('payments', 'purpose', nullable=False)

    # Добавляем FK
    op.create_foreign_key(None, 'payments', 'users', ['user_id'], ['id'])

    # Добавляем payment_id в subscriptions
    op.add_column('subscriptions', sa.Column('payment_id', sa.Integer(), nullable=True))
    op.execute('UPDATE subscriptions SET payment_id = (SELECT id FROM payments WHERE payments.subscription_id = subscriptions.id LIMIT 1)')
    op.alter_column('subscriptions', 'payment_id', nullable=False)
    op.create_foreign_key(None, 'subscriptions', 'payments', ['payment_id'], ['id'])

    # Удаляем старые столбцы
    op.drop_constraint('payments_subscription_id_fkey', 'payments', type_='foreignkey')
    op.drop_column('payments', 'subscription_id')
    op.drop_column('payments', 'discount_applied')
    op.drop_column('payments', 'payout_currency')
    op.drop_column('payments', 'payment_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    # Восстанавливаем старые столбцы
    op.add_column('payments', sa.Column('payment_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('payments', sa.Column('payout_currency', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('payments', sa.Column('discount_applied', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payments', sa.Column('subscription_id', sa.INTEGER(), autoincrement=False, nullable=True))

    # Обновляем данные обратно
    op.execute('UPDATE payments SET payment_id = client_payment_id')
    # subscription_id, discount_applied, payout_currency - assume defaults or manual

    op.alter_column('payments', 'subscription_id', nullable=False)

    # Восстанавливаем FK
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.create_foreign_key('payments_subscription_id_fkey', 'payments', 'subscriptions', ['subscription_id'], ['id'])

    # Удаляем новые столбцы
    op.drop_column('payments', 'client_payment_id')
    op.drop_column('payments', 'level')
    op.drop_column('payments', 'purpose')
    op.drop_column('payments', 'user_id')

    # Удаляем payment_id из subscriptions
    op.drop_constraint(None, 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'payment_id')
    # ### end Alembic commands ###