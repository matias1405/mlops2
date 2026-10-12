import pandas as pd

from movierec_ml.catalog_db import build_catalog, build_onboarding_pool


def test_pool_pondera_votos_y_puntaje():
    catalog = pd.DataFrame({
        "movie_id": [1, 2, 3, 4],
        "vote_average": [9.5, 8.4, 7.0, 8.0],
        "vote_count": [20, 30000, 5000, 1500],  # la 1 tiene nota altísima pero casi sin votos
        "poster_path": ["/a", "/b", "/c", "/d"],
    })
    pool = build_onboarding_pool(catalog, size=3, min_votes=1000)
    assert pool["movie_id"].tolist() == [2, 4, 3]       # la 1 queda afuera por votos
    assert pool["rank"].tolist() == [1, 2, 3]
    assert pool["weighted_rating"].is_monotonic_decreasing


def test_pool_respeta_tamano():
    catalog = pd.DataFrame({"movie_id": range(500), "vote_average": [7.0] * 500,
                            "vote_count": range(1000, 1500), "poster_path": ["/p"] * 500})
    assert len(build_onboarding_pool(catalog, size=200)) == 200


def test_catalogo_del_ambiente_son_las_peliculas_del_modelo():
    app = pd.DataFrame({"id": [1, 2, 3], "title": ["a", "b", "c"], "poster_path": [None, "/b", "/c"],
                        "release_year": [2000, 2001, None], "vote_average": [7.0, 8.0, 6.0],
                        "vote_count": [300, 5000, 250], "popularity": [1.0, 2.0, 3.0],
                        "genres": [["Drama"], ["Comedy"], []]})
    catalog = build_catalog(app, [3, 1], model_version="4")
    assert sorted(catalog["movie_id"]) == [1, 3] and set(catalog["model_version"]) == {"4"}
