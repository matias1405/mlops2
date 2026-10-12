import type Keycloak from "keycloak-js";

export type Movie = {
  movie_id: number;
  title: string;
  genres: string[];
  release_year: number | null;
  vote_average: number | null;
  poster_url: string | null;
  score?: number;
  because_of?: { movie_id: number; title: string | null };
};

export type ModelInfo = { alias: string; version: string; config: string };

export type Recommendations = {
  items: Movie[];
  unknown_movie_ids: number[];
  model: ModelInfo;
  latency_ms: number;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type Api = {
  onboarding: (n?: number) => Promise<{ items: Movie[] }>;
  recommend: (movieIds: number[], k?: number) => Promise<Recommendations>;
};

export function createApi(kc: Keycloak): Api {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    await kc.updateToken(30); // renueva el token si vence en menos de 30 s
    const res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${kc.token}`, ...init.headers },
    });
    if (!res.ok) {
      const detail = await res.json().then((b) => b.detail, () => res.statusText);
      throw new ApiError(res.status, typeof detail === "string" ? detail : res.statusText);
    }
    return res.status === 204 ? (undefined as T) : res.json();
  }

  return {
    onboarding: (n = 24) => request<{ items: Movie[] }>(`/api/movies/onboarding?n=${n}`),
    recommend: (movieIds, k = 12) =>
      request<Recommendations>("/api/recommendations", { method: "POST", body: JSON.stringify({ movie_ids: movieIds, k }) }),
  };
}
