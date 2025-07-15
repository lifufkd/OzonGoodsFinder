"""Make hashtag in products table as list of str

Revision ID: 98455a73fca0
Revises: f7108dfef7a3
Create Date: 2025-07-15 18:25:20.477173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98455a73fca0'
down_revision: Union[str, Sequence[str], None] = 'f7108dfef7a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('hashtag_json', sa.JSON(), nullable=True))

    op.execute("""
        UPDATE products
        SET hashtag_json = json_build_array(hashtag)
    """)

    op.drop_column('products', 'hashtag')

    op.alter_column('products', 'hashtag_json', new_column_name='hashtag', existing_type=sa.JSON())


def downgrade() -> None:
    op.add_column('products', sa.Column('hashtag_str', sa.VARCHAR(), nullable=True))
    op.execute("""
        UPDATE products
        SET hashtag_str = hashtag->>0
    """)
    op.drop_column('products', 'hashtag')
    op.alter_column('products', 'hashtag_str', new_column_name='hashtag', existing_type=sa.VARCHAR())
