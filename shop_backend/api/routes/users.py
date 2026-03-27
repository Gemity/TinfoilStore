from fastapi import APIRouter, Depends

from shop_backend.api.deps import get_current_user
from shop_backend.db.models import User
from shop_backend.schemas.users import UserResponse

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
