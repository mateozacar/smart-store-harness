"""Pydantic schemas for the /customers endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RegisterCustomerRequest(BaseModel):
    """Request body for POST /api/v1/customers."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class CustomerResponse(BaseModel):
    """Response body for a single customer."""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
