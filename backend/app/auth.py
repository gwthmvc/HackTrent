from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from .config import Settings
from .errors import ApiError

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuthContext:
    subject: str
    scopes: frozenset[str]
    permissions: frozenset[str]


@lru_cache(maxsize=8)
def get_jwks_client(domain: str) -> PyJWKClient:
    normalized_domain = domain.removeprefix("https://").rstrip("/")
    return PyJWKClient(f"https://{normalized_domain}/.well-known/jwks.json", cache_keys=True)


def _validate_token(token: str, settings: Settings) -> AuthContext:
    if not settings.auth_configured:
        raise ApiError(
            status_code=503,
            code="authentication_not_configured",
            message="Backend Auth0 domain and audience are not configured.",
        )

    domain = settings.auth0_domain.removeprefix("https://").rstrip("/")
    issuer = f"https://{domain}/"

    try:
        signing_key = get_jwks_client(domain).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except (jwt.PyJWTError, PyJWKClientError) as error:
        if isinstance(error, jwt.ExpiredSignatureError):
            category = "expired"
        elif isinstance(error, jwt.InvalidAudienceError):
            category = "invalid_audience"
        elif isinstance(error, jwt.InvalidIssuerError):
            category = "invalid_issuer"
        elif isinstance(error, jwt.InvalidSignatureError):
            category = "invalid_signature"
        elif isinstance(error, jwt.InvalidAlgorithmError):
            category = "invalid_algorithm"
        elif isinstance(error, PyJWKClientError):
            category = "jwks_key_error"
        else:
            category = "malformed_or_invalid"
        logger.warning("Auth0 access token rejected (%s)", category)
        raise ApiError(
            status_code=401,
            code="invalid_access_token",
            message="The Bearer token is invalid or expired.",
        ) from error

    scopes = frozenset(str(claims.get("scope", "")).split())
    raw_permissions = claims.get("permissions", [])
    permissions = frozenset(
        permission
        for permission in raw_permissions
        if isinstance(permission, str)
    ) if isinstance(raw_permissions, list) else frozenset()

    required_permission = settings.auth0_required_scope
    permission_in_scope = bool(required_permission and required_permission in scopes)
    permission_in_permissions = bool(
        required_permission and required_permission in permissions
    )
    logger.info(
        "Auth0 authorization claims checked "
        "(required_in_scope=%s, required_in_permissions=%s)",
        permission_in_scope,
        permission_in_permissions,
    )

    if required_permission and not (permission_in_scope or permission_in_permissions):
        raise ApiError(
            status_code=403,
            code="insufficient_scope",
            message=f"The token requires the {required_permission!r} permission.",
        )

    return AuthContext(
        subject=str(claims["sub"]),
        scopes=scopes,
        permissions=permissions,
    )


def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    settings: Settings = request.app.state.settings

    if not settings.auth_required:
        return AuthContext(
            subject="authentication-disabled",
            scopes=frozenset(),
            permissions=frozenset(),
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="missing_access_token",
            message="A Bearer access token is required.",
        )

    return _validate_token(credentials.credentials, settings)
