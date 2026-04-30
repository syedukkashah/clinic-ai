from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from core import security
from core.config import settings
from schemas import schemas

router = APIRouter()


@router.post("/login/access-token", response_model=schemas.Token)
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin@mediflow.io" and form_data.password == "demo":
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return {
            "accessToken": security.create_access_token(form_data.username, expires_delta=access_token_expires),
            "tokenType": "bearer",
        }
    if form_data.username == "staff@mediflow.io" and form_data.password == "demo":
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return {
            "accessToken": security.create_access_token(form_data.username, expires_delta=access_token_expires),
            "tokenType": "bearer",
        }
    raise HTTPException(status_code=400, detail="Incorrect email or password")
