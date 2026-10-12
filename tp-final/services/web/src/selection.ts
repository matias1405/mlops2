import type { Movie } from "./api";

// El onboarding exige exactamente esta cantidad (el gateway rechaza cualquier otra).
export const MAX_PICKS = 5;

// Agrega o quita una película de la selección del onboarding (máximo MAX_PICKS, sin duplicados).
export function togglePick(picks: Movie[], movie: Movie): Movie[] {
  if (picks.some((p) => p.movie_id === movie.movie_id)) {
    return picks.filter((p) => p.movie_id !== movie.movie_id);
  }
  return picks.length >= MAX_PICKS ? picks : [...picks, movie];
}

// Huecos de la bandeja: las elegidas primero y después cuadros vacíos hasta completar MAX_PICKS.
export function traySlots(picks: Movie[]): (Movie | null)[] {
  return [...picks, ...Array(Math.max(0, MAX_PICKS - picks.length)).fill(null)];
}

// Géneros en común entre una recomendación y lo elegido: explica por qué aparece.
export function sharedGenres(movie: Movie, picks: Movie[]): string[] {
  const picked = new Set(picks.flatMap((p) => p.genres));
  return movie.genres.filter((g) => picked.has(g));
}
