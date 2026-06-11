"""
auth.py — Email + password authentication with JWT sessions.

Flow:
  1. User POSTs email+password to /api/auth/register or /api/auth/login.
  2. We verify credentials, return a signed JWT (30-day expiry).
  3. Frontend stores the JWT in localStorage and sends it as
     Authorization: Bearer <token> on every subsequent request.
  4. get_current_user() extracts the user from the JWT (no DB hit needed).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import Request

load_dotenv(Path(__file__).parent / ".env")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRE_DAYS = 30
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_jwt(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[_ALGORITHM])
    except pyjwt.PyJWTError:
        return None


def get_current_user(request: Request) -> dict | None:
    """Extract and verify the JWT from the Authorization header.
    Returns {"sub": "1", "email": "..."} or None if absent/invalid.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return decode_jwt(auth[7:])
