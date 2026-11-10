"""Firebase ID token verification (no firebase-admin dependency).

Rules: https://firebase.google.com/docs/auth/admin/verify-id-tokens#verify_id_tokens_using_a_third-party_jwt_library
  alg RS256, signed by a key in Google's securetoken JWKS,
  aud = <project id>, iss = https://securetoken.google.com/<project id>,
  exp in future, iat/auth_time in past, sub non-empty.
"""

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt

JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)
LEEWAY_S = 30  # clock skew tolerance


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class FirebaseIdentity:
    uid: str
    email: str | None
    name: str | None


class SigningKeyResolver(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK: ...


@lru_cache
def google_jwks() -> SigningKeyResolver:
    # PyJWKClient caches keys and refetches on unknown `kid` (Google rotates keys ~daily).
    return jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600, timeout=5)


def verify_id_token(
    token: str, project_id: str, keys: SigningKeyResolver | None = None
) -> FirebaseIdentity:
    try:
        signing_key = (keys or google_jwks()).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise InvalidToken(str(exc)) from exc

    if not claims["sub"] or len(claims["sub"]) > 128:
        raise InvalidToken("invalid sub")
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, int) or auth_time > time.time() + LEEWAY_S:
        raise InvalidToken("invalid auth_time")
    return FirebaseIdentity(uid=claims["sub"], email=claims.get("email"), name=claims.get("name"))
