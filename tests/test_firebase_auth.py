import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.firebase_auth import InvalidToken, verify_id_token

PROJECT = "walk-treadmil"
KID = "test-kid"


def _rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNER = _rsa_key()
OTHER_SIGNER = _rsa_key()


class StaticKeys:
    """Stands in for Google's JWKS: always returns SIGNER's public key."""

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        return jwt.PyJWK.from_dict(
            {**jwt.algorithms.RSAAlgorithm.to_jwk(SIGNER.public_key(), as_dict=True), "kid": KID}
        )


def make_token(signer=SIGNER, alg: str = "RS256", **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "uid-123",
        "iat": now - 10,
        "exp": now + 3600,
        "auth_time": now - 10,
        "email": "owner@example.com",
        "name": "Owner",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, signer, algorithm=alg, headers={"kid": KID})


def test_valid_token_returns_identity() -> None:
    identity = verify_id_token(make_token(), PROJECT, keys=StaticKeys())

    assert (identity.uid, identity.email, identity.name) == (
        "uid-123",
        "owner@example.com",
        "Owner",
    )


@pytest.mark.parametrize(
    "token",
    [
        make_token(aud="some-other-project"),
        make_token(iss="https://securetoken.google.com/some-other-project"),
        make_token(iss="https://accounts.google.com"),
        make_token(exp=int(time.time()) - 3600),
        make_token(iat=int(time.time()) + 3600),  # issued in the future
        make_token(sub=""),
        make_token(sub=None),
        make_token(signer=OTHER_SIGNER),  # not signed by Google's key
        make_token(auth_time=int(time.time()) + 3600),  # authenticated in the future
        make_token(auth_time=None),
    ],
    ids=[
        "wrong-aud",
        "wrong-project-iss",
        "wrong-issuer",
        "expired",
        "future-iat",
        "empty-sub",
        "missing-sub",
        "wrong-signer",
        "future-auth-time",
        "missing-auth-time",
    ],
)
def test_rejects_invalid_tokens(token: str) -> None:
    with pytest.raises(InvalidToken):
        verify_id_token(token, PROJECT, keys=StaticKeys())


def test_rejects_symmetric_alg_confusion() -> None:
    forged = jwt.encode(
        {"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "x"},
        "s" * 32,  # attacker-chosen HMAC secret
        algorithm="HS256",
        headers={"kid": KID},
    )
    with pytest.raises(InvalidToken):
        verify_id_token(forged, PROJECT, keys=StaticKeys())


def test_rejects_garbage() -> None:
    with pytest.raises(InvalidToken):
        verify_id_token("not-a-jwt", PROJECT, keys=StaticKeys())
