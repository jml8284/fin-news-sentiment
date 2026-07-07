"""Tests for sentiment engine selection and scoring helpers."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.sentiment_engines import (
    analyze_dataframe,
    get_engine,
    label_from_compound,
    read_engine_metadata,
    score_text_vader,
    write_engine_metadata,
)


def test_label_from_compound_thresholds() -> None:
    assert label_from_compound(0.10) == "positive"
    assert label_from_compound(-0.10) == "negative"
    assert label_from_compound(0.0) == "neutral"


def test_vader_score_text_returns_expected_keys() -> None:
    scores = score_text_vader("Stock beats earnings expectations")
    assert set(scores) == {"neg", "neu", "pos", "compound"}


def test_analyze_dataframe_vader_adds_columns() -> None:
    df = pd.DataFrame(
        [
            {"title": "Company wins big contract", "summary": "Shares rise", "ticker": "AAA"},
        ]
    )
    out = analyze_dataframe(df, engine="vader")
    assert out.iloc[0]["sentiment_engine"] == "vader"
    assert out.iloc[0]["sentiment_label"] in {"positive", "neutral", "negative"}


def test_engine_metadata_roundtrip(tmp_path) -> None:
    meta = tmp_path / "sentiment_engine.txt"
    write_engine_metadata("finbert", meta)
    assert read_engine_metadata(meta) == "finbert"
    assert read_engine_metadata(tmp_path / "missing.txt", default="vader") == "vader"


def test_finbert_engine_uses_batch_helper() -> None:
    engine = get_engine("finbert")
    fake = [{"neg": 0.1, "neu": 0.2, "pos": 0.7, "compound": 0.6}]
    with patch("src.sentiment_engines.score_batch_finbert", return_value=fake):
        scores = engine.score_batch(["Profit warning issued"])
    assert scores[0]["compound"] == pytest.approx(0.6)
    assert scores[0]["pos"] == pytest.approx(0.7)


def test_finbert_load_error_surfaces_clear_message() -> None:
    engine = get_engine("finbert")
    with patch(
        "src.sentiment_engines._load_finbert",
        side_effect=RuntimeError("FinBERT requires transformers and torch"),
    ):
        with pytest.raises(RuntimeError, match="FinBERT requires"):
            engine.score_text("Profit warning issued")
