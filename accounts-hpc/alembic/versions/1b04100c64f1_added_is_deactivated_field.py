"""added is_deactivated field

Revision ID: 1b04100c64f1
Revises:
Create Date: 2023-09-29 20:49:58.133027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b04100c64f1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deactivated', sa.Boolean(), nullable=False, server_default=''))
    op.execute('UPDATE users SET is_deactivated=0')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_deactivated')

    # ### end Alembic commands ###
