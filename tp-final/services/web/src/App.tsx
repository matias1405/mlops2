import { useEffect, useRef, useState, type CSSProperties } from "react";
import { ApiError, type Api, type Movie, type Recommendations } from "./api";
import type { RuntimeConfig } from "./config";
import { genreEs } from "./genres";
import { MAX_PICKS, togglePick, traySlots } from "./selection";

type Props = { config: RuntimeConfig; api: Api; username: string; onLogout: () => void };

function errorText(err: unknown, action: string): string {
  if (err instanceof ApiError && err.status === 503) return `No se pudo ${action}: el servicio de recomendaciones no responde. Probá de nuevo en unos segundos.`;
  if (err instanceof ApiError && err.status === 429) return `Hiciste muchos pedidos seguidos. Esperá un minuto para ${action}.`;
  if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return "Tu sesión no tiene acceso a este ambiente. Cerrá sesión y entrá con otra cuenta.";
  return `No se pudo ${action}. Revisá tu conexión y probá de nuevo.`;
}

/* La caja de VHS de frente: el afiche con el lomo de plástico negro a la izquierda. */
function Case({ movie, small = false }: { movie: Movie; small?: boolean }) {
  const [broken, setBroken] = useState(false);
  return (
    <span className={`case${small ? " case--sm" : ""}`}>
      {!movie.poster_url || broken
        ? <span className="case__blank" aria-hidden="true">{movie.title}</span>
        : <img className="case__cover" src={movie.poster_url} alt="" loading="lazy" onError={() => setBroken(true)} />}
    </span>
  );
}

function ShelfLabel({ movie }: { movie: Movie }) {
  return (
    <span className="label">
      <span className="label__title">{movie.title}</span>
      <span className="label__meta">
        {movie.release_year ?? "s/f"}
        {movie.genres[0] && <> · {genreEs(movie.genres[0])}</>}
        {movie.genres[1] && <span className="label__more">, {genreEs(movie.genres[1])}</span>}
      </span>
    </span>
  );
}

export function App({ config, api, username, onLogout }: Props) {
  const [choices, setChoices] = useState<Movie[]>([]);
  const [loadingChoices, setLoadingChoices] = useState(true);
  const [choicesError, setChoicesError] = useState<string | null>(null);
  const [picks, setPicks] = useState<Movie[]>([]);
  const [recs, setRecs] = useState<Recommendations | null>(null);
  const [recsFor, setRecsFor] = useState<string>("");
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);
  const recsRef = useRef<HTMLElement>(null);

  // 24 películas al azar entre las 200 más populares; cada recarga o inicio de sesión trae otra selección.
  useEffect(() => {
    let cancelled = false;
    api.onboarding(24)
      .then((r) => { if (!cancelled) setChoices(r.items); })
      .catch((err) => { if (!cancelled) setChoicesError(errorText(err, "cargar las películas")); })
      .finally(() => { if (!cancelled) setLoadingChoices(false); });
    return () => { cancelled = true; };
  }, [api]);

  const pickKey = picks.map((p) => p.movie_id).join(",");
  const full = picks.length >= MAX_PICKS;
  const stale = recs !== null && recsFor !== pickKey;

  async function recommend() {
    setLoadingRecs(true);
    setRecError(null);
    try {
      setRecs(await api.recommend(picks.map((p) => p.movie_id)));
      setRecsFor(pickKey);
      requestAnimationFrame(() => recsRef.current?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }));
    } catch (err) {
      setRecError(errorText(err, "generar recomendaciones"));
    } finally {
      setLoadingRecs(false);
    }
  }


  return (
    <>
      {config.envName === "dev" && (
        <div className="devbar" role="status">Ambiente de desarrollo: modelo y app en prueba, solo para el equipo.</div>
      )}
      <header className="storefront">
        <span className="sign">
          <img className="sign__icon" src="/logo.svg" alt="" width="64" height="60" />
          <span className="sign__word">Movie<span className="sign__rec">Rec</span></span>
        </span>
        <span className="storefront__user">
          <span className="storefront__name">{username}</span>
          <button className="link" onClick={onLogout}>Cerrar sesión</button>
        </span>
      </header>

      <main className="store">
        <section className="intro">
          <h1>Contanos qué películas te gustaron</h1>
          <p>Sacá {MAX_PICKS} cajas del estante. Con esas cinco te armamos el estante de recomendados, y cada una lleva el cartelito de cuál la trajo.</p>
        </section>

        <section aria-label="Películas para elegir" aria-busy={loadingChoices}>
          {choicesError && <p className="notice notice--error" role="alert">{choicesError}</p>}
          {!loadingChoices && !choicesError && choices.length === 0 && (
            <p className="notice">Todavía no hay películas en el estante: el catálogo de este ambiente no está cargado.</p>
          )}
          <ul className="shelf">
            {loadingChoices && Array.from({ length: 24 }, (_, i) => (
              <li key={`sk-${i}`} className="slot slot--empty" aria-hidden="true"><span className="case case--ghost" /><span className="label label--ghost" /></li>
            ))}
            {choices.map((m) => {
              const order = picks.findIndex((p) => p.movie_id === m.movie_id) + 1;
              const picked = order > 0;
              return (
                <li key={m.movie_id} className="slot">
                  <button className={`pick${picked ? " pick--on" : ""}`} onClick={() => setPicks((p) => togglePick(p, m))}
                          aria-pressed={picked} aria-disabled={!picked && full ? true : undefined}>
                    <span className="pick__box">
                      <Case movie={m} />
                      {picked && <span className="sticker" aria-hidden="true">{order}</span>}
                    </span>
                    <ShelfLabel movie={m} />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        {(recs || recError) && (
          <section className="recs" ref={recsRef} aria-live="polite">
            <div className="recs__head">
              <h2>{stale ? "Cambiaste las cajas" : "Recomendados para vos"}</h2>
              <p>{stale ? "Este estante es de tus elegidas anteriores. Actualizalo desde el mostrador."
                        : "Doce cajas, cada una con su cartelito: de cuál de tus elegidas sale."}</p>
            </div>
            {recError && <p className="notice notice--error" role="alert">{recError}</p>}
            {recs && (
              <ul className={`shelf shelf--recs${stale ? " shelf--stale" : ""}`} key={recsFor}>
                {recs.items.map((m, i) => (
                  <li key={m.movie_id} className="slot slot--rec" style={{ "--i": i } as CSSProperties}>
                    <span className="pick__box"><Case movie={m} /></span>
                    <ShelfLabel movie={m} />
                    <div className="talker" style={{ "--tilt": `${(i % 3) - 1}deg` } as CSSProperties}>
                      <span className="talker__hole" aria-hidden="true" />
                      <p className="talker__text">{m.because_of?.title ? <>Por <b>{m.because_of.title}</b></> : "Del videoclub"}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </main>

      <aside className="counter" aria-label="Películas elegidas">
        <ol className="counter__slots">
          {traySlots(picks).map((m, i) => (
            <li key={m ? m.movie_id : `empty-${i}`} className={m ? "cubby cubby--full" : "cubby"}>
              {m ? (
                <button className="cubby__btn" onClick={() => setPicks((p) => togglePick(p, m))} aria-label={`Devolver ${m.title} al estante`}>
                  <Case movie={m} small />
                  <span className="cubby__n" aria-hidden="true">{i + 1}</span>
                </button>
              ) : <span className="cubby__n cubby__n--empty" aria-hidden="true">{i + 1}</span>}
            </li>
          ))}
        </ol>
        <div className="counter__action">
          <span className="counter__count"><b>{picks.length}</b>/{MAX_PICKS}</span>
          <span className="counter__hint" aria-live="polite">
            {full ? "Para cambiar una, tocala acá y devolvela al estante." : "Tocá una caja del estante para sacarla."}
          </span>
          <button className="cta" onClick={recommend} disabled={!full || loadingRecs || (recs !== null && !stale)}
                  data-loading={loadingRecs || undefined}>
            {loadingRecs ? "Buscando recomendaciones…"
              : !full ? `Elegí ${MAX_PICKS - picks.length} más`
              : recs && !stale ? "Estante al día" : recs ? "Actualizar recomendaciones" : "Ver recomendaciones"}
          </button>
        </div>
      </aside>

      <footer className="receipt">
        {recs && (
          <p className="receipt__model">
            Atendido por el modelo <b>{recs.model.config}</b> · versión {recs.model.version} · @{recs.model.alias}
          </p>
        )}
        <p>Esta aplicación usa datos e imágenes de TMDB, pero no está avalada ni certificada por TMDB.</p>
      </footer>
    </>
  );
}
