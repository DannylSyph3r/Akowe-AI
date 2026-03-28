from uuid import UUID

from pydantic import BaseModel

from app.core.enums import StepUpAction


class RegisterRequest(BaseModel):
    phone_number: str
    full_name: str
    pin: str


class LoginRequest(BaseModel):
    phone_number: str
    pin: str


class AuthTokens(BaseModel):
    member_id: UUID
    full_name: str
    phone_number: str
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshTokensResponse(BaseModel):
    access_token: str
    refresh_token: str


class StepUpRequest(BaseModel):
    pin: str
    action: StepUpAction


class StepUpResponse(BaseModel):
    step_up_token: str
    expires_in: int