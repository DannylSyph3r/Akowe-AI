from pydantic import BaseModel, field_validator

from app.core.enums import StepUpAction
from app.core.phone import validate_nigerian_phone


class RegisterRequest(BaseModel):
    phone_number: str
    full_name: str
    pin: str

    @field_validator("phone_number")
    @classmethod
    def normalise_phone(cls, v: str) -> str:
        try:
            return validate_nigerian_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        if not v.isdigit() or not (4 <= len(v) <= 6):
            raise ValueError("PIN must be 4–6 digits")
        return v


class LoginRequest(BaseModel):
    phone_number: str
    pin: str

    @field_validator("phone_number")
    @classmethod
    def normalise_phone(cls, v: str) -> str:
        try:
            return validate_nigerian_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class RefreshRequest(BaseModel):
    refresh_token: str


class StepUpRequest(BaseModel):
    pin: str
    action: StepUpAction


# --- Responses

class AuthTokens(BaseModel):
    member_id: str
    access_token: str
    refresh_token: str


class RefreshTokensResponse(BaseModel):
    access_token: str
    refresh_token: str


class StepUpResponse(BaseModel):
    step_up_token: str
    expires_in: int = 300