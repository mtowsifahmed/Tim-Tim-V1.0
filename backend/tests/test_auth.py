import asyncio
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app import auth
from app.config import settings

PRIV = ec.generate_private_key(ec.SECP256R1())
JWK = {**jwt.algorithms.ECAlgorithm.to_jwk(PRIV.public_key(), as_dict=True), "kid": "k1", "alg": "ES256", "use": "sig"}
URL = "https://proj.supabase.co"


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", URL)
    auth._cache.clear(); auth._jwks.update(keys=[JWK], at=time.time())


def token(**over):
    p = {"sub": "user-1", "aud": "authenticated", "iss": URL + "/auth/v1", "exp": time.time() + 600, **over}
    return jwt.encode(p, PRIV, algorithm="ES256", headers={"kid": "k1"})


def verify(t):
    return asyncio.run(auth.verify_token(t))


def test_valid_token_verifies_locally_without_any_network_call(monkeypatch):
    async def boom(t): raise AssertionError("must not call Supabase")
    monkeypatch.setattr(auth, "_network_verify", boom)
    assert verify(token()) == "user-1"


def test_expired_wrong_audience_and_forged_tokens_are_401(monkeypatch):
    for t in (token(exp=time.time() - 300), token(aud="anon"), token(iss="https://evil.example/auth/v1"),
              jwt.encode({"sub": "x", "aud": "authenticated", "exp": time.time() + 99}, ec.generate_private_key(ec.SECP256R1()), algorithm="ES256", headers={"kid": "k1"})):
        with pytest.raises(HTTPException) as e:
            verify(t)
        assert e.value.status_code == 401


def test_unknown_algorithm_falls_back_to_network_and_rate_limits_are_503_not_401(monkeypatch):
    legacy = jwt.encode({"sub": "u", "aud": "authenticated", "exp": time.time() + 99}, "secret-secret-secret-secret-123456", algorithm="HS256")
    async def busy(t): raise HTTPException(503, "busy")
    monkeypatch.setattr(auth, "_network_verify", busy)
    with pytest.raises(HTTPException) as e:
        verify(legacy)
    assert e.value.status_code == 503                                  # transient: the client must NOT sign the user out


def test_a_previously_trusted_token_survives_a_rate_limited_recheck(monkeypatch):
    legacy = jwt.encode({"sub": "u", "aud": "authenticated", "exp": time.time() + 99}, "secret-secret-secret-secret-123456", algorithm="HS256")
    auth._cache[legacy] = (time.time() - 1, "user-9")                  # trusted earlier, cache entry just expired
    async def busy(t): raise HTTPException(503, "busy")
    monkeypatch.setattr(auth, "_network_verify", busy)
    assert verify(legacy) == "user-9"


def test_legacy_hs256_secret_is_verified_locally(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "secret-secret-secret-secret-123456")
    t = jwt.encode({"sub": "legacy-user", "aud": "authenticated", "iss": URL + "/auth/v1", "exp": time.time() + 99}, "secret-secret-secret-secret-123456", algorithm="HS256")
    assert verify(t) == "legacy-user"
