import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

_bearer = HTTPBearer(auto_error=False)


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f"{salt.hex()}:{_scrypt(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest = stored.split(":")
        return hmac.compare_digest(_scrypt(password, bytes.fromhex(salt_hex)).hex(), digest)
    except ValueError:
        return False


DUMMY_HASH = hash_password("not-a-real-password")  # keeps login timing similar for unknown emails


def new_session_id() -> str:
    return uuid.uuid4().hex


def make_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_hours)
    return jwt.encode({"sub": str(user.id), "sid": user.session_id, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    unauth = HTTPException(401, "Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if not creds:
        raise unauth
    try:
        data = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauth
    if not user or not user.session_id or not hmac.compare_digest(user.session_id, str(data.get("sid", ""))):
        raise HTTPException(401, "This session ended because the account signed in somewhere else.")
    return user
