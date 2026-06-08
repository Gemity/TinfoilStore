"""content_size_bytes_bigint

Revision ID: 9d7d77f0d3ab
Revises: d4fa69bd0bcd
Create Date: 2026-03-29 22:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "9d7d77f0d3ab"
down_revision = "d4fa69bd0bcd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "content_objects",
        "size_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "content_objects",
        "size_bytes",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
