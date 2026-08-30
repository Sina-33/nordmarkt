"""Search and performance indexes.

Split out from the schema migration because these are built CONCURRENTLY:
a GIN build on a large products table would otherwise hold an ACCESS EXCLUSIVE
lock for the duration and take the storefront down during deploy.

Concurrent index builds cannot run inside a transaction, so this revision
disables the surrounding transaction explicitly.
"""

from alembic import op

revision = "0002_search_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("COMMIT")  # leave Alembic's transaction before CONCURRENTLY

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Trigram index carries typo tolerance and substring matching, which the
    # Swedish tsvector alone does not provide ("fatolj" -> "Fåtölj").
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_title_trgm "
        "ON products USING gin ((title->>'sv') gin_trgm_ops, (title->>'en') gin_trgm_ops)"
    )

    # Partial index: the storefront only ever queries published rows, so the
    # index stays small even as the archive grows.
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_live "
        "ON products (created_at DESC, id DESC) "
        "WHERE is_published = true AND deleted_at IS NULL"
    )

    # Covering index for the cart's hottest lookup - the price read never has
    # to visit the heap.
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_variants_product_price "
        "ON product_variants (product_id, price_minor_units) "
        "INCLUDE (sku, currency) WHERE is_active = true"
    )


def downgrade() -> None:
    op.execute("COMMIT")
    for name in (
        "ix_variants_product_price",
        "ix_products_live",
        "ix_products_title_trgm",
    ):
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
