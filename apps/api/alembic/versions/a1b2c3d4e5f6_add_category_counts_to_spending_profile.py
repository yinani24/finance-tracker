"""add category_counts_json to spending_profiles

Revision ID: a1b2c3d4e5f6
Revises: 14fc7f6a99e3
Create Date: 2026-07-09 06:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '14fc7f6a99e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills existing rows with an empty JSON object so the
    # column is safely non-nullable on upgrade.
    op.add_column(
        'spending_profiles',
        sa.Column(
            'category_counts_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('spending_profiles', 'category_counts_json')
