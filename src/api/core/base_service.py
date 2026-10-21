from typing import Any

from pydantic import BaseModel


class ServiceResponse(BaseModel):
    success: bool
    status: int = 200
    data: Any = None
    message: str | None = None

    @classmethod
    def ok(
        cls, data: Any = None, message: str | None = None, status: int = 200
    ) -> "ServiceResponse":
        return cls(success=True, status=status, message=message, data=data)

    @classmethod
    def error(
        cls,
        message: str | None = None,
        data: Any = None,
        status: int = 400,
    ) -> "ServiceResponse":
        return cls(success=False, status=status, message=message, data=data)

    def response(self) -> dict[str, Any]:
        return {
            "content": {
                "data": self.data,
                "message": self.message,
                "success": self.success,
            },
            "status_code": self.status,
        }


class BaseService:
    def ok(
        self, data: Any = None, message: str | None = None, status: int = 200
    ) -> ServiceResponse:
        return ServiceResponse.ok(data=data, message=message, status=status)

    def error(
        self,
        message: str | None = None,
        data: Any = None,
        status: int = 400,
    ) -> ServiceResponse:
        return ServiceResponse.error(message=message, data=data, status=status)
