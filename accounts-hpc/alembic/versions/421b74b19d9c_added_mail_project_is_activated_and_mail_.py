"""added mail_project_is_actived and mail_project_is_deactivated fields

Revision ID: 421b74b19d9c
Revises: 279bca80e20b
Create Date: 2024-01-20 14:15:41.665000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '421b74b19d9c'
down_revision: Union[str, None] = '279bca80e20b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mail_project_is_activated', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('mail_project_is_deactivated', sa.JSON(), nullable=False, server_default='{}'))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('mail_project_is_deactivated')
        batch_op.drop_column('mail_project_is_activated')

    # ### end Alembic commands ###
