"""Common schemas used across the application."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime | None = None


class TenantMixin(BaseModel):
    """Mixin for tenant-scoped resources."""

    tenant_id: UUID


class PaginationParams(BaseModel):
    """Pagination parameters."""

    limit: int = 20
    offset: int = 0


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    total: int
    limit: int
    offset: int
    has_more: bool


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str
    details: dict | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
