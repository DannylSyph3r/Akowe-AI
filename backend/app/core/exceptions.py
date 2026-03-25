class AppException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class BadRequestException(AppException):
    def __init__(self, message: str):
        super().__init__(400, message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(401, message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(403, message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(404, message)


class ConflictException(AppException):
    def __init__(self, message: str):
        super().__init__(409, message)


class UnprocessableException(AppException):
    def __init__(self, message: str):
        super().__init__(422, message)


class NotImplementedException(AppException):
    def __init__(self, message: str = "Not yet implemented"):
        super().__init__(501, message)


class InternalServerException(AppException):
    def __init__(self, message: str = "An unexpected error occurred"):
        super().__init__(500, message)