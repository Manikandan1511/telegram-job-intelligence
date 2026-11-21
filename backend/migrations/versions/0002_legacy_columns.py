"""Add columns introduced after the first local SQLite schema."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision="0002_legacy_columns"
down_revision="0001_initial"
branch_labels=None
depends_on=None

COLUMNS={
    "resumes":[sa.Column("file_path",sa.String(1000),nullable=True)],
    "profile":[
        sa.Column("education",sa.Text(),nullable=True),sa.Column("college",sa.String(300),nullable=True),
        sa.Column("degree",sa.String(200),nullable=True),sa.Column("cgpa",sa.String(40),nullable=True),
        sa.Column("experience_json",sa.Text(),nullable=False,server_default="[]"),
        sa.Column("projects_json",sa.Text(),nullable=False,server_default="[]"),
        sa.Column("certifications_json",sa.Text(),nullable=False,server_default="[]"),
    ],
    "jobs":[
        sa.Column("experience_required",sa.String(200),nullable=True),sa.Column("education_required",sa.Text(),nullable=True),
        sa.Column("graduation_year",sa.String(100),nullable=True),sa.Column("work_mode",sa.String(100),nullable=True),
        sa.Column("salary",sa.String(200),nullable=True),sa.Column("application_deadline",sa.String(100),nullable=True),
        sa.Column("contact_email",sa.String(300),nullable=True),sa.Column("contact_information",sa.Text(),nullable=True),
        sa.Column("extraction_confidence",sa.Float(),nullable=True),
    ],
    "notification_preferences":[
        sa.Column("last_digest_date",sa.String(10),nullable=True),sa.Column("chat_id",sa.String(100),nullable=True),
    ],
}

def upgrade():
    bind=op.get_bind()
    for table,columns in COLUMNS.items():
        if table not in inspect(bind).get_table_names(): continue
        existing={item["name"] for item in inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in existing: op.add_column(table,column)

def downgrade():
    # Local data is preserved on downgrade; the initial migration owns table removal.
    pass
