"""
Cortexium 2.0 — Local Auth (No Supabase Required)
===================================================
Replaces the Supabase JWT verifier with a simple local user that works
100% offline. All data (encounters, sessions, face DB) is stored on disk.

The LocalUser object mimics the shape the rest of the app expects from
Supabase's user object (id + email), so no other code needs to change.
"""
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer(auto_error=False)


class LocalUser:
    """
    Offline local user — stands in for a Supabase user object.
    All API endpoints receive this instead of a real JWT-verified user.
    """
    id: str = "local-user-00000000"
    email: str = "admin@cortexium.local"
    role: str = "admin"
    # Supabase-compatible metadata dicts � prevents AttributeError in
    # endpoints that access current_user.app_metadata / user_metadata
    app_metadata: dict = {}
    user_metadata: dict = {}

    def __repr__(self):
        return f"LocalUser({self.email})"


# Singleton — reuse the same object for every request (no auth cost)
_LOCAL_USER = LocalUser()


async def get_current_user(
    token: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> LocalUser:
    """
    FastAPI dependency that returns the local user.
    Accepts any token (or no token) — no verification performed.
    All data stays on disk; nothing is sent to an external service.
    """
    return _LOCAL_USER
