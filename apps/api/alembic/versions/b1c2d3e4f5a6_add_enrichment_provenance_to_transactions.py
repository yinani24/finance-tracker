"""add category_confidence + enriched_at to transactions

Revision ID: b1c2d3e4f5a6
Revises: 2e3d11d4afb9
Create Date: 2026-08-02 19:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '2e3d11d4afb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Both nullable: existing rows have no provenance yet, and NULL enriched_at
    # is exactly the marker a future backfill selects on. No server_default —
    # a pre-enrichment row is genuinely "unknown", not "confidence 0".
    op.add_column(
        'transactions',
        sa.Column('category_confidence', sa.Float(), nullable=True),
    )
    op.add_column(
        'transactions',
        sa.Column('enriched_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transactions', 'enriched_at')
    op.drop_column('transactions', 'category_confidence')
