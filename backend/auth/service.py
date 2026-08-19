import os
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from database.models import User

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM = "HS256"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str):
    if not EMAIL_RE.match(email):
        raise ValueError("A valid email address is required.")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.user_id),
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def signup(db: Session, payload):
    email = normalize_email(payload.email)
    validate_email(email)
    if payload.password != payload.confirm_password:
        raise ValueError("Password and Confirm Password must match.")
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email is already registered.")

    user = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user); db.commit(); db.refresh(user)
    return user


def login(db: Session, payload):
    email = normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise ValueError("Invalid email or password.")
    return user, create_token(user)
