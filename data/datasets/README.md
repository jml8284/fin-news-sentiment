# Benchmark datasets (local copies)

These files live under `data/datasets/` so the project root stays tidy and GitHub paths stay predictable.

| Folder | Contents | Typical use |
|--------|-----------|-------------|
| `financial_phrasebank_v1/` | Financial PhraseBank v1.0 (`README.txt`, `License.txt`, `Sentences_*.txt`) | Sentence-level **positive / neutral / negative** labels (strong majority agreement in `Sentences_AllAgree.txt`). |
| `combined_financial_sentiment/` | `all-data.csv` | Two-column CSV (**label**, **sentence**) — good for quick baseline training / evaluation. |
| `sentfin_v1_1/` | `SEntFiN-v1.1.csv` | Headlines + JSON **entity → sentiment** in `Decisions` — useful for entity-linked sentiment or richer modeling. |

## Loading in Python

Use `src/dataset_loaders.py` for shared parsing logic, for example:

```python
from pathlib import Path
import pandas as pd
from src.dataset_loaders import (
    default_paths,
    load_financial_phrasebank_all_agree,
    load_combined_two_column_csv,
    load_sentfin_headlines,
)

paths = default_paths(Path(__file__).resolve().parent.parent)
dfb = load_financial_phrasebank_all_agree(paths.phrasebank_all_agree)
dfc = load_combined_two_column_csv(paths.all_data)
dfs = load_sentfin_headlines(paths.sentfin)
```

## License & citation

- Keep **`License.txt` / `README.txt`** from each publisher in place.
- Course reports should cite the original papers and dataset terms (especially if use is beyond coursework).
