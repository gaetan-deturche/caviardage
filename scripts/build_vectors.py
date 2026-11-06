"""Filter ConceptNet Numberbatch (mini.h5) to single French and English words.

Input:  .cache/numberbatch/mini.h5
        https://conceptnet.s3.amazonaws.com/precomputed-data/2016/numberbatch/19.08/mini.h5
Output: data/numberbatch.npy (int8 matrix) and data/numberbatch_vocab.json

The source file can be deleted once this has run.
"""
import json
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / ".cache" / "numberbatch" / "mini.h5"
OUT = ROOT / "data"
PREFIXES = {"/c/fr/": "fr", "/c/en/": "en"}


def main():
    OUT.mkdir(exist_ok=True)
    with h5py.File(SOURCE, "r") as f:
        names = f["mat/axis1"][:]
        rows, vocab = [], {"fr": {}, "en": {}}
        for i, raw in enumerate(names):
            uri = raw.decode("utf-8", "ignore")
            prefix = uri[:6]
            lang = PREFIXES.get(prefix)
            if not lang:
                continue
            word = uri[6:]
            if "_" in word or "#" in word or not word or len(word) > 30:
                continue
            vocab[lang][word] = len(rows)
            rows.append(i)
        matrix = f["mat/block0_values"][rows]
    np.save(OUT / "numberbatch.npy", matrix)
    (OUT / "numberbatch_vocab.json").write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in vocab.items()}, matrix.shape, f"{matrix.nbytes / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
