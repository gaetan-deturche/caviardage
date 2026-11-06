"""Tokenising and word matching.

A guess matches an article word when they share a "key". Keys ignore accents
and capitals, and include the word's base form, so est, était and être all
match each other, and a matches à.
"""
import functools
import itertools
import re
import unicodedata

from . import store

WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

# French elided forms keep their full word's identity: guessing "de" reveals d'.
ELISIONS = {"l": "le", "d": "de", "j": "je", "n": "ne", "s": "se", "c": "ce", "m": "me", "t": "te", "qu": "que"}

# Forms that belong to two common base forms. The lemmatiser only returns one.
AMBIGUOUS = {
    "fr": {
        "suis": ["être", "suivre"],
        "es": ["être"],
        "fut": ["être"],
        "as": ["avoir"],
        "sont": ["être"],
        "vis": ["vivre", "voir"],
        "vit": ["vivre", "voir"],
        "été": ["être", "été"],
        # Contractions match both of their parts: du is de + le.
        "du": ["de", "le"],
        "des": ["de", "le", "un"],
        "au": ["à", "le"],
        "aux": ["à", "le"],
    },
    "en": {"saw": ["see", "saw"], "left": ["leave", "left"], "found": ["find", "found"]},
}

MAX_ACCENT_SLOTS = 10  # Keeps a long unknown guess from trying thousands of spellings.
ACCENTS = {"e": "éèê", "a": "àâ", "u": "ùû", "i": "îï", "o": "ô", "c": "ç"}

STOPWORDS = {
    "fr": set(
        "le la les l un une des du de d et ou mais donc or ni car à au aux en dans par pour sur sous avec sans chez vers entre "
        "ce cet cette ces se sa son ses mon ma mes ton ta tes notre votre leur leurs je tu il elle on nous vous ils elles lui eux y "
        "qui que quoi dont où ne pas plus moins très aussi comme si être avoir faire est sont était a ont été fut "
        "quel quelle quels quelles tout toute tous toutes c qu s n m t j".split()
    ),
    "en": set(
        "the a an and or but nor so of to in on at by for from with without as into over under about between "
        "this that these those it its he she they we you i him her them his their our your my who whom which what when where why how "
        "not no be is are was were been being am have has had do does did will would can could may might shall should must "
        "there here than then very also if s t".split()
    ),
}


def fold(word):
    """Lowercase and remove accents: Été -> ete."""
    text = word.casefold().replace("œ", "oe").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _known(word, lang):
    return store.lemma(lang, word) is not None


def _accent_variants(word, lang):
    """Known spellings of an unaccented French word: etait -> était."""
    if lang != "fr" or word != fold(word) or _known(word, lang):
        return []
    slots = [i for i, c in enumerate(word) if c in ACCENTS]
    if len(slots) > MAX_ACCENT_SLOTS:
        return []
    found = []
    for count in (1, 2, 3):
        for places in itertools.combinations(slots, count):
            for letters in itertools.product(*(ACCENTS[word[i]] for i in places)):
                chars = list(word)
                for i, letter in zip(places, letters):
                    chars[i] = letter
                candidate = "".join(chars)
                if _known(candidate, lang):
                    found.append(candidate)
        if found:
            return found
    return found


@functools.lru_cache(maxsize=4000)
def lemmas(word, lang):
    """Every base form a word could have, most likely first."""
    lower = word.lower()
    lower = ELISIONS.get(lower, lower) if lang == "fr" else lower
    spellings = [lower] + _accent_variants(lower, lang)
    found = []
    for spelling in spellings:
        for lemma in AMBIGUOUS.get(lang, {}).get(spelling, []) + [store.lemma(lang, spelling) or spelling]:
            if lemma not in found:
                found.append(lemma)
    return tuple(found)


@functools.lru_cache(maxsize=4000)
def keys(word, lang):
    """The matching keys of a word."""
    lower = word.lower()
    out = {fold(lower)}
    if lang == "fr" and lower in ELISIONS:
        out.add(fold(ELISIONS[lower]))
    out.update(fold(lemma) for lemma in lemmas(word, lang))
    # Plurals the lemmatiser does not know: lorises -> loris.
    if len(lower) >= 4 and not _known(lower, lang):
        base = fold(lower)
        if base.endswith("es"):
            out.add(base[:-2])
        if base.endswith(("s", "x")):
            out.add(base[:-1])
    return frozenset(out)


def is_real_word(word, lang):
    return _known(word.lower(), lang) or bool(_accent_variants(word.lower(), lang))


@functools.lru_cache(maxsize=4000)
def is_stopword(word, lang):
    """Words too common to be related to anything: peut, alors, celle. Real topics like guerre stay."""
    stops = STOPWORDS[lang]
    lower = word.lower()
    if lower in stops or len(lower) < 3 or any(lemma in stops for lemma in lemmas(word, lang)):
        return True
    return store.is_common(lang, lower)


def tokenize(text):
    """Split text into [{"word": bool, "text": str}], keeping everything else as is."""
    tokens, position = [], 0
    for match in WORD_RE.finditer(text):
        if match.start() > position:
            tokens.append({"word": False, "text": text[position:match.start()]})
        tokens.append({"word": True, "text": match.group()})
        position = match.end()
    if position < len(text):
        tokens.append({"word": False, "text": text[position:]})
    return tokens
