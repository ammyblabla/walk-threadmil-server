"""Current-user dependency.

TEMPORARY dev stub until Firebase Auth lands: outside prod, every request acts as one
auto-provisioned owner (spec 02 §4.1 just-in-time provisioning). In prod it refuses,
so the public URL can never read or write data without real auth.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User

DEV_FIREBASE_UID = "dev-owner"


def get_current_user(db: Annotated[Session, Depends(get_session)]) -> User:
    if get_settings().env == "prod":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication not configured")

    user = db.scalar(select(User).where(User.firebase_uid == DEV_FIREBASE_UID))
    if user is None:
        user = User(firebase_uid=DEV_FIREBASE_UID, display_name="Owner")
        db.add(user)
        db.flush()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_session)]
