from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.schemas import LoginRequest, SignupRequest
from auth.service import login, signup
from database.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup")
def signup_route(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        user = signup(db, payload)
        return {"message": "Account created successfully", "user_id": str(user.user_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/login")
def login_route(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = login(db, payload)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.user_id),
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "onboarding_completed": user.onboarding_completed,
        }
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc

@router.post("/logout")
def logout_route():
    return {"message": "Logged out successfully"}
