# Architecture

## Shape: modular monolith

One deployable, six modules with enforced boundaries. Microservices were
considered and rejected: at this size, service boundaries would buy independent
scaling nobody needs while charging a distributed transaction across every
checkout. The module boundaries are drawn where the service boundaries would
go, so extracting one later is a mechanical change rather than a rewrite.

```
                 ┌──────────────────────────────────────┐
   browser ──────► Next.js 15 (RSC, locale-prefixed)     │
                 └──────────────┬───────────────────────┘
                                │ typed fetch, X-Locale header
                 ┌──────────────▼───────────────────────┐
                 │  api/     routers · deps · middleware │  ← only HTTP-aware layer
                 ├──────────────────────────────────────┤
                 │  modules/ catalog identity cart       │  ← domain rules
                 │           inventory orders payments   │
                 ├──────────────────────────────────────┤
                 │  shared/  UnitOfWork · events · outbox│
                 ├──────────────────────────────────────┤
                 │  db/      SQLAlchemy 2.0 async        │
                 └──────┬──────────────────────┬────────┘
                        │                      │
                  ┌─────▼─────┐          ┌─────▼─────┐
                  │ PostgreSQL│          │   Redis   │
                  └─────┬─────┘          └───────────┘
                        │ outbox_messages (SKIP LOCKED)
              ┌─────────▼─────────┐  ┌───────────────────┐
              │  outbox relay     │  │ reservation sweeper│
              └───────────────────┘  └───────────────────┘
```

## Dependency rule

Dependencies point inward only.

- `api/` imports from `modules/` and `core/`. Nothing imports from `api/`.
- `modules/` import from `core/` and `shared/`, and from each other **only
  through service classes**, never by reaching into another module's tables.
- `core/` imports nothing from the application.

The practical test: `core/money.py` and the order state machine have no
knowledge of FastAPI, SQLAlchemy sessions or HTTP, which is why their tests run
in 0.3 seconds with no infrastructure.

## Request lifecycle

1. `RequestContextMiddleware` assigns a request id and binds it to a context
   variable, so every log line in the request carries it.
2. Dependencies resolve. `get_uow` opens one session; `get_locale` resolves the
   language from `X-Locale`, falling back to `Accept-Language` negotiation.
3. The router calls a service. Services never touch HTTP concepts and never
   commit — the boundary owns the transaction.
4. On success the router calls `uow.commit()`, which writes any queued domain
   events into `outbox_messages` **in the same transaction** as the state
   change, then commits once.
5. Domain errors bubble to a single handler that maps them to status codes and
   a stable body shape carrying a translation key.

## Why one transaction per request

Checkout writes to `orders`, `order_items`, `stock_items`,
`stock_reservations`, `carts` and `outbox_messages`. If those were separate
commits, a failure between them would leave stock reserved against an order
that does not exist, or an order with no reservation behind it. The Unit of Work
makes the whole thing atomic: the shopper either has an order with stock held,
or nothing happened.

## The three correctness mechanisms

**Inventory: conditional update.** `UPDATE stock_items SET reserved = reserved
+ :qty WHERE variant_id = :v AND on_hand - reserved >= :qty`. The predicate is
evaluated under the row lock Postgres already takes for the write, so check and
increment are one step. `rowcount == 0` means another transaction won. A check
constraint (`reserved <= on_hand`) backs this up at the schema level, so even a
buggy service cannot oversell.

**Idempotency: claim then cache.** Checkout requires an `Idempotency-Key`. The
key is claimed with Redis `SET NX`; a completed response is cached for 24 hours
so a retry replays the original order. A failure releases the claim so the
shopper can fix the problem and try again.

**Outbox: same-transaction publish.** Domain events are rows, not broker calls.
A relay drains them with `FOR UPDATE SKIP LOCKED`, which lets N workers
partition the table with no coordination service. Delivery is at-least-once, so
every handler is written to tolerate replay.

## Localisation

Translated content is a JSONB column (`{"sv": ..., "en": ...}`) with a
deterministic fallback chain, not a translations table. A product page is one
row fetch instead of a join per language.

Money formatting happens server-side and ships as a preformatted string.
Sweden writes `1 299,00 kr` with a non-breaking thin space and a trailing
symbol; English writes `SEK 1,299.00`. The client never re-formats, so the two
can never disagree.

Search uses `to_tsvector('swedish', ...)` as a generated column with a GIN
index, plus a `pg_trgm` index for typo tolerance and substring matching —
Swedish stemming alone will not match "fatolj" against "Fåtölj".

## Frontend

Server Components by default. Only four components are client components, and
each earns it: the cart provider (optimistic state), the facet panel (URL
mutation), the locale switch, and the checkout form.

Catalogue reads are cached at the edge (`s-maxage=60,
stale-while-revalidate=300`) and tagged for targeted revalidation. Anything
carrying a cart or session is explicitly `no-store` — the failure mode of
getting that wrong is serving one shopper another's basket.

## Indexing strategy

Concurrent index builds live in migration `0002`, separate from the schema
migration, because a GIN build holds `ACCESS EXCLUSIVE` and would take the
storefront down during deploy. `0002` disables the surrounding transaction
explicitly, since `CREATE INDEX CONCURRENTLY` cannot run inside one.

Notable indexes:
- Partial index on live products only — the storefront never queries archived
  rows, so the index stays small as the archive grows.
- Covering index on `(product_id, price_minor_units) INCLUDE (sku, currency)` —
  the cart's hottest read never visits the heap.
- Partial index on unpublished outbox rows only.

## Pagination

Keyset, not offset. Offset degrades past a few hundred thousand rows and
double-shows or skips items when the underlying list changes between pages. The
cursor is an opaque base64 tuple matching the `ORDER BY`, so every page is a
single index range scan regardless of depth.
