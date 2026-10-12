#!/usr/bin/env python3
"""Genera los .env a partir de sus plantillas reemplazando <generate> por secretos aleatorios.

Uso: python3 scripts/gen_secrets.py platform.env.template [...]

- Si el .env no existe, se crea completo.
- Si ya existe, solo se AGREGAN las claves nuevas de la plantilla; los valores existentes nunca
  se modifican (cambiarlos invalidaría volúmenes ya inicializados: Postgres, MinIO, Keycloak).
"""
import base64
import secrets
import sys
from pathlib import Path


def generate(kind: str) -> str:
    if kind == "fernet":
        # Clave Fernet: 32 bytes aleatorios en base64 url-safe (igual que Fernet.generate_key()).
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    # 32 caracteres url-safe (sirve también como cookie secret de 32 bytes para oauth2-proxy).
    return secrets.token_urlsafe(24)


def render_line(line: str) -> str:
    if "=<generate" in line and not line.lstrip().startswith("#"):
        key, placeholder = line.split("=", 1)
        kind = placeholder.strip("<>").partition(":")[2]
        return f"{key}={generate(kind)}"
    return line


def keys_of(lines: list[str]) -> set[str]:
    return {line.split("=", 1)[0] for line in lines if "=" in line and not line.lstrip().startswith("#")}


def render(template: Path) -> None:
    target = template.with_name(template.name.removesuffix(".template"))
    tpl_lines = template.read_text(encoding="utf-8").splitlines()
    if not target.exists():
        target.write_text("\n".join(render_line(line) for line in tpl_lines) + "\n", encoding="utf-8")
        target.chmod(0o600)
        print(f"+ {target} generado")
        return
    current = target.read_text(encoding="utf-8").splitlines()
    existing = keys_of(current)
    missing = [line for line in tpl_lines if "=" in line and not line.lstrip().startswith("#")
               and line.split("=", 1)[0] not in existing]
    if not missing:
        print(f"= {target} al día")
        return
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n# --- agregadas por make secrets ---\n")
        fh.write("\n".join(render_line(line) for line in missing) + "\n")
    print(f"~ {target}: agregadas {', '.join(line.split('=', 1)[0] for line in missing)}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        render(Path(arg))
