"""Build data/words.sqlite, so the game can read its word data from disk.

Everything the game looks up lives in this one file, which keeps its memory use
low enough for a Raspberry Pi. It needs requirements-build.txt, data/pool.json
and data/numberbatch_vocab.json. The game itself needs none of them.
"""
import json
import sqlite3
from pathlib import Path

import nltk
from simplemma.strategies.dictionaries.dictionary_factory import _load_dictionary_from_disk
from wordfreq import iter_wordlist, zipf_frequency

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "words.sqlite"
COMMON_ZIPF = 5.7  # About 500 uses per million words. These never count as "close".
WORDNET_LANG = {"fr": "fra", "en": "eng"}
MAX_SENSES = 6


def add_lemmas(db):
    for lang in ("fr", "en"):
        table = _load_dictionary_from_disk(lang)
        rows = {}
        for form, lemma in table.items():
            form, lemma = form.decode().lower(), lemma.decode().lower()
            rows.setdefault(form, lemma)
            rows.setdefault(lemma, lemma)
        db.executemany("INSERT INTO lemma VALUES (?,?,?)", ((lang, w, l) for w, l in rows.items()))
        print(lang, "lemmas", len(rows), flush=True)


def add_common(db):
    for lang in ("fr", "en"):
        count = 0
        for word in iter_wordlist(lang):
            if zipf_frequency(word, lang) < COMMON_ZIPF:
                break
            db.execute("INSERT OR IGNORE INTO common VALUES (?,?)", (lang, word.lower()))
            count += 1
        print(lang, "common", count, flush=True)


def add_vectors(db):
    vocab = json.loads((ROOT / "data" / "numberbatch_vocab.json").read_text(encoding="utf-8"))
    for lang, words in vocab.items():
        db.executemany("INSERT INTO vec VALUES (?,?,?)", ((lang, w, i) for w, i in words.items()))
        print(lang, "vectors", len(words), flush=True)


def add_wordnet(db):
    nltk.data.path.insert(0, str(ROOT / ".cache" / "nltk"))
    from nltk.corpus import wordnet as wn

    ids = {}

    def synset_id(synset):
        return ids.setdefault(synset.name(), len(ids))

    needed = {}
    for lang, code in WORDNET_LANG.items():
        rows = []
        for word in wn.all_lemma_names(lang=code):
            if "_" in word or " " in word:
                continue
            synsets = wn.synsets(word, lang=code)
            nouns = [s for s in synsets if s.pos() == "n"]
            chosen = (nouns or synsets)[:MAX_SENSES]
            if chosen:
                for synset in chosen:
                    needed[synset.name()] = synset
                rows.append((lang, word.lower(), ",".join(str(synset_id(s)) for s in chosen)))
        db.executemany("INSERT OR IGNORE INTO wn_word VALUES (?,?,?)", rows)
        print(lang, "wordnet words", len(rows), flush=True)

    sizes = {}
    for name, synset in needed.items():
        best = {}
        for ancestor, steps in synset.hypernym_distances():
            key = synset_id(ancestor)
            if steps < best.get(key, 999):
                best[key] = steps
                if key not in sizes:
                    sizes[key] = sum(1 for _ in ancestor.closure(lambda s: s.hyponyms()))
        db.execute("INSERT INTO wn_up VALUES (?,?)", (ids[name], ",".join(f"{a}:{s}" for a, s in best.items())))
    db.executemany("INSERT INTO wn_size VALUES (?,?)", sizes.items())
    print("synsets", len(needed), "groups", len(sizes), flush=True)


def add_pool(db):
    pool = json.loads((ROOT / "data" / "pool.json").read_text(encoding="utf-8"))
    for lang, levels in pool.items():
        for level, titles in levels.items():
            db.executemany("INSERT INTO pool VALUES (?,?,?,?)", ((lang, level, n, t) for n, t in enumerate(titles)))
            db.execute("INSERT INTO pool_size VALUES (?,?,?)", (lang, level, len(titles)))


def main():
    OUT.unlink(missing_ok=True)
    db = sqlite3.connect(OUT)
    db.executescript("""
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE lemma(lang TEXT, word TEXT, lemma TEXT, PRIMARY KEY(lang, word)) WITHOUT ROWID;
        CREATE TABLE common(lang TEXT, word TEXT, PRIMARY KEY(lang, word)) WITHOUT ROWID;
        CREATE TABLE vec(lang TEXT, word TEXT, idx INTEGER, PRIMARY KEY(lang, word)) WITHOUT ROWID;
        CREATE TABLE wn_word(lang TEXT, word TEXT, synsets TEXT, PRIMARY KEY(lang, word)) WITHOUT ROWID;
        CREATE TABLE wn_up(synset INTEGER PRIMARY KEY, up TEXT);
        CREATE TABLE wn_size(synset INTEGER PRIMARY KEY, size INTEGER);
        CREATE TABLE pool(lang TEXT, level TEXT, n INTEGER, title TEXT, PRIMARY KEY(lang, level, n)) WITHOUT ROWID;
        CREATE TABLE pool_size(lang TEXT, level TEXT, size INTEGER, PRIMARY KEY(lang, level)) WITHOUT ROWID;
    """)
    add_lemmas(db)
    add_common(db)
    add_vectors(db)
    add_wordnet(db)
    add_pool(db)
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"{OUT.name}: {OUT.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
