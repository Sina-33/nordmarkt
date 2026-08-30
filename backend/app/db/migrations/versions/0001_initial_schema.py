"""Initial schema.

Kept deliberately free of CONCURRENTLY index builds - those live in 0002 so
this revision can run inside a single transaction and roll back cleanly.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "categories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False, unique=True, index=True),
        sa.Column("name", JSONB, nullable=False),
        sa.Column("parent_id", UUID, sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("path", sa.String(512), nullable=False, index=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
    )

    op.create_table(
        "brands",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("logo_url", sa.Text),
        *_ts(),
    )

    op.create_table(
        "products",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False, unique=True, index=True),
        sa.Column("title", JSONB, nullable=False),
        sa.Column("description", JSONB, nullable=False),
        sa.Column("highlights", JSONB, nullable=False, server_default="{}"),
        sa.Column("category_id", UUID, sa.ForeignKey("categories.id"), nullable=False, index=True),
        sa.Column("brand_id", UUID, sa.ForeignKey("brands.id")),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false", index=True),
        sa.Column("rating_average", sa.Numeric(3, 2), nullable=False, server_default="0"),
        sa.Column("rating_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tags", pg.ARRAY(sa.String(48)), nullable=False, server_default="{}"),
        sa.Column(
            "search_vector",
            pg.TSVECTOR,
            sa.Computed(
                "to_tsvector('swedish', coalesce(title->>'sv','') || ' ' "
                "|| coalesce(title->>'en','') || ' ' || coalesce(description->>'sv',''))",
                persisted=True,
            ),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts(),
    )
    op.create_index("ix_products_search", "products", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_products_category_published", "products", ["category_id", "is_published"])

    op.create_table(
        "product_variants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("options", JSONB, nullable=False, server_default="{}"),
        sa.Column("price_minor_units", sa.Integer, nullable=False),
        sa.Column("compare_at_minor_units", sa.Integer),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("vat_rate", sa.Numeric(4, 3), nullable=False, server_default="0.250"),
        sa.Column("weight_grams", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("sku", name="uq_product_variants_sku"),
        sa.CheckConstraint("price_minor_units >= 0", name="ck_product_variants_price_non_negative"),
        sa.CheckConstraint(
            "compare_at_minor_units IS NULL OR compare_at_minor_units >= price_minor_units",
            name="ck_product_variants_compare_at_above_price",
        ),
        *_ts(),
    )

    op.create_table(
        "product_images",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("alt_text", JSONB, nullable=False, server_default="{}"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("preferred_locale", sa.String(5), nullable=False, server_default="sv"),
        sa.Column("roles", pg.ARRAY(sa.String(32)), nullable=False, server_default="{customer}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email", name="uq_users_email"),
        *_ts(),
    )

    op.create_table(
        "addresses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient", sa.String(160), nullable=False),
        sa.Column("street", sa.String(240), nullable=False),
        sa.Column("postal_code", sa.String(16), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="SE"),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        *_ts(),
    )

    op.create_table(
        "session_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, index=True),
        sa.Column("user_agent", sa.String(320)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_ts(),
    )

    op.create_table(
        "stock_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("variant_id", UUID, sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("warehouse_code", sa.String(16), nullable=False, server_default="SE-STO"),
        sa.Column("on_hand", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer, nullable=False, server_default="5"),
        sa.CheckConstraint("on_hand >= 0", name="ck_stock_items_on_hand_non_negative"),
        sa.CheckConstraint("reserved >= 0", name="ck_stock_items_reserved_non_negative"),
        sa.CheckConstraint("reserved <= on_hand", name="ck_stock_items_reserved_within_on_hand"),
        *_ts(),
    )
    op.create_index("uq_stock_variant_warehouse", "stock_items",
                    ["variant_id", "warehouse_code"], unique=True)

    op.create_table(
        "stock_reservations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("variant_id", UUID, sa.ForeignKey("product_variants.id"),
                  nullable=False, index=True),
        sa.Column("order_id", UUID, index=True),
        sa.Column("cart_id", UUID, index=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("committed_at", sa.DateTime(timezone=True)),
        *_ts(),
    )
    op.create_index("ix_reservations_expiry", "stock_reservations", ["released_at", "expires_at"])

    op.create_table(
        "carts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("anonymous_token", sa.String(64), index=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("locale", sa.String(5), nullable=False, server_default="sv"),
        sa.Column("checked_out_at", sa.DateTime(timezone=True)),
        *_ts(),
    )

    op.create_table(
        "cart_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("cart_id", UUID, sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID, sa.ForeignKey("product_variants.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price_minor_units", sa.Integer, nullable=False),
        sa.UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_variant"),
        *_ts(),
    )

    order_status = pg.ENUM(
        "pending_payment", "paid", "packing", "shipped", "delivered", "cancelled", "refunded",
        name="order_status",
    )
    order_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_number", sa.String(24), nullable=False, unique=True, index=True),
        sa.Column("customer_id", UUID, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", order_status, nullable=False, server_default="pending_payment",
                  index=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("locale", sa.String(5), nullable=False, server_default="sv"),
        sa.Column("subtotal_minor_units", sa.Integer, nullable=False),
        sa.Column("vat_minor_units", sa.Integer, nullable=False),
        sa.Column("shipping_minor_units", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discount_minor_units", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_minor_units", sa.Integer, nullable=False),
        sa.Column("shipping_address", JSONB, nullable=False),
        sa.Column("billing_address", JSONB, nullable=False),
        sa.Column("shipping_method", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("placed_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text),
        sa.CheckConstraint("total_minor_units >= 0", name="ck_orders_total_non_negative"),
        *_ts(),
    )
    op.create_index("ix_orders_customer_created", "orders", ["customer_id", "created_at"])

    op.create_table(
        "order_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID, sa.ForeignKey("product_variants.id"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("title_snapshot", JSONB, nullable=False),
        sa.Column("options_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("image_url", sa.Text),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_minor_units", sa.Integer, nullable=False),
        sa.Column("vat_rate", sa.Numeric(4, 3), nullable=False),
        sa.Column("line_total_minor_units", sa.Integer, nullable=False),
    )

    payment_status = pg.ENUM(
        "initiated", "authorized", "captured", "failed", "refunded", name="payment_status"
    )
    payment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="swish_sandbox"),
        sa.Column("provider_reference", sa.String(96), nullable=False),
        sa.Column("status", payment_status, nullable=False, server_default="initiated"),
        sa.Column("amount_minor_units", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("failure_reason", sa.Text),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("raw_response", JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("provider_reference", name="uq_payments_provider_ref"),
        *_ts(),
    )

    op.create_table(
        "processed_webhooks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),
        *_ts(),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(96), nullable=False, index=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("last_error", sa.Text),
        *_ts(),
    )
    op.execute(
        "CREATE INDEX ix_outbox_pending ON outbox_messages (next_attempt_at, created_at) "
        "WHERE published_at IS NULL"
    )


def downgrade() -> None:
    for table in (
        "outbox_messages", "processed_webhooks", "payments", "order_items", "orders",
        "cart_items", "carts", "stock_reservations", "stock_items", "session_tokens",
        "addresses", "users", "product_images", "product_variants", "products",
        "brands", "categories",
    ):
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS order_status")
