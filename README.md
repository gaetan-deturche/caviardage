# Caviardage

Uncover a hidden Wikipedia page by guessing words, in French or English, as many times as you like.

## Setup

You need Python 3.12. The word vectors aren't in this repo because of their size, so the setup downloads a 633 MB file and filters it down to 89 MB. The file in `.cache` can be deleted afterwards.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
mkdir -p .cache/numberbatch
curl -L -o .cache/numberbatch/mini.h5 https://conceptnet.s3.amazonaws.com/precomputed-data/2016/numberbatch/19.08/mini.h5
.venv/Scripts/python scripts/build_vectors.py
```

## Run

```bash
.venv/Scripts/python app.py
```

Then open http://127.0.0.1:5180. The first start downloads a text model of about 220 MB and the WordNet data. It needs an internet connection to fetch each page.

## How guesses work

- **Matching (green):** accents, capitals and word forms don't matter. `est`, `était`, `fut` and `être` all reveal each other, and `a` matches `à`.
- **Direct link (orange):** a family link, such as monkey and primate, or a very strong association.
- **Same area (yellow):** the same broad category or setting, such as pangolin and primate, or roi and château.

A close guess is written in the slot it's close to. The hidden word itself stays hidden, and a closer guess replaces a weaker one. Clicking a bar shows its letter count.

## How closeness is scored

`caviardage/closeness.py` combines WordNet (what a word is), ConceptNet Numberbatch (related words) and a small multilingual text model that refines the score. Words Numberbatch doesn't know only ever match exactly. The thresholds are constants at the top of that file. Very common words such as `peut` and `alors` only ever match exactly.

## Rebuilding the data

- `scripts/build_pool.py` rebuilds `data/pool.json` from Wikipedia's Vital articles lists.
- `scripts/build_vectors.py` rebuilds the word vectors from Numberbatch `mini.h5`; its docstring has the download link.

## Tests

```bash
.venv/Scripts/python -m pytest tests
```

## Credits

Article text comes from Wikipedia (CC BY-SA). Word data: ConceptNet Numberbatch (CC BY-SA), Princeton WordNet and Open Multilingual Wordnet.
