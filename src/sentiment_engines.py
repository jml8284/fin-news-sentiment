"""
Pluggable sentiment scorers for the fin-news-sentiment pipeline.

Engines:
  - vader   : fast rule-based baseline (default)
  - finbert : ProsusAI/finbert transformer (finance-tuned)
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

FINBERT_MODEL_ID = "ProsusAI/finbert"
SUPPORTED_ENGINES = ("vader", "finbert")

_vader: SentimentIntensityAnalyzer | None = None
_finbert_bundle: tuple[object, object] | None = None


class SentimentEngine(Protocol):
    name: str

    def score_text(self, text: str) -> dict[str, float]: ...

    def score_batch(self, texts: list[str]) -> list[dict[str, float]]: ...


def label_from_compound(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def get_vader_analyzer() -> SentimentIntensityAnalyzer:
    global _vader
    if _vader is None:
        _vader = SentimentIntensityAnalyzer()
    return _vader


def score_text_vader(text: str) -> dict[str, float]:
    scores = get_vader_analyzer().polarity_scores(text or "")
    return {
        "neg": scores["neg"],
        "neu": scores["neu"],
        "pos": scores["pos"],
        "compound": scores["compound"],
    }


def _load_finbert() -> tuple[object, object]:
    global _finbert_bundle
    if _finbert_bundle is not None:
        return _finbert_bundle
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "FinBERT requires transformers and torch. Install with:\n"
            "  pip install transformers torch"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_ID)
    model.eval()
    _finbert_bundle = (tokenizer, model)
    return _finbert_bundle


def _finbert_probs(text: str) -> dict[str, float]:
    tokenizer, model = _load_finbert()
    import torch

    inputs = tokenizer(text or "", return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1).tolist()

    id2label = getattr(model.config, "id2label", None) or {
        0: "positive",
        1: "negative",
        2: "neutral",
    }
    label_probs = {str(id2label[i]).lower(): float(probs[i]) for i in range(len(probs))}
    pos = label_probs.get("positive", 0.0)
    neg = label_probs.get("negative", 0.0)
    neu = label_probs.get("neutral", 0.0)
    return {"pos": pos, "neg": neg, "neu": neu}


def score_text_finbert(text: str) -> dict[str, float]:
    probs = _finbert_probs(text)
    compound = probs["pos"] - probs["neg"]
    return {
        "neg": probs["neg"],
        "neu": probs["neu"],
        "pos": probs["pos"],
        "compound": compound,
    }


def score_batch_finbert(texts: list[str], *, batch_size: int = 16) -> list[dict[str, float]]:
    if not texts:
        return []

    tokenizer, model = _load_finbert()
    import torch

    id2label = getattr(model.config, "id2label", None) or {
        0: "positive",
        1: "negative",
        2: "neutral",
    }
    results: list[dict[str, float]] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        inputs = tokenizer(
            chunk,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)

        for row in probs.tolist():
            label_probs = {str(id2label[i]).lower(): float(row[i]) for i in range(len(row))}
            pos = label_probs.get("positive", 0.0)
            neg = label_probs.get("negative", 0.0)
            neu = label_probs.get("neutral", 0.0)
            results.append(
                {
                    "neg": neg,
                    "neu": neu,
                    "pos": pos,
                    "compound": pos - neg,
                }
            )
    return results


class VaderEngine:
    name = "vader"

    def score_text(self, text: str) -> dict[str, float]:
        return score_text_vader(text)

    def score_batch(self, texts: list[str]) -> list[dict[str, float]]:
        return [score_text_vader(t) for t in texts]


class FinBertEngine:
    name = "finbert"

    def score_text(self, text: str) -> dict[str, float]:
        return score_text_finbert(text)

    def score_batch(self, texts: list[str]) -> list[dict[str, float]]:
        return score_batch_finbert(texts)


def get_engine(name: str) -> SentimentEngine:
    key = (name or "vader").strip().lower()
    if key not in SUPPORTED_ENGINES:
        raise ValueError(f"Unknown engine {name!r}. Choose from: {', '.join(SUPPORTED_ENGINES)}")
    if key == "finbert":
        return FinBertEngine()
    return VaderEngine()


def predict_label(text: str, *, engine: str = "vader") -> str:
    compound = get_engine(engine).score_text(text)["compound"]
    return label_from_compound(compound)


def analyze_dataframe(df: pd.DataFrame, *, engine: str = "vader") -> pd.DataFrame:
    scorer = get_engine(engine)
    out = df.copy()
    text = (out.get("title", "").fillna("") + ". " + out.get("summary", "").fillna("")).str.strip()
    scored = scorer.score_batch(text.tolist())
    out["sentiment_neg"] = [s["neg"] for s in scored]
    out["sentiment_neu"] = [s["neu"] for s in scored]
    out["sentiment_pos"] = [s["pos"] for s in scored]
    out["sentiment_compound"] = [s["compound"] for s in scored]
    out["sentiment_label"] = out["sentiment_compound"].map(label_from_compound)
    out["sentiment_engine"] = engine
    return out


def write_engine_metadata(engine: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(engine.strip().lower() + "\n", encoding="utf-8")


def read_engine_metadata(path: Path, *, default: str = "vader") -> str:
    if not path.exists():
        return default
    line = path.read_text(encoding="utf-8").strip().lower()
    return line if line in SUPPORTED_ENGINES else default


# Backward-compatible aliases used by older imports/tests.
score_text = score_text_vader
