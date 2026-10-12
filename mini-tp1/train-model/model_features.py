"""Transformer custom del pipeline v1, en módulo propio.

Separado de train_model.py a propósito: joblib pickla las instancias de
FeatureEngineering con una referencia a `<módulo>.FeatureEngineering`. Si
esta clase viviera en el script de entrenamiento (`__main__` al correrlo con
`python train_model.py`), el FastAPI que sirve el modelo no podría
deserializarla. Mantené un `model_features.py` idéntico en `fastapi/` para
que el nombre de módulo coincida en ambos lados.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import MultiLabelBinarizer


class FeatureEngineering(BaseEstimator, TransformerMixin):
    def __init__(self, n_top_languages=10, n_top_countries=25, n_top_companies=35):
        self.n_top_languages = n_top_languages
        self.n_top_countries = n_top_countries
        self.n_top_companies = n_top_companies

    def _to_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if pd.isna(value):
            return []
        return [v.strip() for v in str(value).split(",") if v.strip()]

    def _convert_to_lists(self, df):
        df = df.copy()
        for col in ["genres", "production_countries", "production_companies"]:
            df[col] = df[col].apply(self._to_list)
        return df

    def fit(self, X, y=None):
        X = self._convert_to_lists(X)
        self.top_languages_ = (
            X["original_language"].value_counts().nlargest(self.n_top_languages).index.tolist()
        )
        self.mlb_genres_ = MultiLabelBinarizer()
        self.mlb_genres_.fit(X["genres"])
        self.top_countries_ = (
            X["production_countries"].explode().value_counts().nlargest(self.n_top_countries).index.tolist()
        )
        self.mlb_countries_ = MultiLabelBinarizer(classes=self.top_countries_)
        self.mlb_countries_.fit(X["production_countries"])
        self.top_companies_ = (
            X["production_companies"].explode().value_counts().nlargest(self.n_top_companies).index.tolist()
        )
        self.mlb_companies_ = MultiLabelBinarizer(classes=self.top_companies_)
        self.mlb_companies_.fit(X["production_companies"])
        return self

    def transform(self, X):
        X = self._convert_to_lists(X)
        X["n_genres"] = X["genres"].apply(len)

        X["original_language"] = X["original_language"].where(
            X["original_language"].isin(self.top_languages_), "other"
        )
        language_encoded = pd.get_dummies(X["original_language"], prefix="lang", dtype=int)
        expected_languages = [f"lang_{lang}" for lang in self.top_languages_] + ["lang_other"]
        language_encoded = language_encoded.reindex(columns=expected_languages, fill_value=0)
        X = pd.concat([X.drop(columns=["original_language"]), language_encoded], axis=1)

        genres_encoded = self.mlb_genres_.transform(X["genres"])
        genres_df = pd.DataFrame(
            genres_encoded, columns=[f"genre_{g}" for g in self.mlb_genres_.classes_], index=X.index
        )
        X = pd.concat([X.drop(columns=["genres"]), genres_df], axis=1)

        countries = X["production_countries"].apply(
            lambda values: [c for c in values if c in self.top_countries_]
        )
        countries_encoded = self.mlb_countries_.transform(countries)
        countries_df = pd.DataFrame(
            countries_encoded, columns=[f"country_{c}" for c in self.mlb_countries_.classes_], index=X.index
        )
        X = pd.concat([X.drop(columns=["production_countries"]), countries_df], axis=1)

        companies = X["production_companies"].apply(
            lambda values: [c for c in values if c in self.top_companies_]
        )
        companies_encoded = self.mlb_companies_.transform(companies)
        companies_df = pd.DataFrame(
            companies_encoded, columns=[f"company_{c}" for c in self.mlb_companies_.classes_], index=X.index
        )
        X = pd.concat([X.drop(columns=["production_companies"]), companies_df], axis=1)

        X["budget"] = np.log1p(X["budget"])
        X["release_month"] = pd.to_datetime(X["release_date"]).dt.month
        X = X.drop(columns=["release_date"])

        X = X.select_dtypes(include=["number", "bool"])
        return X
