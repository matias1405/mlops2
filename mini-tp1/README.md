## Qué se debe entregar — Mini-TP 1 (individual, esta semana)

Servir **tu** modelo (el de Aprendizaje de Máquina, o uno simple) con FastAPI:

1. Contrato Pydantic con las **features reales** del modelo.
2. Endpoint `/v1/predict` (online) y `/health`.
3. La respuesta devuelve la predicción y la **versión del modelo**.
4. Un cliente que dispare un caso válido y uno inválido (mostrar el 422).

**Se evalúa:** que corra de punta a punta; que la validación rechace entradas malas; que el contrato coincida con las features del modelo; y que el código esté en el repo con un README de cómo ejecutarlo (con `uv`). Es el cimiento del TP integrador.

---

## Cómo ejecutarlo

Estructura:

```
mini-tp1/
├── train-model/   # entrena el modelo y genera model.joblib
├── fastapi/       # sirve el modelo (/health, /v1/predict) + client.py de prueba
├── client-app/     # frontend React que consume la API
└── docker-compose.yml
```

### 1. Entrenar el modelo

```bash
cd train-model
uv run train_model.py --data-path /ruta/al/TMDB_movie_dataset_v11.csv
```

Genera `train-model/model.joblib` y `train-model/metrics.json`. Sin `--data-path`
busca el CSV en `train-model/dataset/TMDB_movie_dataset_v11.csv`.

### 2. Levantar la API y el frontend

```bash
cd ..  # volver a mini-tp1/
docker compose up --build
```

- API: http://localhost:8000 (`/health`, `/v1/predict`)
- Frontend: http://localhost:3001

### 3. Probar la API (caso válido + caso inválido → 422)

```bash
cd fastapi
uv run --with requests client.py --base-url http://localhost:8000
```

También se puede probar desde el frontend: el botón **"Probar caso inválido (422)"**
dispara un payload inválido a propósito y muestra el error de validación en pantalla.