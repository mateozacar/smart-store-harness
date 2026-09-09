"""FastAPI router for /api/v1/customers."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.application.register_customer import RegisterCustomerCommand, RegisterCustomerUseCase
from app.interface.http.dependencies import get_register_customer_use_case
from app.interface.schemas.customers import CustomerResponse, RegisterCustomerRequest

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.post(
    "",
    status_code=201,
    response_model=CustomerResponse,
    responses={
        409: {
            "description": "A customer with the same email already exists.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/email-conflict",
                        "title": "Email Conflict",
                        "status": 409,
                        "detail": "A customer with email 'buyer@example.com' already exists.",
                    }
                }
            },
        },
        422: {
            "description": "The email address is not valid.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/invalid-email",
                        "title": "Invalid Email",
                        "status": 422,
                        "detail": "'not-an-email' is not a valid email address.",
                    }
                }
            },
        },
    },
)
async def register_customer(
    body: RegisterCustomerRequest,
    response: Response,
    use_case: RegisterCustomerUseCase = get_register_customer_use_case,
) -> CustomerResponse:
    """Register a new customer with a unique, valid email address.

    Returns 201 with the created customer and a Location header.
    Returns 409 if a customer with the same email already exists.
    Returns 422 if the email address does not match RFC 5322 basic form.
    """
    cmd = RegisterCustomerCommand(email=body.email, password=body.password)
    customer = await use_case.execute(cmd)
    response.headers["Location"] = f"/api/v1/customers/{customer.id}"
    return CustomerResponse(id=customer.id, email=customer.email.value)
