"""
API Authentication Boundary and Role-Based Access Control (RBAC).
Supports API Key / Bearer Token authentication and roles:
- ADMIN (Full platform, secret configuration, server management)
- LEAD_TD (Approvals, high-risk actions, override execution)
- TD (Standard pipeline operations, monitoring, retry submission)
- ARTIST (Read-only, telemetry submission)
- SYSTEM (Internal automation, specialist agents, watsonx orchestrate)
"""

from enum import Enum
import os
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    LEAD_TD = "LEAD_TD"
    TD = "TD"
    ARTIST = "ARTIST"
    SYSTEM = "SYSTEM"


class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    role: UserRole
    is_active: bool = True


# In-memory API key to user mapping (configured via environment variables or defaults)
def get_configured_api_keys() -> dict[str, AuthenticatedUser]:
    """Load API keys from environment variables, falling back to secure test defaults."""
    admin_key = os.getenv("VFX_ADMIN_API_KEY", "vfx-admin-secret-key-prod-001")
    lead_td_key = os.getenv("VFX_LEAD_TD_API_KEY", "vfx-lead-td-secret-key-prod-002")
    td_key = os.getenv("VFX_TD_API_KEY", "vfx-td-standard-key-prod-003")
    system_key = os.getenv("VFX_SYSTEM_API_KEY", "vfx-system-internal-key-prod-004")

    return {
        admin_key: AuthenticatedUser(user_id="usr-admin-01", username="admin_director", role=UserRole.ADMIN),
        lead_td_key: AuthenticatedUser(user_id="usr-lead-01", username="lead_pipeline_td", role=UserRole.LEAD_TD),
        td_key: AuthenticatedUser(user_id="usr-td-01", username="alex_pipeline_td", role=UserRole.TD),
        system_key: AuthenticatedUser(user_id="usr-sys-01", username="system_orchestrator", role=UserRole.SYSTEM),
    }


def authenticate_request(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
) -> AuthenticatedUser:
    """
    Authenticates incoming request using either X-API-Key header or Bearer token.
    If neither or invalid, raises HTTP 401 Unauthorized.
    """
    # Check if authentication boundary bypass is enabled for testing
    if os.getenv("VFX_AUTH_DISABLED", "false").lower() in ("true", "1"):
        return AuthenticatedUser(user_id="usr-test-bypass", username="test_operator", role=UserRole.ADMIN)

    token = api_key or (bearer.credentials if bearer else None)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials: Provide X-API-Key header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    keys = get_configured_api_keys()
    user = keys.get(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token or API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(allowed_roles: list[UserRole]):
    """FastAPI dependency factory to enforce RBAC permissions."""
    def role_checker(user: AuthenticatedUser = Depends(authenticate_request)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: User role '{user.role.value}' is not authorized. Required: {[r.value for r in allowed_roles]}",
            )
        return user
    return role_checker
