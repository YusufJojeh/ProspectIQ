"""Refactor auth, workspace lifecycle, and simulated billing.

Revision ID: 0005_auth_billing_workspace_refactor
Revises: 0004_outreach_versions
Create Date: 2026-04-22
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

from app.shared.utils.identifiers import new_public_id

revision = "0005_auth_billing_workspace_refactor"
down_revision = "0004_outreach_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column(
        "workspaces",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column(
        "workspaces",
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column("workspaces", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.add_column(
        "workspaces",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_foreign_key(
        "fk_workspaces_owner_user_id",
        "workspaces",
        "users",
        ["owner_user_id"],
        ["id"],
    )

    op.add_column(
        "users",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("users", sa.Column("invited_by_user_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_users_invited_by_user_id",
        "users",
        "users",
        ["invited_by_user_id"],
        ["id"],
    )

    op.execute("UPDATE users SET role = 'manager' WHERE role = 'agency_manager'")
    op.execute("UPDATE users SET role = 'member' WHERE role = 'sales_user'")
    op.execute(
        """
        DELETE FROM roles
        WHERE `key`='agency_manager'
          AND EXISTS (SELECT 1 FROM roles WHERE `key`='manager')
        """
    )
    op.execute(
        """
        UPDATE roles
        SET `key`='manager', label='Manager', description='Operational product access with limited governance.'
        WHERE `key`='agency_manager'
          AND NOT EXISTS (SELECT 1 FROM roles WHERE `key`='manager')
        """
    )
    op.execute(
        """
        DELETE FROM roles
        WHERE `key`='sales_user'
          AND EXISTS (SELECT 1 FROM roles WHERE `key`='member')
        """
    )
    op.execute(
        """
        UPDATE roles
        SET `key`='member', label='Member', description='Standard workspace access.'
        WHERE `key`='sales_user'
          AND NOT EXISTS (SELECT 1 FROM roles WHERE `key`='member')
        """
    )
    op.execute(
        """
        INSERT INTO roles (`key`, label, description, created_at)
        SELECT 'account_owner', 'Account Owner', 'Full ownership of the workspace and billing.', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE `key`='account_owner')
        """
    )

    bind = op.get_bind()
    workspaces = list(bind.execute(sa.text("SELECT id, public_id, name FROM workspaces")).mappings())
    for row in workspaces:
        slug = row["name"].strip().lower().replace(" ", "-")
        bind.execute(
            sa.text(
                """
                UPDATE workspaces
                SET slug=:slug, settings_json=:settings_json
                WHERE id=:workspace_id
                """
            ),
            {
                "slug": slug[:120] or row["public_id"],
                "settings_json": '{"locale":"en-US","theme":"dark"}',
                "workspace_id": row["id"],
            },
        )
        owner = bind.execute(
            sa.text(
                """
                SELECT id FROM users
                WHERE workspace_id=:workspace_id
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ),
            {"workspace_id": row["id"]},
        ).scalar()
        if owner is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE users SET role='account_owner'
                    WHERE id=:owner_id
                    """
                ),
                {"owner_id": owner},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE workspaces
                    SET owner_user_id=:owner_id
                    WHERE id=:workspace_id
                    """
                ),
                {"owner_id": owner, "workspace_id": row["id"]},
            )

    with op.batch_alter_table("users") as batch_op:
        try:
            batch_op.drop_constraint("uq_users_workspace_email", type_="unique")
        except Exception:
            pass
        batch_op.create_unique_constraint("uq_users_email", ["email"])

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("yearly_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("limits_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("billing_cycle", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("renews_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=24), nullable=False, unique=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("simulated_result", sa.String(length=32), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    plan_rows = [
        (
            "starter",
            "Starter",
            Decimal("49.00"),
            Decimal("490.00"),
            '{"searches_per_month":50,"exports_per_month":25,"ai_scoring_runs_per_month":100,"outreach_generations_per_month":150,"max_team_users":3}',
        ),
        (
            "growth",
            "Growth",
            Decimal("149.00"),
            Decimal("1490.00"),
            '{"searches_per_month":250,"exports_per_month":100,"ai_scoring_runs_per_month":500,"outreach_generations_per_month":700,"max_team_users":10}',
        ),
        (
            "pro",
            "Pro",
            Decimal("399.00"),
            Decimal("3990.00"),
            '{"searches_per_month":1000,"exports_per_month":500,"ai_scoring_runs_per_month":2000,"outreach_generations_per_month":3000,"max_team_users":30}',
        ),
        (
            "enterprise",
            "Enterprise",
            Decimal("999.00"),
            Decimal("9990.00"),
            '{"searches_per_month":5000,"exports_per_month":2500,"ai_scoring_runs_per_month":10000,"outreach_generations_per_month":15000,"max_team_users":200}',
        ),
    ]
    for code, name, monthly, yearly, limits_json in plan_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO plans (code, name, monthly_price, yearly_price, limits_json, is_active, created_at)
                VALUES (:code, :name, :monthly_price, :yearly_price, :limits_json, true, :created_at)
                """
            ),
            {
                "code": code,
                "name": name,
                "monthly_price": monthly,
                "yearly_price": yearly,
                "limits_json": limits_json,
                "created_at": datetime.now(tz=UTC),
            },
        )

    starter_id = bind.execute(sa.text("SELECT id FROM plans WHERE code='starter'")).scalar()
    now = datetime.now(tz=UTC)
    trial_ends_at = now + timedelta(days=14)
    for row in workspaces:
        bind.execute(
            sa.text(
                """
                INSERT INTO subscriptions (
                    public_id, workspace_id, plan_id, status, billing_cycle, started_at, renews_at,
                    trial_ends_at, created_at, updated_at
                ) VALUES (
                    :public_id, :workspace_id, :plan_id, 'trialing', 'monthly', :started_at,
                    :renews_at, :trial_ends_at, :created_at, :updated_at
                )
                """
            ),
            {
                "public_id": new_public_id("sub"),
                "workspace_id": row["id"],
                "plan_id": starter_id,
                "started_at": now,
                "renews_at": trial_ends_at,
                "trial_ends_at": trial_ends_at,
                "created_at": now,
                "updated_at": now,
            },
        )
        subscription_id = bind.execute(
            sa.text("SELECT id FROM subscriptions WHERE workspace_id=:workspace_id ORDER BY id DESC LIMIT 1"),
            {"workspace_id": row["id"]},
        ).scalar()
        bind.execute(
            sa.text(
                """
                INSERT INTO invoices (public_id, workspace_id, subscription_id, amount, currency, status, issued_at, due_at, paid_at)
                VALUES (:public_id, :workspace_id, :subscription_id, :amount, 'USD', 'paid', :issued_at, :due_at, :paid_at)
                """
            ),
            {
                "public_id": new_public_id("inv"),
                "workspace_id": row["id"],
                "subscription_id": subscription_id,
                "amount": Decimal("49.00"),
                "issued_at": now,
                "due_at": trial_ends_at,
                "paid_at": now,
            },
        )

    op.alter_column("workspaces", "slug", existing_type=sa.String(length=120), nullable=False)
    op.alter_column("workspaces", "status", existing_type=sa.String(length=32), server_default=None)
    op.alter_column("workspaces", "settings_json", existing_type=sa.JSON(), server_default=None)
    op.alter_column("workspaces", "updated_at", existing_type=sa.DateTime(), server_default=None)
    op.alter_column("users", "status", existing_type=sa.String(length=32), server_default=None)
    op.alter_column("users", "updated_at", existing_type=sa.DateTime(), server_default=None)


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("payment_attempts")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.create_unique_constraint("uq_users_workspace_email", ["workspace_id", "email"])
    op.drop_constraint("fk_users_invited_by_user_id", "users", type_="foreignkey")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "job_title")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "invited_by_user_id")
    op.drop_column("users", "status")
    op.drop_constraint("fk_workspaces_owner_user_id", "workspaces", type_="foreignkey")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_column("workspaces", "updated_at")
    op.drop_column("workspaces", "owner_user_id")
    op.drop_column("workspaces", "settings_json")
    op.drop_column("workspaces", "status")
    op.drop_column("workspaces", "slug")
