"""FastAPI router for /api/v1/customers."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.application.delete_customer import DeleteCustomerCommand, DeleteCustomerUseCase
from app.application.register_customer import RegisterCustomerCommand, RegisterCustomerUseCase
from app.interface.http.dependencies import (
    get_delete_customer_use_case,
    get_register_customer_use_case,
)
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
    customer = await use_case.execute(RegisterCustomerCommand(email=body.email))
    response.headers["Location"] = f"/api/v1/customers/{customer.id}"
    return CustomerResponse(id=customer.id, email=customer.email.value)


@router.delete(
    "/{customer_id}",
    status_code=204,
    responses={
        404: {
            "description": "No customer with the given id exists.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/customer-not-found",
                        "title": "Customer Not Found",
                        "status": 404,
                        "detail": "Customer with id 'uuid-99' does not exist.",
                    }
                }
            },
        },
        409: {
            "description": "Customer has active (PENDING or CONFIRMED) orders.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/customer-has-active-orders",
                        "title": "Customer Has Active Orders",
                        "status": 409,
                        "detail": "Customer 'uuid-2' has active orders and cannot be deleted.",
                    }
                }
            },
        },
    },
)
async def delete_customer(
    customer_id: str,
    use_case: DeleteCustomerUseCase = get_delete_customer_use_case,
) -> Response:
    """Delete a customer by id.

    Returns 204 on success.
    Returns 404 if no customer with the given id exists.
    Returns 409 if the customer has at least one PENDING or CONFIRMED order.
    """
    await use_case.execute(DeleteCustomerCommand(customer_id=customer_id))
    return Response(status_code=204)
