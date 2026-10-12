import { useEffect, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const GRAPHQL_URL = import.meta.env.VITE_GRAPHQL_URL || "http://localhost:8001";

const METADATA_QUERY = `query GetModel {
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
}`;

const initialForm = {
  budget: "10000000",
  runtime: "120",
  original_language: "en",
  release_date: "2024-07-15",
  genres: "Action,Comedy",
  production_countries: "United States of America",
  production_companies: "Warner Bros.",
};

function parseList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

// A propósito inválido: runtime negativo y sin genres, viola las mismas
// reglas (gt=0 / min_length=1) que fastapi/client.py usa para su caso
// inválido. Sirve para demostrar el 422 sin tocar el formulario.
const INVALID_PAYLOAD = {
  runtime: -10,
  budget: 10000000,
  original_language: "en",
  release_date: "2024-07-15",
  genres: [],
  production_companies: ["Warner Bros."],
  production_countries: ["United States of America"],
};

function App() {
  const [health, setHealth] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [validationError, setValidationError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [metadata, setMetadata] = useState(null);
  const [metadataSource, setMetadataSource] = useState(null);
  const [metadataError, setMetadataError] = useState("");
  const [metadataLoading, setMetadataLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "unreachable" }));
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setValidationError(null);
    setResult(null);

    const payload = {
      runtime: Number(form.runtime),
      budget: Number(form.budget),
      original_language: form.original_language.trim(),
      release_date: form.release_date,
      genres: parseList(form.genres),
      production_companies: parseList(form.production_companies),
      production_countries: parseList(form.production_countries),
    };

    try {
      const response = await fetch(`${API_URL}/v1/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch {
      setError("No se pudo conectar con el backend o el modelo falló al predecir.");
    } finally {
      setLoading(false);
    }
  }

  // Dispara un payload inválido a propósito (mismo caso que fastapi/client.py)
  // para mostrar en pantalla que FastAPI lo rechaza con 422.
  async function handleInvalidCase() {
    setLoading(true);
    setError("");
    setResult(null);
    setValidationError(null);

    try {
      const response = await fetch(`${API_URL}/v1/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(INVALID_PAYLOAD),
      });

      const data = await response.json();

      if (response.status === 422) {
        setValidationError(data);
      } else {
        setError(`Se esperaba 422 y llegó ${response.status} - revisá la API.`);
      }
    } catch {
      setError("No se pudo conectar con el backend.");
    } finally {
      setLoading(false);
    }
  }

  // Trae los metadatos del modelo (name, version, metrics) por REST o por
  // GraphQL y guarda cuánto tardó (round-trip, medido en el browser) y
  // cuántos bytes tenía la respuesta - para comparar sin salir del navegador.
  // Para latencia/tamaño exactos (incluyendo TTFB) usá la pestaña Network de
  // DevTools: cada fetch de acá aparece ahí con su nombre (metrics / graphql).
  async function fetchMetadata(source) {
    setMetadataLoading(true);
    setMetadataError("");
    setMetadata(null);
    setMetadataSource(source);

    const isRest = source === "REST";
    const url = isRest ? `${API_URL}/v1/metrics` : `${GRAPHQL_URL}/graphql`;
    const options = isRest
      ? { method: "GET" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: METADATA_QUERY }),
        };

    const t0 = performance.now();
    try {
      const response = await fetch(url, options);
      const text = await response.text();
      const t1 = performance.now();

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const body = JSON.parse(text);
      const data = isRest ? body : body.data?.model;

      setMetadata({
        data,
        raw: body,
        roundTripMs: t1 - t0,
        bytes: Number(response.headers.get("content-length")) || new TextEncoder().encode(text).length,
      });
    } catch (err) {
      setMetadataError(`No se pudo leer metadata por ${source}: ${err.message}`);
    } finally {
      setMetadataLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">Prediction Movies</p>
          <h1>Probá el modelo de rentabilidad de películas.</h1>
          <p className="lede">
            Enviá datos de una película y obtené una predicción del modelo
            servido por FastAPI.
          </p>

          <div className="status-card">
            <span className="status-label">Backend</span>
            <strong>{API_URL}</strong>
            <pre>{health ? JSON.stringify(health, null, 2) : "cargando..."}</pre>
          </div>
        </div>

        <form className="panel" onSubmit={handleSubmit}>
          <div className="grid">
            <label>
              Budget
              <input
                type="number"
                value={form.budget}
                onChange={(event) =>
                  setForm({ ...form, budget: event.target.value })
                }
              />
            </label>
            <label>
              Runtime
              <input
                type="number"
                value={form.runtime}
                onChange={(event) =>
                  setForm({ ...form, runtime: event.target.value })
                }
              />
            </label>
          </div>

          <label>
            Original language
            <input
              type="text"
              value={form.original_language}
              onChange={(event) =>
                setForm({ ...form, original_language: event.target.value })
              }
            />
          </label>
          <label>
            Release date
            <input
              type="date"
              value={form.release_date}
              onChange={(event) =>
                setForm({ ...form, release_date: event.target.value })
              }
            />
          </label>
          <label>
            Genres
            <textarea
              rows="2"
              value={form.genres}
              onChange={(event) => setForm({ ...form, genres: event.target.value })}
            />
          </label>

          <label>
            Production countries
            <textarea
              rows="2"
              value={form.production_countries}
              onChange={(event) =>
                setForm({ ...form, production_countries: event.target.value })
              }
            />
          </label>

          <label>
            Production companies
            <textarea
              rows="2"
              value={form.production_companies}
              onChange={(event) =>
                setForm({ ...form, production_companies: event.target.value })
              }
            />
          </label>

          <div className="actions">
            <button type="submit" disabled={loading}>
              {loading ? "Prediciendo..." : "Predecir"}
            </button>
            <button type="button" disabled={loading} onClick={handleInvalidCase}>
              Probar caso inválido (422)
            </button>
          </div>

          {error ? <div className="feedback feedback--error">{error}</div> : null}
          {result ? (
            <div className="feedback feedback--success">
              <div>
                <span>Predicción</span>
                <strong>
                  {result.prediction === 1 ? "Rentable" : "No rentable"}
                </strong>
              </div>
              {typeof result.probability === "number" ? (
                <div>
                  <span>Probabilidad de Rentabilidad</span>
                  <strong>{(result.probability * 100).toFixed(2)}%</strong>
                </div>
              ) : null}
              <div>
                <span>Versión del modelo</span>
                <strong>{result.model_version}</strong>
              </div>
            </div>
          ) : null}
          {validationError ? (
            <div className="feedback feedback--error">
              <div>
                <span>422 Unprocessable Entity</span>
                <strong>La API rechazó el payload inválido, como se esperaba.</strong>
              </div>
              <ul>
                {(validationError.detail ?? []).map((issue, index) => (
                  <li key={index}>
                    {(issue.loc ?? []).join(".")}: {issue.msg}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </form>
      </section>

      <section className="hero">
        <div className="panel compare">
          <p className="eyebrow">Mini-TP 2 · REST vs GraphQL</p>
          <h2>Metadatos del modelo: mismos datos, dos protocolos</h2>
          <p className="lede">
            Abrí DevTools → pestaña <strong>Network</strong> antes de
            clickear (filtrá por <code>metrics</code> / <code>graphql</code>).
            Ahí vas a ver el tamaño real de la respuesta (columna{" "}
            <em>Size</em>) y la latencia (<em>Time</em>, con el desglose de
            Waterfall). Los números de abajo son solo una referencia rápida
            medida en el navegador (menos precisos que DevTools).
          </p>

          <div className="actions">
            <button
              type="button"
              disabled={metadataLoading}
              onClick={() => fetchMetadata("REST")}
            >
              GET /v1/metrics (REST)
            </button>
            <button
              type="button"
              disabled={metadataLoading}
              onClick={() => fetchMetadata("GraphQL")}
            >
              POST /graphql (GraphQL)
            </button>
          </div>

          {metadataError ? (
            <div className="feedback feedback--error">{metadataError}</div>
          ) : null}

          {metadata ? (
            <div className="feedback feedback--success compare-result">
              <div>
                <span>Fuente</span>
                <strong>{metadataSource}</strong>
              </div>
              <div>
                <span>Round-trip (navegador)</span>
                <strong>{metadata.roundTripMs.toFixed(1)} ms</strong>
              </div>
              <div>
                <span>Tamaño de la respuesta</span>
                <strong>{metadata.bytes} bytes</strong>
              </div>
              <pre>{JSON.stringify(metadata.raw, null, 2)}</pre>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

export default App;
