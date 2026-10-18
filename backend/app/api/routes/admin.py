"""Admin endpoints: user management, roles, and configuration (Admin only)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_permission
from app.api.schemas import UserCreate, UserResponse
from app.auth.rbac import ROLE_PERMISSIONS
from app.config import get_settings
from app.persistence.postgres.database import get_db_session
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _current: CurrentUser = Depends(require_permission("manage_users")),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    service = AdminService(session)
    users = await service.list_users()
    return [
        UserResponse(
            id=u.id, username=u.username, email=u.email, role=u.role.name, is_active=u.is_active
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current: CurrentUser = Depends(require_permission("manage_users")),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    service = AdminService(session)
    user = await service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        role=body.role,
        actor_id=current.id,
    )
    role_name = body.role
    return UserResponse(
        id=user.id, username=user.username, email=user.email, role=role_name, is_active=user.is_active
    )


@router.get("/roles")
async def list_roles(
    _current: CurrentUser = Depends(require_permission("manage_users")),
) -> dict:
    """Return the static role/permission matrix."""
    return {"roles": ROLE_PERMISSIONS}


@router.get("/config")
async def get_config(
    _current: CurrentUser = Depends(require_permission("manage_config")),
) -> dict:
    """Return non-secret runtime configuration (operational modes)."""
    settings = get_settings()
    return {
        "environment": settings.environment,
        "llm_mode": settings.llm_mode,
        "osint_mode": settings.osint_mode,
        "crypto_mode": settings.crypto_mode,
        "ibmz_mode": settings.ibmz_mode,
        "max_upload_bytes": settings.max_upload_bytes,
    }
