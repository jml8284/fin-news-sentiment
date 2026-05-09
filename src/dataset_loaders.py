"""
Load local benchmark finance sentiment datasets into normalized pandas DataFrames.

Normalized columns (where applicable):
  - text: model input string
  - label: positive | neutral | negative  (lowercase)
  - dataset: short source id for mixing / stratified splits
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DatasetPaths:
    phrasebank_all_agree: Path
    all_data: Path
    sentfin: Path


def default_paths(root: Path = PROJECT_ROOT) -> DatasetPaths:
    base = root / "data" / "datasets"
    phrase = _first_match(
        base / "financial_phrasebank_v1",
        "Sentences_AllAgree.txt",
    )
    return DatasetPaths(
        phrasebank_all_agree=phrase,
        all_data=base / "combined_financial_sentiment" / "all-data.csv",
        sentfin=base / "sentfin_v1_1" / "SEntFiN-v1.1.csv",
    )


def _first_match(folder: Path, filename: str) -> Path:
    hits = sorted(folder.rglob(filename))
    if not hits:
        raise FileNotFoundError(f"Could not find {filename} under {folder}")
    return hits[0]


def _norm_label(value: object) -> str:
    s = str(value).strip().lower()
    if s not in {"positive", "neutral", "negative"}:
        raise ValueError(f"Unexpected label: {value!r}")
    return s


def load_financial_phrasebank_all_agree(path: Path | None = None) -> pd.DataFrame:
    path = path or default_paths().phrasebank_all_agree
    text = path.read_text(encoding="utf-8", errors="replace")
    rows: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "@" not in line:
            continue
        sentence, label = line.rsplit("@", 1)
        rows.append(
            {
                "text": sentence.strip(),
                "label": _norm_label(label),
                "dataset": "financial_phrasebank_all_agree",
            }
        )
    return pd.DataFrame(rows)


def load_combined_two_column_csv(path: Path | None = None) -> pd.DataFrame:
    """Load CSV with columns: sentiment, sentence (no header row)."""
    path = path or default_paths().all_data
    df = pd.read_csv(
        path,
        header=None,
        names=["label", "text"],
        encoding="utf-8",
        engine="python",
        on_bad_lines="skip",
    )
    df["label"] = df["label"].map(_norm_label)
    df["text"] = df["text"].fillna("").astype(str).str.strip()
    df = df[df["text"].str.len() > 0].reset_index(drop=True)
    df["dataset"] = "combined_financial_sentiment"
    return df


def _majority_label(decisions: dict[str, str]) -> str:
    if not decisions:
        return "neutral"
    votes = [_norm_label(v) for v in decisions.values()]
    counts = Counter(votes)
    return counts.most_common(1)[0][0]


def load_sentfin_headlines(path: Path | None = None) -> pd.DataFrame:
    """
    SEntFiN-style CSV: headline-level text + JSON entity sentiment in Decisions.

    Adds `label` via majority vote over entities (simple whole-headline proxy).
    """
    path = path or default_paths().sentfin
    df = pd.read_csv(path, encoding="utf-8")
    if "Title" in df.columns:
        col_title = "Title"
    else:
        raise KeyError(f"Expected a Title column. Got: {list(df.columns)}")
    if "Decisions" in df.columns:
        col_dec = "Decisions"
    else:
        raise KeyError(f"Expected a Decisions column. Got: {list(df.columns)}")

    def parse_decisions(cell: object) -> dict[str, str]:
        if cell is None or (isinstance(cell, float) and pd.isna(cell)):
            return {}
        if isinstance(cell, dict):
            return {str(k): str(v) for k, v in cell.items()}
        s = str(cell).strip()
        if not s:
            return {}
        return json.loads(s)

    decisions = df[col_dec].map(parse_decisions)
    out = pd.DataFrame(
        {
            "text": df[col_title].fillna("").astype(str).str.strip(),
            "label": decisions.map(_majority_label),
            "dataset": "sentfin_v1_1",
            "entity_decisions": decisions.map(json.dumps),
        }
    )
    out = out[out["text"].str.len() > 0].reset_index(drop=True)
    return out


def concat_training_views(paths: DatasetPaths | None = None) -> pd.DataFrame:
    paths = paths or default_paths()
    frames: list[pd.DataFrame] = []
    if paths.phrasebank_all_agree.exists():
        frames.append(load_financial_phrasebank_all_agree(paths.phrasebank_all_agree))
    if paths.all_data.exists():
        frames.append(load_combined_two_column_csv(paths.all_data))
    if paths.sentfin.exists():
        sf = load_sentfin_headlines(paths.sentfin)
        frames.append(sf[["text", "label", "dataset"]])
    if not frames:
        raise FileNotFoundError("No dataset files found under data/datasets/")
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    paths = default_paths()
    print("Paths:")
    for k, v in paths.__dict__.items():
        print(f"  {k}: {v} exists={v.exists()}")

    if paths.phrasebank_all_agree.exists():
        df = load_financial_phrasebank_all_agree()
        print("\nFinancial PhraseBank (AllAgree):", df.shape)
        print(df.head(3))

    if paths.all_data.exists():
        df = load_combined_two_column_csv()
        print("\nCombined two-column CSV:", df.shape)
        print(df.head(3))

    if paths.sentfin.exists():
        df = load_sentfin_headlines()
        print("\nSEntFiN (headline majority label):", df.shape)
        print(df[["text", "label"]].head(3))


if __name__ == "__main__":
    main()
