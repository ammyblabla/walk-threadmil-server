"""Current-user dependency.

AUTH_MODE=firebase (default, prod): `Authorization: Bearer <Firebase ID token>`; the user row is
created on first sight (just-in-time provisioning, spec 02 §4.1).
AUTH_MODE=dev (local only, refused when ENV=prod): every request is one auto-provisioned owner.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.firebase_auth import InvalidToken, verify_id_token
from app.models import User

DEV_FIREBASE_UID = "dev-owner"

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _get_or_create(db: Session, uid: str, email: str | None, name: str | None) -> User:
    user = db.scalar(select(User).where(User.firebase_uid == uid))
    if user is None:
        user = User(firebase_uid=uid, email=email, display_name=name)
        db.add(user)
        db.flush()
    return user


def get_current_user(
    db: Annotated[Session, Depends(get_session)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    settings = get_settings()
    if settings.auth_mode == "dev":
        return _get_or_create(db, DEV_FIREBASE_UID, None, "Owner")

    if creds is None:
        raise _unauthorized("Missing bearer token")
    try:
        identity = verify_id_token(creds.credentials, settings.firebase_project_id)
    except InvalidToken:
        raise _unauthorized("Invalid or expired token") from None
    return _get_or_create(db, identity.uid, identity.email, identity.name)


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_session)]
