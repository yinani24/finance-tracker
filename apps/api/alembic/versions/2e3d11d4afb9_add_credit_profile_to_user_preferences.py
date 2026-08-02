"""add credit profile to user preferences

Revision ID: 2e3d11d4afb9
Revises: a1b2c3d4e5f6
Create Date: 2026-08-01 20:14:38.628450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e3d11d4afb9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_preferences",
        sa.Column("credit_score_band", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("recent_card_applications", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_preferences", "recent_card_applications")
    op.drop_column("user_preferences", "credit_score_band")
