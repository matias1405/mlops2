import json

import numpy as np
import pandas as pd
import pytest
import torch

from movierec_ml import serving_bundle as sb
from movierec_ml.dataops.transform import build_app_catalog, build_training, clean
from movierec_ml.training.data import Tabular, Target, Vocab, build_text, split_of, tokenize
from movierec_ml.training.evaluation import evaluate, heads_tag, loggable
from movierec_ml.training.model import MovieEncoder, collate
from movierec_ml.training.train import embed, fit

BASE = {
    "embedding_dim": 16, "token_dim": 16, "categorical_dim": 8, "vocab_size": 2000, "min_token_freq": 2,
    "max_tokens": 64, "dropout": 0.1, "epochs": 2, "early_stopping_patience": 1, "batch_size": 128,
    "learning_rate": 0.01, "seed": 7,
}
CFG_COMPANY = {**BASE, "name": "t1", "text_columns": ["title", "overview", "tagline", "keywords"],
               "tabular": {"numeric": ["budget", "release_year"], "categorical": {"original_language": {"top": 5}}},
               "targets": {"genres": {"type": "multilabel"},
                           "production_companies": {"type": "multilabel", "top": 20}},
               "loss_weights": {"genres": 1.0, "production_companies": 0.5}}
CFG_LANGUAGE = {**BASE, "name": "t4", "text_columns": ["title", "overview", "tagline"],
                "tabular": {"numeric": ["budget", "release_year"],
                            "categorical": {"keywords": {"top": 30}, "production_companies": {"top": 20}}},
                "targets": {"genres": {"type": "multilabel"}, "original_language": {"type": "multiclass", "top": 5}},
                "loss_weights": {"genres": 1.0, "original_language": 0.5}}


@pytest.fixture(scope="module")
def training(raw_sample):
    silver, _ = clean(raw_sample)
    return build_training(silver, 10)[0].head(1500).reset_index(drop=True)


@pytest.fixture(scope="module")
def app_catalog(raw_sample, training):
    silver, _ = clean(raw_sample)
    return build_app_catalog(training, silver, 2000)[0]


def test_tokenize_y_vocab():
    assert tokenize("A Space Odyssey, 2001!") == ["a", "space", "odyssey", "2001"]
    vocab = Vocab.build(["space space ship", "space ship"], size=10, min_freq=2)
    assert vocab.itos[:2] == ["<pad>", "<unk>"] and "space" in vocab.stoi
    assert vocab.encode("space alien", 10) == [vocab.stoi["space"], 1]
    assert vocab.encode("", 10) == [1]  # nunca una secuencia vacía


def test_split_determinista_y_proporciones():
    assert split_of(123) == split_of(123)
    counts = pd.Series([split_of(i) for i in range(5000)]).value_counts(normalize=True)
    assert 0.75 < counts["train"] < 0.85 and 0.05 < counts["test"] < 0.15


def test_build_text_une_listas_e_ignora_nulos(training):
    row = training.head(1).assign(tagline=None)
    text = build_text(row, ["title", "tagline", "keywords"]).iloc[0]
    assert training.loc[0, "title"] in text and training.loc[0, "keywords"][0] in text


def test_targets_configurables(training):
    genres = Target.build(training, "genres", {"type": "multilabel"})
    companies = Target.build(training, "production_companies", {"type": "multilabel", "top": 10})
    language = Target.build(training, "original_language", {"type": "multiclass", "top": 2})
    assert genres.encode(training).shape == (len(training), len(genres.classes)) and genres.metric == "f1_genre"
    assert len(companies.classes) == 10 and companies.metric == "f1_company"
    assert language.classes[-1] == "other" and len(language.classes) == 3 and language.metric == "f1_language"
    assert language.encode(training).max() <= 2


def test_tabular_estandariza_y_marca_nulos(training):
    tab = Tabular.build(training, {"numeric": ["budget", "release_year"],
                                   "categorical": {"original_language": {"top": 3}, "keywords": {"top": 30}}})
    num = tab.numeric_matrix(training)
    assert num.shape == (len(training), 4) and abs(num[:, 2].mean()) < 0.5
    assert set(np.unique(num[:, 1])) <= {0.0, 1.0}                 # indicador de budget nulo
    cat = tab.categorical_matrix(training)
    assert cat.shape == (len(training), 4 + 30)                     # one-hot top 3 + other, multi-hot top 30
    assert (cat[:, :4].sum(1) == 1).all()                           # idioma: exactamente una clase


def test_modelo_formas():
    model = MovieEncoder(vocab_size=50, token_dim=8, embedding_dim=12, heads={"genres": 4, "original_language": 3},
                         n_numeric=4, n_categorical=6)
    tokens, offsets = collate([[2, 3, 4], [5], [6, 7]])
    num, cat = torch.zeros(3, 4), torch.zeros(3, 6)
    out = model(tokens, offsets, num, cat)
    assert out["genres"].shape == (3, 4) and out["original_language"].shape == (3, 3)
    assert model.embed(tokens, offsets, num, cat).shape == (3, 12)


@pytest.mark.parametrize("cfg,present,absent,heads", [
    (CFG_COMPANY, "f1_company", "f1_language", "genre,company"),
    (CFG_LANGUAGE, "f1_language", "f1_company", "genre,language"),
])
def test_fit_evaluate_f1_null_segun_config(training, cfg, present, absent, heads):
    result = fit(cfg, training, log=lambda *_: None)
    assert 1 <= result.best_epoch <= len(result.history) and "val_loss" in result.history[0]
    metrics = evaluate(result, training, cfg)
    assert metrics[absent] is None and 0 <= metrics[present] <= 1 and 0 <= metrics["f1_genre"] <= 1
    assert metrics["f1_mean"] == pytest.approx((metrics["f1_genre"] + metrics[present]) / 2)
    assert absent not in loggable(metrics) and heads_tag(result) == heads


def test_embeddings_solo_de_app_catalog_y_bundle(training, app_catalog, tmp_path):
    result = fit(CFG_COMPANY, training, log=lambda *_: None)
    features = training.set_index("id").loc[app_catalog["id"]].reset_index()
    emb = embed(result.model, result.inputs(features, CFG_COMPANY))
    assert emb.shape == (len(app_catalog), 16) and np.allclose(np.linalg.norm(emb, axis=1), 1, atol=1e-4)

    path = sb.write_bundle(tmp_path / "b", emb, app_catalog["id"], {"text_columns": CFG_COMPANY["text_columns"]})
    bundle = sb.load_bundle(path)
    assert bundle["manifest"]["n_movies"] == len(app_catalog)
    ex = sb.examples(emb, app_catalog)
    assert len(ex) == 3 and all(len(e["neighbors"]) == 5 for e in ex)
    card = sb.model_card(CFG_COMPANY, {"f1_genre": 0.5, "f1_company": 0.2, "f1_language": None, "f1_mean": 0.35},
                         "genre,company", {"rows": len(training), "app_catalog_rows": len(app_catalog)}, training, ex)
    assert "| f1_language | n/a |" in card and ex[0]["title"] in card


def test_bundle_incompatible_es_rechazado(app_catalog, tmp_path):
    emb = np.eye(len(app_catalog), 4, dtype=np.float32)
    path = sb.write_bundle(tmp_path / "b", emb, app_catalog["id"], {})
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["contract_version"] = 99
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(sb.IncompatibleBundle):
        sb.load_bundle(path)


def test_recommend_per_seed_cuota_normalizacion_y_corte():
    rng = np.random.default_rng(0)
    emb = rng.normal(size=(300, 8)).astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    seeds = [0, 1, 2, 3, 4]
    recs = sb.recommend_per_seed(emb, seeds, k=12)
    assert len(recs) == 12                                   # 5 semillas x 3 = 15 candidatos -> 12
    assert not {r for r, _, _ in recs} & set(seeds)
    assert [z for _, z, _ in recs] == sorted((z for _, z, _ in recs), reverse=True)
    per_seed = {s: sum(1 for _, _, b in recs if b == s) for s in seeds}
    assert all(v <= 3 for v in per_seed.values())            # nadie aporta más de su cuota


def test_recommend_per_seed_pocas_semillas_llena_k():
    assert sb.per_seed_quota(5, 12) == 3 and sb.per_seed_quota(4, 12) == 3
    assert sb.per_seed_quota(2, 12) == 6 and sb.per_seed_quota(1, 12) == 12
    emb = np.eye(40, 6, dtype=np.float32) + 0.01
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    assert len(sb.recommend_per_seed(emb, [0, 1], k=12)) == 12


def test_recommend_per_seed_una_semilla_puede_no_aportar():
    # Con corte en k, alguna semilla puede quedar sin aportes.
    rng = np.random.default_rng(1)
    emb = rng.normal(size=(200, 8)).astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    recs = sb.recommend_per_seed(emb, [0, 1, 2, 3, 4], k=3)
    assert len(recs) == 3 and len({b for _, _, b in recs}) <= 3
