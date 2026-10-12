"""Loop de entrenamiento (CPU) y cálculo de embeddings con los pesos finales."""
import copy
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from torch import nn

from .data import Tabular, Target, Vocab, build_text, split_of
from .model import MovieEncoder, collate


@dataclass
class Inputs:
    """Entrada de la red para un conjunto de películas (sin las salidas conocidas)."""
    seqs: list[list[int]]
    numeric: np.ndarray
    categorical: np.ndarray

    def batch(self, idx) -> tuple[torch.Tensor, ...]:
        tokens, offsets = collate([self.seqs[i] for i in idx])
        return tokens, offsets, torch.from_numpy(self.numeric[idx]), torch.from_numpy(self.categorical[idx])


@dataclass
class TrainResult:
    model: MovieEncoder
    vocab: Vocab
    tabular: Tabular
    targets: list[Target]
    splits: pd.Series        # split por fila de gold/training
    history: list[dict]      # métricas por época
    best_epoch: int          # época cuyos pesos se conservan (early stopping)

    def inputs(self, df: pd.DataFrame, cfg: dict) -> Inputs:
        return encode_inputs(df, self.vocab, self.tabular, cfg)


def encode_inputs(df: pd.DataFrame, vocab: Vocab, tabular: Tabular, cfg: dict) -> Inputs:
    texts = build_text(df, cfg["text_columns"])
    return Inputs([vocab.encode(t, cfg["max_tokens"]) for t in texts], tabular.numeric_matrix(df),
                  tabular.categorical_matrix(df))


def _batches(n: int, size: int, rng: np.random.Generator | None):
    order = rng.permutation(n) if rng is not None else np.arange(n)
    for start in range(0, n, size):
        yield order[start:start + size]


def _losses(targets: list[Target], y: dict[str, np.ndarray], train_mask: np.ndarray) -> dict[str, nn.Module]:
    out = {}
    for t in targets:
        if t.kind == "multilabel":
            # pos_weight compensa clases poco frecuentes (multi-label desbalanceado).
            pos = y[t.column][train_mask].mean(0).clip(1e-3, None)
            out[t.column] = nn.BCEWithLogitsLoss(
                pos_weight=torch.from_numpy(((1 - pos) / pos).clip(1, 20).astype(np.float32)))
        else:
            out[t.column] = nn.CrossEntropyLoss()
    return out


def _loss(model, inputs: Inputs, y, idx, losses, weights) -> torch.Tensor:
    logits = model(*inputs.batch(idx))
    return sum(weights[c] * fn(logits[c], torch.from_numpy(y[c][idx])) for c, fn in losses.items())


def fit(cfg: dict, training: pd.DataFrame, log=print) -> TrainResult:
    torch.manual_seed(cfg["seed"])
    rng = np.random.default_rng(cfg["seed"])
    splits = training["id"].map(split_of)
    train_mask = (splits == "train").to_numpy()
    train_df = training[train_mask]

    vocab = Vocab.build(build_text(train_df, cfg["text_columns"]), cfg["vocab_size"], cfg["min_token_freq"])
    tabular = Tabular.build(train_df, cfg.get("tabular"))
    targets = [Target.build(train_df, col, spec) for col, spec in cfg["targets"].items()]
    inputs = encode_inputs(training, vocab, tabular, cfg)
    y = {t.column: t.encode(training) for t in targets}
    log(f"vocab={len(vocab.itos)} tabular={tabular.n_numeric}+{tabular.n_categorical} "
        f"targets={ {t.column: len(t.classes) for t in targets} } "
        f"train={train_mask.sum()} val={(splits == 'val').sum()} test={(splits == 'test').sum()}")

    model = MovieEncoder(len(vocab.itos), cfg["token_dim"], cfg["embedding_dim"],
                         {t.column: len(t.classes) for t in targets}, tabular.n_numeric, tabular.n_categorical,
                         cfg.get("categorical_dim", 32), cfg["dropout"])
    optim = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], weight_decay=1e-4)
    losses, weights = _losses(targets, y, train_mask), cfg["loss_weights"]
    train_idx, val_idx = np.flatnonzero(train_mask), np.flatnonzero((splits == "val").to_numpy())

    # Early stopping por val_loss: es la métrica de lo que se entrena (las dos cabezas, ponderadas).
    history = []
    best_loss, best_epoch, best_state = float("inf"), 0, None
    patience = cfg.get("early_stopping_patience", 3)
    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        total = 0.0
        for b in _batches(len(train_idx), cfg["batch_size"], rng):
            loss = _loss(model, inputs, y, train_idx[b], losses, weights)
            optim.zero_grad()
            loss.backward()
            optim.step()
            total += loss.item() * len(b)
        model.eval()
        with torch.no_grad():
            val_loss = sum(_loss(model, inputs, y, val_idx[b], losses, weights).item() * len(b)
                           for b in _batches(len(val_idx), 2048, None)) / max(len(val_idx), 1)
        history.append({"epoch": epoch, "train_loss": total / len(train_idx), "val_loss": val_loss})
        log(f"época {epoch}: train_loss={history[-1]['train_loss']:.4f} val_loss={val_loss:.4f}")
        if val_loss < best_loss:
            best_loss, best_epoch, best_state = val_loss, epoch, copy.deepcopy(model.state_dict())
        elif epoch - best_epoch >= patience:
            log(f"early stopping: sin mejora en val_loss desde la época {best_epoch}")
            break

    model.load_state_dict(best_state)
    return TrainResult(model, vocab, tabular, targets, splits, history, best_epoch)


@torch.no_grad()
def embed(model: MovieEncoder, inputs: Inputs, batch: int = 2048) -> np.ndarray:
    """Pasada hacia adelante con los pesos fijos hasta el tronco; filas L2-normalizadas."""
    model.eval()
    n = len(inputs.seqs)
    out = [model.embed(*inputs.batch(np.arange(i, min(i + batch, n)))).numpy() for i in range(0, n, batch)]
    emb = np.concatenate(out).astype(np.float32)
    return emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(1e-12, None)


@torch.no_grad()
def predict(model: MovieEncoder, inputs: Inputs, targets: list[Target], batch: int = 2048) -> dict[str, np.ndarray]:
    """Predicción de cada cabeza: multi-label = sigmoid >= 0.5; multi-clase = argmax."""
    model.eval()
    n = len(inputs.seqs)
    out: dict[str, list] = {t.column: [] for t in targets}
    for i in range(0, n, batch):
        logits = model(*inputs.batch(np.arange(i, min(i + batch, n))))
        for t in targets:
            z = logits[t.column]
            out[t.column].append((torch.sigmoid(z) >= 0.5).int().numpy() if t.kind == "multilabel"
                                 else z.argmax(1).numpy())
    return {c: np.concatenate(v) for c, v in out.items()}
