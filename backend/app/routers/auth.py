from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_member
from app.core.exceptions import NotImplementedException
from app.core.responses import ApiResponse
from app.models.member import Member
from app.schemas.auth import (
    AuthTokens,
    LoginRequest,
    RefreshRequest,
    RefreshTokensResponse,
    RegisterRequest,
    StepUpRequest,
    StepUpResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await AuthService(db).register(
        phone_number=body.phone_number,
        full_name=body.full_name,
        pin=body.pin,
    )
    return ApiResponse.success(
        data=AuthTokens(**result),
        message="Registration successful",
        status_code=201,
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await AuthService(db).login(
        phone_number=body.phone_number,
        pin=body.pin,
    )
    return ApiResponse.success(data=AuthTokens(**result), message="Login successful")


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await AuthService(db).refresh(body.refresh_token)
    return ApiResponse.success(
        data=RefreshTokensResponse(**result),
        message="Tokens refreshed",
    )


@router.post("/logout", status_code=204)
async def logout(
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await AuthService(db).logout(current_member)
    return Response(status_code=204)


@router.post("/step-up")
async def step_up(
    body: StepUpRequest,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await AuthService(db).step_up(current_member, body.pin, body.action)
    return ApiResponse.success(
        data=StepUpResponse(**result),
        message="Step-up token issued",
    )


@router.post("/reset-pin")
async def reset_pin() -> ApiResponse:
    raise NotImplementedException(
        "PIN reset is not yet available. Please contact your cooperative administrator."
    )