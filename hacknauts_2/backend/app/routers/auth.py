from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import Credentials, TokenOut, UserOut
from ..security import DUMMY_HASH, current_user, hash_password, make_token, new_session_id, verify_password

router = APIRouter()


def _start_session(db: Session, user: User) -> TokenOut:
    user.session_id = new_session_id()  # replaces any older session for this email
    db.commit()
    return TokenOut(token=make_token(user), email=user.email)


@router.post("/signup", response_model=TokenOut, status_code=201)
def signup(body: Credentials, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    return _start_session(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, "Email or password is incorrect.")
    return _start_session(db, user)


@router.post("/demo", response_model=TokenOut)
def demo(db: Session = Depends(get_db)):
    if not settings.enable_demo:
        raise HTTPException(404, "Demo login is disabled.")
    user = db.scalar(select(User).where(User.email == settings.demo_email))
    if not user:
        raise HTTPException(503, "Demo account is not ready yet.")
    return _start_session(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(email=user.email)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.session_id = None
    db.commit()
