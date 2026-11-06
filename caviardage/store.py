"""Read-only access to data/words.sqlite, so word data stays on disk instead of in memory."""
import functools
import sqlite3
import threading
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "words.sqlite"

_db = sqlite3.connect(f"{PATH.as_uri()}?mode=ro&immutable=1", uri=True, check_same_thread=False)
_db.execute("PRAGMA cache_size=-2000")  # At most 2 MB of cached pages.
_lock = threading.Lock()


def _one(sql, *args):
    with _lock:
        row = _db.execute(sql, args).fetchone()
    return row[0] if row else None


@functools.lru_cache(maxsize=4000)
def lemma(lang, word):
    return _one("SELECT lemma FROM lemma WHERE lang=? AND word=?", lang, word)


@functools.lru_cache(maxsize=4000)
def is_common(lang, word):
    return _one("SELECT 1 FROM common WHERE lang=? AND word=?", lang, word) is not None


@functools.lru_cache(maxsize=4000)
def vector_index(lang, word):
    return _one("SELECT idx FROM vec WHERE lang=? AND word=?", lang, word)


@functools.lru_cache(maxsize=2000)
def word_synsets(lang, word):
    found = _one("SELECT synsets FROM wn_word WHERE lang=? AND word=?", lang, word)
    return tuple(int(s) for s in found.split(",")) if found else ()


@functools.lru_cache(maxsize=2000)
def synset_ancestors(synset):
    """((ancestor, steps), ...) for every ancestor of a synset."""
    found = _one("SELECT up FROM wn_up WHERE synset=?", synset)
    if not found:
        return ()
    return tuple(tuple(int(n) for n in pair.split(":")) for pair in found.split(","))


@functools.lru_cache(maxsize=2000)
def group_size(synset):
    return _one("SELECT size FROM wn_size WHERE synset=?", synset) or 0


def pool_size(lang, level):
    return _one("SELECT size FROM pool_size WHERE lang=? AND level=?", lang, level) or 0


def pool_title(lang, level, n):
    return _one("SELECT title FROM pool WHERE lang=? AND level=? AND n=?", lang, level, n)
