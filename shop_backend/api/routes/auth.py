from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shop_backend.db.session import get_db
from shop_backend.schemas.auth import LoginRequest, TokenResponse
from shop_backend.services.auth_service import authenticate_user

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        token = authenticate_user(db, body.username, body.password)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=token)
