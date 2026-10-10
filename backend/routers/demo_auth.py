from fastapi import APIRouter, Depends
from ..auth.supabase_auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/me")
async def read_users_me(current_user = Depends(get_current_user)):
    """
    Verifies the Supabase JWT and returns basic user info.
    Requires 'Authorization: Bearer <JWT>' header.
    """
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "app_metadata": current_user.app_metadata,
        "user_metadata": current_user.user_metadata,
    }

@router.get("/public")
async def public_endpoint():
    """
    A public endpoint that doesn't require authentication.
    """
    return {"message": "This is a public endpoint."}
