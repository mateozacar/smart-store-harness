"""Pydantic schemas for the /auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response body for a successful login."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str
