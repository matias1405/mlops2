import { describe, expect, it } from "vitest";
import type { Movie } from "./api";
import { MAX_PICKS, sharedGenres, togglePick, traySlots } from "./selection";

const movie = (id: number, genres: string[] = ["Drama"]): Movie => ({
  movie_id: id, title: `m${id}`, genres, release_year: 2000, vote_average: 7, poster_url: null,
});

describe("selección del onboarding", () => {
  it("agrega y quita con el mismo gesto", () => {
    const one = togglePick([], movie(1));
    expect(one.map((m) => m.movie_id)).toEqual([1]);
    expect(togglePick(one, movie(1))).toEqual([]);
  });

  it("no supera el máximo", () => {
    let picks: Movie[] = [];
    for (let i = 1; i <= MAX_PICKS + 2; i++) picks = togglePick(picks, movie(i));
    expect(picks).toHaveLength(MAX_PICKS);
  });

  it("la bandeja siempre tiene MAX_PICKS cuadros", () => {
    expect(traySlots([])).toEqual(Array(MAX_PICKS).fill(null));
    expect(traySlots([movie(1)])[0]?.movie_id).toBe(1);
    expect(traySlots([movie(1)])).toHaveLength(MAX_PICKS);
  });

  it("géneros en común con lo elegido", () => {
    expect(sharedGenres(movie(9, ["Animation", "Comedy"]), [movie(1, ["Animation"]), movie(2, ["Family"])]))
      .toEqual(["Animation"]);
  });
});
