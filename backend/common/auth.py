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


# In-memory API key to user mapping (loaded from environment variables — no hardcoded fallbacks)
def get_configured_api_keys() -> dict[str, "AuthenticatedUser"]:
    """
    Load API keys strictly from environment variables.
    Raises RuntimeError on startup if any required key is missing.
    This prevents accidental deployment with insecure default credentials.
    """
    required_keys = {
        "VFX_ADMIN_API_KEY": ("usr-admin-01", "admin_director", UserRole.ADMIN),
        "VFX_LEAD_TD_API_KEY": ("usr-lead-01", "lead_pipeline_td", UserRole.LEAD_TD),
        "VFX_TD_API_KEY": ("usr-td-01", "alex_pipeline_td", UserRole.TD),
        "VFX_SYSTEM_API_KEY": ("usr-sys-01", "system_orchestrator", UserRole.SYSTEM),
    }

    result: dict[str, "AuthenticatedUser"] = {}
    missing = []

    for env_var, (user_id, username, role) in required_keys.items():
        key = os.getenv(env_var)
        if not key:
            missing.append(env_var)
        else:
            result[key] = AuthenticatedUser(user_id=user_id, username=username, role=role)

    if missing:
        raise RuntimeError(
            f"Missing required API key environment variables: {', '.join(missing)}. "
            "Set them in your .env file. See .env.example for reference."
        )

    return result


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
