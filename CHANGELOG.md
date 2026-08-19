# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- feat: scaffold hexagonal layout with FastAPI, SQLAlchemy, Alembic, testcontainers baseline (#1)
- feat: add POST /api/v1/products — create a product with unique SKU, name, and price; returns 409 on duplicate SKU, 422 on invalid input (#6)
