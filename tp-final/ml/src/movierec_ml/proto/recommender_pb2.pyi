from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RecommendRequest(_message.Message):
    __slots__ = ("movie_ids", "k")
    MOVIE_IDS_FIELD_NUMBER: _ClassVar[int]
    K_FIELD_NUMBER: _ClassVar[int]
    movie_ids: _containers.RepeatedScalarFieldContainer[int]
    k: int
    def __init__(self, movie_ids: _Optional[_Iterable[int]] = ..., k: _Optional[int] = ...) -> None: ...

class Recommendation(_message.Message):
    __slots__ = ("movie_id", "score", "because_of")
    MOVIE_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    BECAUSE_OF_FIELD_NUMBER: _ClassVar[int]
    movie_id: int
    score: float
    because_of: int
    def __init__(self, movie_id: _Optional[int] = ..., score: _Optional[float] = ..., because_of: _Optional[int] = ...) -> None: ...

class RecommendResponse(_message.Message):
    __slots__ = ("items", "unknown_movie_ids", "model")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    UNKNOWN_MOVIE_IDS_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Recommendation]
    unknown_movie_ids: _containers.RepeatedScalarFieldContainer[int]
    model: ModelInfo
    def __init__(self, items: _Optional[_Iterable[_Union[Recommendation, _Mapping]]] = ..., unknown_movie_ids: _Optional[_Iterable[int]] = ..., model: _Optional[_Union[ModelInfo, _Mapping]] = ...) -> None: ...

class GetModelInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ModelInfo(_message.Message):
    __slots__ = ("model_name", "alias", "version", "contract_version", "embedding_dim", "n_movies", "config", "loaded_at")
    MODEL_NAME_FIELD_NUMBER: _ClassVar[int]
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_VERSION_FIELD_NUMBER: _ClassVar[int]
    EMBEDDING_DIM_FIELD_NUMBER: _ClassVar[int]
    N_MOVIES_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    LOADED_AT_FIELD_NUMBER: _ClassVar[int]
    model_name: str
    alias: str
    version: str
    contract_version: int
    embedding_dim: int
    n_movies: int
    config: str
    loaded_at: str
    def __init__(self, model_name: _Optional[str] = ..., alias: _Optional[str] = ..., version: _Optional[str] = ..., contract_version: _Optional[int] = ..., embedding_dim: _Optional[int] = ..., n_movies: _Optional[int] = ..., config: _Optional[str] = ..., loaded_at: _Optional[str] = ...) -> None: ...

class ReloadRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ReloadResponse(_message.Message):
    __slots__ = ("reloaded", "model", "message")
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    reloaded: bool
    model: ModelInfo
    message: str
    def __init__(self, reloaded: bool = ..., model: _Optional[_Union[ModelInfo, _Mapping]] = ..., message: _Optional[str] = ...) -> None: ...
