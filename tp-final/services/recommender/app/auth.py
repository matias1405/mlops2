"""Validación de JWT (Keycloak, realm platform) para el RPC Reload."""
import jwt


class Unauthenticated(Exception):
    pass


class PermissionDenied(Exception):
    pass


class JwtValidator:
    def __init__(self, issuer: str, jwks_url: str, required_role: str, jwks_client=None):
        self.issuer, self.required_role = issuer, required_role
        # PyJWKClient cachea las claves y las vuelve a pedir si aparece un `kid` nuevo (rotación).
        self._jwks = jwks_client or jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def validate(self, authorization: str | None) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise Unauthenticated("falta 'authorization: Bearer <token>'")
        token = authorization.split(" ", 1)[1]
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer,
                                options={"verify_aud": False, "require": ["exp", "iss"]})
        except jwt.PyJWTError as exc:
            raise Unauthenticated(f"token inválido: {exc}") from exc
        roles = set(claims.get("roles", [])) | set(claims.get("realm_access", {}).get("roles", []))
        if self.required_role not in roles:
            raise PermissionDenied(f"se requiere el rol {self.required_role!r}")
        return claims
