"""Store review signals for suspicious job posts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_job_review"
down_revision = "0003_local_account"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("jobs")}
    if "review_reasons" not in columns:
        op.add_column("jobs", sa.Column("review_reasons", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("jobs")}
    if "review_reasons" in columns:
        op.drop_column("jobs", "review_reasons")
