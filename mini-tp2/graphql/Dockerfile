# Build context = graphql/ (no necesita ../model - se monta como volumen en
# runtime, ver docker-compose.yml, así metrics.json puede aparecer/cambiar
# sin tener que reconstruir la imagen).
FROM python:3.11-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY app.py client.py ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
