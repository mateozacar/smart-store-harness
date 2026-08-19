# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- feat: scaffold hexagonal layout with FastAPI, SQLAlchemy, Alembic, testcontainers baseline (#1)
- feat: add POST /api/v1/products — create a product with unique SKU, name, and price; returns 409 on duplicate SKU, 422 on invalid input (#6)
- fix: normalize `DATABASE_URL` to `postgresql+psycopg://` in both Alembic and app config so Render's raw DSN does not resolve to psycopg2 (which we do not install)
- chore: align `render.yaml` with the manually-created `smart-store-harness` service (name + linked DB `smart-store-db`); document that the Blueprint drifted from the live service
