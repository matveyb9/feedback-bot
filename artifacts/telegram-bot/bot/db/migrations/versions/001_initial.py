"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-07-25 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tg_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tg_users_telegram_id", "tg_users", ["telegram_id"], unique=True)

    op.create_table(
        "tg_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("tg_users.id"), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_msg_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "direction",
            sa.Enum("incoming", "outgoing", name="messagedirection"),
            nullable=False,
        ),
        sa.Column(
            "content_type",
            sa.Enum("text", "photo", "document", "voice", "video", "sticker", "other", name="contenttype"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(512), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tg_messages_user_id", "tg_messages", ["user_id"])
    op.create_index("ix_tg_messages_admin_msg_id", "tg_messages", ["admin_msg_id"])


def downgrade() -> None:
    op.drop_index("ix_tg_messages_admin_msg_id", table_name="tg_messages")
    op.drop_index("ix_tg_messages_user_id", table_name="tg_messages")
    op.drop_table("tg_messages")
    op.execute("DROP TYPE IF EXISTS messagedirection")
    op.execute("DROP TYPE IF EXISTS contenttype")
    op.drop_index("ix_tg_users_telegram_id", table_name="tg_users")
    op.drop_table("tg_users")
