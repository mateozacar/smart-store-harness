"""FastAPI router for /api/v1/auth."""

from __future__ import annotations

from fastapi import APIRouter

from app.application.login_customer import LoginCommand, LoginUseCase
from app.interface.http.dependencies import get_login_use_case
from app.interface.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    status_code=200,
    response_model=TokenResponse,
    responses={
        401: {
            "description": "Email or password is incorrect.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/invalid-credentials",
                        "title": "Invalid Credentials",
                        "status": 401,
                        "detail": "Email or password is incorrect.",
                    }
                }
            },
        },
        422: {
            "description": "Request body is missing required fields.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/validation-error",
                        "title": "Validation Error",
                        "status": 422,
                        "detail": "Field required",
                    }
                }
            },
        },
    },
)
async def login(
    body: LoginRequest,
    use_case: LoginUseCase = get_login_use_case,
) -> TokenResponse:
    """Authenticate a Buyer and return a short-lived JWT access token.

    Returns 200 with access_token and token_type on success.
    Returns 401 for any credential failure (unknown email or wrong password).
    Returns 422 if the request body is missing required fields.
    """
    result = await use_case.execute(LoginCommand(email=body.email, password=body.password))
    return TokenResponse(access_token=result.access_token, token_type=result.token_type)
