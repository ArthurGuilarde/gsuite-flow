from functools import lru_cache

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException

from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Principal

oauth = OAuth()
oauth.register(
    name="guilarde",
    client_id=settings.OIDC_CLIENT_ID,
    client_secret=settings.OIDC_CLIENT_SECRET,
    server_metadata_url=settings.OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
)


@lru_cache(maxsize=1)
def key_client():
    # Fixed issuer configuration; no token-controlled jwks URL.
    return jwt.PyJWKClient(settings.OIDC_ISSUER.rstrip("/") + "/jwks/", timeout=5, lifespan=300)


def validate_access_token(token: str) -> Principal:
    try:
        key = key_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.OIDC_AUDIENCE,
            issuer=settings.OIDC_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise ValueError("Invalid subject")
        return Principal(sub=claims["sub"], name=claims.get("name", ""))
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Identity keys unavailable") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(401, "Invalid or expired access token") from exc
