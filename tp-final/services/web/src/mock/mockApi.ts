// API simulada para comparar variantes sin levantar Keycloak ni el backend (?mock=1).
// Películas reales del sample de TMDB; la recomendación imita la estrategia por semilla:
// 3 vecinos por elegida (por géneros en común) y los 12 mejores con su "because_of".
import type { Api, Movie, Recommendations } from "../api";
import data from "./movies.json";

const pool = data.pool as Movie[];
const catalog = data.catalog as Movie[];
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

function shuffle<T>(xs: T[]): T[] {
  const a = [...xs];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function similarity(a: Movie, b: Movie): number {
  const ga = new Set(a.genres);
  const shared = b.genres.filter((g) => ga.has(g)).length;
  const union = new Set([...a.genres, ...b.genres]).size || 1;
  return shared / union + (b.vote_average ?? 0) / 100;
}

export function createMockApi(): Api {
  return {
    async onboarding(n = 24) {
      await wait(450);
      return { items: shuffle(pool).slice(0, n) };
    },
    async recommend(movieIds, k = 12): Promise<Recommendations> {
      await wait(700);
      const seeds = movieIds.map((id) => pool.find((m) => m.movie_id === id) ?? catalog.find((m) => m.movie_id === id)!);
      const taken = new Set(movieIds);
      const candidates: Movie[] = [];
      for (const seed of seeds) {
        const ranked = catalog
          .filter((m) => !taken.has(m.movie_id))
          .map((m) => ({ m, s: similarity(seed, m) + Math.random() * 0.15 }))
          .sort((x, y) => y.s - x.s)
          .slice(0, 3);
        for (const { m, s } of ranked) {
          taken.add(m.movie_id);
          candidates.push({ ...m, score: s, because_of: { movie_id: seed.movie_id, title: seed.title } });
        }
      }
      const items = candidates.sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, k);
      return { items, unknown_movie_ids: [], model: { alias: "production", version: "3", config: "v2" }, latency_ms: 38 };
    },
  };
}
