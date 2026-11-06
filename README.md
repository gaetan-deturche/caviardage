# Caviardage

Uncover a hidden Wikipedia page by guessing words, in French or English, as many times as you like.

## Setup

The game needs Python 3.9 or later and uses about 60 MB of memory, so it can run on a Raspberry Pi. The word vectors aren't in this repo because of their size, so setup downloads a 633 MB file and filters it down to 89 MB. Do this on any computer, then copy `data/numberbatch.npy` to where the game runs.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-build.txt
mkdir -p .cache/numberbatch
curl -L -o .cache/numberbatch/mini.h5 https://conceptnet.s3.amazonaws.com/precomputed-data/2016/numberbatch/19.08/mini.h5
.venv/Scripts/python scripts/build_vectors.py
```

## Run

```bash
.venv/Scripts/python app.py
```

Then open http://127.0.0.1:5180. It needs an internet connection to fetch each page.

## How guesses work

- **Matching (green):** accents, capitals and word forms don't matter. `est`, `était`, `fut` and `être` all reveal each other, and `a` matches `à`.
- **Direct link (orange):** a family link, such as monkey and primate, or a very strong association.
- **Same area (yellow):** the same broad category or setting, such as pangolin and primate, or roi and château.

A close guess is written in the slot it's close to. The hidden word itself stays hidden, and a closer guess replaces a weaker one. Clicking a bar shows its letter count.

## How closeness is scored

`caviardage/closeness.py` combines WordNet (what a word is) and ConceptNet Numberbatch (related words). The thresholds are constants at the top of that file. Very common words such as `peut` and `alors`, and words Numberbatch doesn't know, only ever match exactly.

## Rebuilding the data

The game reads its word data and page lists from `data/words.sqlite`. After changing any source data, run `scripts/build_store.py`, which needs `requirements-build.txt`.

- `scripts/build_pool.py` rebuilds the first two levels of `data/pool.json` from Wikipedia's Vital articles lists.
- `scripts/build_deep_pool.py` adds the 100,000-page level, ranked by Wikimedia's monthly clickstream data. It's a popularity ranking and isn't curated, so it can include news, celebrity and adult subjects.
- `scripts/build_vectors.py` rebuilds the word vectors from Numberbatch `mini.h5`; its docstring has the download link.

## Tests

```bash
.venv/Scripts/python -m pytest tests
```

## Credits

Article text comes from Wikipedia (CC BY-SA). Word data: ConceptNet Numberbatch (CC BY-SA), Princeton WordNet and Open Multilingual Wordnet.
