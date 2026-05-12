from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from core import security
from core.config import settings
from schemas import schemas

router = APIRouter()


@router.post("/login/access-token", response_model=schemas.Token)
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    valid_users = []
    if settings.ADMIN_PASSWORD:
        valid_users.append((settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD))
    if settings.STAFF_PASSWORD:
        valid_users.append((settings.STAFF_EMAIL, settings.STAFF_PASSWORD))
    if settings.ALLOW_DEMO_AUTH:
        valid_users.extend([
            ("admin@mediflow.io", "demo"),
            ("staff@mediflow.io", "demo"),
        ])

    if any(
        form_data.username == username and form_data.password == password
        for username, password in valid_users
    ):
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return {
            "accessToken": security.create_access_token(form_data.username, expires_delta=access_token_expires),
            "tokenType": "bearer",
        }
    raise HTTPException(status_code=400, detail="Incorrect email or password")
