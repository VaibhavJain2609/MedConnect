from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorWrapper(BaseModel):
    error: ErrorResponse


class PaginationMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False
    limit: int = 20


class PaginatedResponse(BaseModel):
    data: list
    pagination: PaginationMeta
