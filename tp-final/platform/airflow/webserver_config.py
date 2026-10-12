"""Login de la UI de Airflow con Keycloak (realm `platform`) vía Flask-AppBuilder OAuth.

- El navegador va a Keycloak por la URL pública (KEYCLOAK_PUBLIC_URL, issuer de los tokens).
- Airflow canjea el code y consulta userinfo por la red interna (http://keycloak:8080).
- Los roles del realm (claim `roles`) se mapean a roles de Airflow en cada login.
"""
import os

from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask_appbuilder.security.manager import AUTH_OAUTH

KC_PUBLIC = os.environ["KEYCLOAK_PUBLIC_URL"].rstrip("/")
KC_INTERNAL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080").rstrip("/")
REALM = os.environ.get("KEYCLOAK_REALM", "platform")
OIDC_PUBLIC = f"{KC_PUBLIC}/realms/{REALM}/protocol/openid-connect"
OIDC_INTERNAL = f"{KC_INTERNAL}/realms/{REALM}/protocol/openid-connect"

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True          # crea el usuario de Airflow en el primer login
AUTH_USER_REGISTRATION_ROLE = "Public"  # sin rol del realm => sin permisos
AUTH_ROLES_SYNC_AT_LOGIN = True         # los cambios de rol en Keycloak se aplican al siguiente login
PERMANENT_SESSION_LIFETIME = 1800

# Rol del realm `platform` -> rol de Airflow (ver docs/roles.md). DataScientist es un rol a medida
# (platform/airflow/init_roles.py): ve todo, pero solo dispara los DAGs que le asigna `access_control`
# en cada DAG (datos y entrenamiento). promote y validate_dev solo los dispara ml-engineer (Admin).
AUTH_ROLES_MAPPING = {
    "ml-engineer": ["Admin"],
    "data-scientist": ["DataScientist"],
    "app-developer": ["Viewer"],
}

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ["KC_AIRFLOW_CLIENT_ID"],
            "client_secret": os.environ["KC_AIRFLOW_CLIENT_SECRET"],
            "client_kwargs": {"scope": "openid profile email"},
            "authorize_url": f"{OIDC_PUBLIC}/auth",
            "access_token_url": f"{OIDC_INTERNAL}/token",
            "api_base_url": f"{OIDC_INTERNAL}/",
            "jwks_uri": f"{OIDC_INTERNAL}/certs",
        },
    }
]


class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    def get_oauth_user_info(self, provider, response):
        if provider != "keycloak":
            return super().get_oauth_user_info(provider, response)
        me = self.appbuilder.sm.oauth_remotes[provider].get("userinfo").json()
        return {
            "username": me["preferred_username"],
            "email": me.get("email"),
            "first_name": me.get("given_name", ""),
            "last_name": me.get("family_name", ""),
            "role_keys": me.get("roles", []),
        }


SECURITY_MANAGER_CLASS = KeycloakSecurityManager
