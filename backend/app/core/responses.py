from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    is_successful: bool
    status_code: int
    message: str
    data: T | None = None

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "OK",
        status_code: int = 200,
    ) -> "ApiResponse":
        return cls(
            is_successful=True,
            status_code=status_code,
            message=message,
            data=data,
        )