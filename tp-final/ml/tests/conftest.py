from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample" / "tmdb_sample.csv"


@pytest.fixture(scope="session")
def raw_sample():
    from movierec_ml.dataops.transform import read_raw

    df, skipped = read_raw(SAMPLE)
    assert skipped == 0
    return df
