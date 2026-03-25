from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import StepUpAction
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_step_up_token,
    decode_token,
    hash_pin,
    hash_refresh_token,
    tokens_match,
    verify_pin,
)
from app.models.member import Member
from app.repositories.member_repository import MemberRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_repo = MemberRepository(db)

    async def register(
        self, phone_number: str, full_name: str, pin: str
    ) -> dict:
        existing = await self.member_repo.get_by_phone(phone_number)
        if existing:
            raise ConflictException(
                "An account with this phone number already exists"
            )

        member = await self.member_repo.create(
            phone_number=phone_number,
            full_name=full_name,
            pin_hash=hash_pin(pin),
        )

        access_token = create_access_token(str(member.id))
        refresh_token = create_refresh_token(str(member.id))

        await self.member_repo.update_refresh_token_hash(
            member.id, hash_refresh_token(refresh_token)
        )

        await self.db.commit()
        await self.db.refresh(member)

        return {
            "member_id": str(member.id),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def login(self, phone_number: str, pin: str) -> dict:
        member = await self.member_repo.get_by_phone(phone_number)

        # Evaluate all conditions before raising — no enumeration
        valid = (
            member is not None
            and member.pin_hash is not None
            and verify_pin(pin, member.pin_hash)
        )
        if not valid:
            raise UnauthorizedException("Invalid credentials")

        access_token = create_access_token(str(member.id))
        refresh_token = create_refresh_token(str(member.id))

        await self.member_repo.update_refresh_token_hash(
            member.id, hash_refresh_token(refresh_token)
        )

        await self.db.commit()

        return {
            "member_id": str(member.id),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")

        member_id: str | None = payload.get("sub")
        if not member_id:
            raise UnauthorizedException("Invalid token payload")

        member = await self.member_repo.get_by_id(UUID(member_id))
        if not member or not member.refresh_token_hash:
            raise UnauthorizedException("Session expired, please log in again")

        if not tokens_match(refresh_token, member.refresh_token_hash):
            raise UnauthorizedException("Invalid refresh token")

        new_access = create_access_token(str(member.id))
        new_refresh = create_refresh_token(str(member.id))

        await self.member_repo.update_refresh_token_hash(
            member.id, hash_refresh_token(new_refresh)
        )

        await self.db.commit()

        return {"access_token": new_access, "refresh_token": new_refresh}

    async def logout(self, member: Member) -> None:
        await self.member_repo.update_refresh_token_hash(member.id, None)
        await self.db.commit()

    async def step_up(
        self, member: Member, pin: str, action: StepUpAction
    ) -> dict:
        valid = member.pin_hash is not None and verify_pin(pin, member.pin_hash)
        if not valid:
            raise UnauthorizedException("Invalid credentials")

        return {
            "step_up_token": create_step_up_token(str(member.id), action),
            "expires_in": 300,
        }