## Mini-TP 2 — Metadatos del modelo por GraphQL

Expone `name`, `version` y `metrics` del modelo de rentabilidad de películas por
GraphQL (Strawberry + FastAPI), y sirve el mismo modelo por REST (Mini-TP1) para
poder comparar ambos.

```
mini-tp2/
├── model/            # model.joblib (ya entrenado) + metrics.json (opcional)
├── fastapi/          # REST API - igual que mini-tp1 (/health, /v1/predict)
├── graphql/           # GraphQL API - Model(name, version, metrics)
├── client-app/        # frontend React - igual que mini-tp1
└── docker-compose.yml
```

### Cómo ejecutarlo

```bash
docker compose up --build
```

- REST (Mini-TP1): http://localhost:8000 — `/health`, `/v1/predict`
- GraphQL (Mini-TP2): http://localhost:8001/graphql — GraphiQL en el navegador
- Frontend: http://localhost:3001

Query de ejemplo en GraphiQL:
```graphql
query {
  model {
    name
    version
    metrics {
      accuracy
      precision
      recall
      f1
      rocAuc
    }
  }
}
```

O desde un cliente Python:
```bash
cd graphql
uv run --with requests client.py --base-url http://localhost:8001
```

### Metadatos del modelo: REST vs GraphQL

Ambas APIs sirven **la misma lectura** (`name`, `version`, `metrics`), leída del
mismo `model/metrics.json` montado como volumen en los dos contenedores:

- REST: `GET /v1/metrics` → http://localhost:8000/v1/metrics
- GraphQL: `POST /graphql` con `{ model { name version metrics { accuracy precision recall f1 rocAuc } } }`

### Comparar velocidad y bytes desde el navegador (sin scripts)

El frontend (http://localhost:3001) tiene una sección **"Metadatos del modelo:
mismos datos, dos protocolos"** con dos botones, uno por protocolo. Pasos:

1. Abrí DevTools (F12) → pestaña **Network**.
2. Tildá **Preserve log** y limpiá la lista (ícono 🚫 o `Ctrl+L`) antes de cada prueba.
3. Clickeá **"GET /v1/metrics (REST)"**. Va a aparecer una fila `metrics`.
4. Limpiá de nuevo y clickeá **"POST /graphql (GraphQL)"**. Aparece una fila `graphql`.
5. Para cada fila mirá:
   - **Size** (columna, o pestaña *Response* / *Headers* → `content-length`): bytes reales transferidos.
   - **Time**: latencia total; abrí la fila y mirá el **Waterfall** para separar
     *Waiting (TTFB)* de *Content Download*.
   - **Payload / Request** (solo GraphQL): el POST tiene un body con la query -
     eso también son bytes *enviados*, a diferencia del GET de REST.
6. La tarjeta de resultado en la página también muestra un round-trip medido
   con `performance.now()` en el propio navegador (referencia rápida, menos
   preciso que Network porque no separa TTFB de descarga).

**Qué se espera notar:** con un solo campo (`Model`) la diferencia de bytes
entre REST y GraphQL va a ser chica (ambos devuelven básicamente lo mismo,
GraphQL con algo de overhead por el sobre `{"data": {...}}` y los nombres de
campo repetidos si pedís varios). La ventaja de GraphQL se nota más al *pedir
menos campos de los que trae REST* (over-fetching) o al necesitar *unir varios
recursos* en una sola llamada (evita N+1) — no tanto en este único endpoint.
Anotá acá tu propia conclusión después de probarlo.
