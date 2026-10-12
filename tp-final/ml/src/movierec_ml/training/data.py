"""Preparación de datos: texto por película, tokenizer, features tabulares, targets y split train/val/test."""
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TOKEN_RE = re.compile(r"[a-z0-9áéíóúñü']+")
PAD, UNK = 0, 1
OTHER = "other"
# Nombre de la métrica por target (las cuatro configs comparten genres; company y language se alternan).
METRIC_NAMES = {"genres": "f1_genre", "production_companies": "f1_company", "original_language": "f1_language"}


def build_text(df: pd.DataFrame, text_columns: list[str]) -> pd.Series:
    """Une las columnas de texto elegidas en la config (las listas, p.ej. keywords, se unen con espacios)."""
    parts = []
    for col in text_columns:
        s = df[col]
        parts.append(s.map(lambda v: " ".join(v) if isinstance(v, (list, np.ndarray)) else (v if isinstance(v, str) else "")))
    return pd.concat(parts, axis=1).agg(" ".join, axis=1)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class Vocab:
    itos: list[str]
    stoi: dict[str, int] = field(init=False)

    def __post_init__(self):
        self.stoi = {t: i for i, t in enumerate(self.itos)}

    @classmethod
    def build(cls, texts, size: int, min_freq: int) -> "Vocab":
        counts = Counter(tok for t in texts for tok in tokenize(t))
        common = [t for t, c in counts.most_common(size) if c >= min_freq]
        return cls(["<pad>", "<unk>"] + common)

    def encode(self, text: str, max_tokens: int) -> list[int]:
        ids = [self.stoi.get(t, UNK) for t in tokenize(text)][:max_tokens]
        return ids or [UNK]


def split_of(movie_id: int, val: float = 0.1, test: float = 0.1) -> str:
    """Split determinístico por id: la misma película cae siempre en el mismo conjunto."""
    bucket = int(hashlib.md5(str(movie_id).encode()).hexdigest(), 16) % 1000 / 1000
    return "test" if bucket < test else "val" if bucket < test + val else "train"


def _as_list(v) -> list:
    return list(v) if isinstance(v, (list, np.ndarray)) else []


def top_values(series: pd.Series, top: int | None) -> list[str]:
    """Valores más frecuentes de una columna (listas o escalares), en orden de frecuencia."""
    values = series.explode() if series.map(lambda v: isinstance(v, (list, np.ndarray))).any() else series
    counts = values.dropna().value_counts()
    return [str(v) for v in (counts.index if top is None else counts.index[:top])]


@dataclass
class Target:
    """Una salida del clasificador.

    multilabel: columna lista (géneros, productoras) -> sigmoid por clase; sin ninguna clase del top -> vector 0.
    multiclass: columna escalar (idioma) -> softmax sobre el top + "other".
    """
    column: str
    kind: str
    classes: list[str]

    @classmethod
    def build(cls, df: pd.DataFrame, column: str, spec: dict) -> "Target":
        classes = top_values(df[column], spec.get("top"))
        if spec["type"] == "multilabel":
            return cls(column, "multilabel", sorted(classes) if spec.get("top") is None else classes)
        return cls(column, "multiclass", classes + [OTHER])

    @property
    def metric(self) -> str:
        return METRIC_NAMES.get(self.column, f"f1_{self.column}")

    def encode(self, df: pd.DataFrame) -> np.ndarray:
        idx = {c: i for i, c in enumerate(self.classes)}
        if self.kind == "multilabel":
            y = np.zeros((len(df), len(self.classes)), dtype=np.float32)
            for row, values in enumerate(df[self.column]):
                for v in _as_list(values):
                    if v in idx:
                        y[row, idx[v]] = 1.0
            return y
        other = len(self.classes) - 1
        return df[self.column].map(lambda v: idx.get(v, other)).to_numpy(dtype=np.int64)


@dataclass
class Tabular:
    """Features de entrada no textuales.

    numeric: log1p(budget) y año estandarizados con media/desvío de train, más un indicador de nulo
             (el nulo se imputa con la media = 0 después de estandarizar).
    categorical: one-hot (columna escalar, top N + "other") o multi-hot (columna lista, top N).
    """
    numeric: list[str]
    stats: dict[str, tuple[float, float]]
    categorical: dict[str, list[str]]

    LOG_COLUMNS = ("budget",)

    @classmethod
    def build(cls, train: pd.DataFrame, spec: dict | None) -> "Tabular":
        spec = spec or {}
        numeric = list(spec.get("numeric", []))
        stats = {}
        for col in numeric:
            x = cls._raw_numeric(train, col)
            x = x[~np.isnan(x)]
            stats[col] = (float(x.mean()) if len(x) else 0.0, float(x.std()) if len(x) and x.std() > 0 else 1.0)
        categorical = {}
        for col, opts in (spec.get("categorical") or {}).items():
            values = top_values(train[col], opts.get("top"))
            scalar = not train[col].map(lambda v: isinstance(v, (list, np.ndarray))).any()
            categorical[col] = values + ([OTHER] if scalar else [])
        return cls(numeric, stats, categorical)

    @classmethod
    def _raw_numeric(cls, df: pd.DataFrame, col: str) -> np.ndarray:
        x = pd.to_numeric(df[col], errors="coerce").astype(float).to_numpy()
        return np.log1p(x) if col in cls.LOG_COLUMNS else x

    @property
    def n_numeric(self) -> int:
        return 2 * len(self.numeric)

    @property
    def n_categorical(self) -> int:
        return sum(len(v) for v in self.categorical.values())

    def numeric_matrix(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for col in self.numeric:
            x = self._raw_numeric(df, col)
            mean, std = self.stats[col]
            missing = np.isnan(x)
            cols.append(np.where(missing, 0.0, (x - mean) / std))
            cols.append(missing.astype(float))
        return np.stack(cols, axis=1).astype(np.float32) if cols else np.zeros((len(df), 0), np.float32)

    def categorical_matrix(self, df: pd.DataFrame) -> np.ndarray:
        blocks = []
        for col, values in self.categorical.items():
            idx = {v: i for i, v in enumerate(values)}
            block = np.zeros((len(df), len(values)), dtype=np.float32)
            for row, v in enumerate(df[col]):
                if isinstance(v, (list, np.ndarray)):
                    for item in v:
                        if item in idx:
                            block[row, idx[item]] = 1.0
                elif (j := idx.get(v, idx.get(OTHER))) is not None:
                    block[row, j] = 1.0
            blocks.append(block)
        return np.concatenate(blocks, axis=1) if blocks else np.zeros((len(df), 0), np.float32)

    def to_json(self) -> dict:
        return {"numeric": self.numeric, "stats": self.stats, "categorical": self.categorical}
