"""Validación de JWT de Keycloak como dependencia de FastAPI.

- iss: realm del ambiente (prod -> movierec, dev -> platform; un token del otro realm es 401).
- azp: el client que pidió el token tiene que estar habilitado (frontend del ambiente o qa-bot en dev).
- roles: al menos uno de los requeridos (prod: movierec-user; dev: cualquier rol del equipo) -> si no, 403.
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    sub: str
    username: str
    roles: frozenset[str]
    client: str


class TokenVerifier:
    def __init__(self, issuer: str, jwks_url: str, allowed_clients, required_roles, jwks_client=None):
        self.issuer, self.allowed_clients, self.required_roles = issuer, set(allowed_clients), set(required_roles)
        self._jwks = jwks_client or jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def verify(self, token: str) -> User:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer,
                                options={"verify_aud": False, "require": ["exp", "iss", "sub"]})
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            raise HTTPException(401, f"token inválido: {exc}", headers={"WWW-Authenticate": "Bearer"}) from exc
        client = claims.get("azp", "")
        if client not in self.allowed_clients:
            raise HTTPException(401, f"client {client!r} no habilitado en este ambiente")
        roles = frozenset(claims.get("roles", [])) | frozenset(claims.get("realm_access", {}).get("roles", []))
        if not roles & self.required_roles:
            raise HTTPException(403, f"se requiere alguno de los roles {sorted(self.required_roles)}")
        return User(claims["sub"], claims.get("preferred_username", client), roles, client)


def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if creds is None:
        raise HTTPException(401, "falta 'Authorization: Bearer <token>'", headers={"WWW-Authenticate": "Bearer"})
    return request.app.state.verifier.verify(creds.credentials)

