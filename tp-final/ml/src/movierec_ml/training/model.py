"""Clasificador de dos salidas: texto (EmbeddingBag) + tabular -> tronco (embedding de película) -> cabezas."""
import torch
from torch import nn


class MovieEncoder(nn.Module):
    def __init__(self, vocab_size: int, token_dim: int, embedding_dim: int, heads: dict[str, int],
                 n_numeric: int = 0, n_categorical: int = 0, categorical_dim: int = 32, dropout: float = 0.2):
        super().__init__()
        self.bag = nn.EmbeddingBag(vocab_size, token_dim, mode="mean", padding_idx=0)
        # Las categóricas (one-hot / multi-hot) pasan por una capa lineal; las numéricas entran directo.
        self.categorical = nn.Linear(n_categorical, categorical_dim) if n_categorical else None
        in_dim = token_dim + n_numeric + (categorical_dim if n_categorical else 0)
        self.trunk = nn.Sequential(
            nn.Linear(in_dim, embedding_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(embedding_dim, embedding_dim),
        )
        self.heads = nn.ModuleDict({name: nn.Sequential(nn.ReLU(), nn.Dropout(dropout), nn.Linear(embedding_dim, n))
                                    for name, n in heads.items()})

    def embed(self, tokens: torch.Tensor, offsets: torch.Tensor, numeric: torch.Tensor,
              categorical: torch.Tensor) -> torch.Tensor:
        """Embedding de película (salida del tronco). Es lo único que se usa en serving."""
        parts = [self.bag(tokens, offsets), numeric]
        if self.categorical is not None:
            parts.append(self.categorical(categorical))
        return self.trunk(torch.cat(parts, dim=1))

    def forward(self, tokens, offsets, numeric, categorical) -> dict[str, torch.Tensor]:
        z = self.embed(tokens, offsets, numeric, categorical)
        return {name: head(z) for name, head in self.heads.items()}


def collate(sequences: list[list[int]]) -> tuple[torch.Tensor, torch.Tensor]:
    """Formato de EmbeddingBag: tokens concatenados + offset de inicio de cada película."""
    lengths = torch.tensor([len(s) for s in sequences])
    offsets = torch.cat([torch.zeros(1, dtype=torch.long), lengths.cumsum(0)[:-1]])
    tokens = torch.tensor([t for s in sequences for t in s], dtype=torch.long)
    return tokens, offsets
