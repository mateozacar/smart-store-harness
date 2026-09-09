# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- feat: add GET /api/v1/products/{sku} — retrieve product detail with computed available stock (on_hand - reserved); returns 404 problem+json for unknown SKU; available defaults to 0 when no inventory row exists (#21)
- feat: add POST /api/v1/orders — place an order with atomic inventory reservation (SELECT FOR UPDATE); optionally attach to a registered customer; returns 409 on insufficient stock, 422 on unknown customer_id (#19)
- feat: add POST /api/v1/customers — register a customer with a unique, RFC 5322-validated email; normalizes to lowercase; returns 409 on duplicate email, 422 on malformed email (#17)
- feat: scaffold hexagonal layout with FastAPI, SQLAlchemy, Alembic, testcontainers baseline (#1)
- feat: add POST /api/v1/products — create a product with unique SKU, name, and price; returns 409 on duplicate SKU, 422 on invalid input (#6)
- feat: add GET /api/v1/products — list products with 1-based pagination (default page=1, size=20, max size=100) and optional inclusive price range filter; ordered by created_at DESC; returns 422 problem+json for invalid price range or pagination params (#11)
- fix: normalize `DATABASE_URL` to `postgresql+psycopg://` in both Alembic and app config so Render's raw DSN does not resolve to psycopg2 (which we do not install)
- chore: align `render.yaml` with the manually-created `smart-store-harness` service (name + linked DB `smart-store-db`); document that the Blueprint drifted from the live service
