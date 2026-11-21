"""Create the single local account table."""
from alembic import op
from backend.app.db import Base
from backend.app import models  # noqa: F401

revision="0003_local_account"
down_revision="0002_legacy_columns"
branch_labels=None
depends_on=None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind())

def downgrade():
    op.drop_table("users")
