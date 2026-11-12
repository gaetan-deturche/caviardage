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

# Letters and numbers. Signs that only look like them stay visible: the micro sign, the
# degree-style º, and enclosed characters such as ① and Ⓐ.
WORD_RE = re.compile(r"[^\W_µº\u2460-\u24FF\u2776-\u2793\u3248-\u324F\u3251-\u325F\u3280-\u32BF]+", re.UNICODE)
FRACTION_SLASH = "\u2044"
WORD_BREAK = "\u200b"  # Invisible word edge, kept for rounds saved before the marks below.
# Invisible marks around superscripts and subscripts, as in XXe and CO2.
SUP_OPEN, SUP_CLOSE, SUB_OPEN, SUB_CLOSE = "\ue000", "\ue001", "\ue002", "\ue003"
MARKS_RE = re.compile("([\ue000-\ue003\u200b])")
SCRIPT_CHARACTERS_RE = re.compile(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻₀₁₂₃₄₅₆₇₈₉₊₋ᵉʳᵈˢᵗʰⁿ]+)")

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
    # NFKD also turns ² and ₂ into 2, ᵉ into e, and Ⅳ into iv.
    return "".join(c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn").casefold()


def _known(word, lang):
    """In either word list. Some words, like relativité, are only in the word vectors."""
    return store.lemma(lang, word) is not None or store.vector_index(lang, word) is not None


def _accent_variants(word, lang):
    """Known spellings of an unaccented French word: etait -> était."""
    if lang != "fr" or word != fold(word) or store.lemma(lang, word) is not None:
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
def _plural_lemma(word, lang):
    """The base form of a plural the word list lacks: relativités -> relativité."""
    if len(word) < 4 or _known(word, lang):
        return None
    for ending in ("s", "x", "es"):
        if word.endswith(ending):
            singular = word[: -len(ending)]
            if ending == "x" and not singular.endswith("u"):
                continue  # French -x plurals follow -u: bijoux, feux.
            for spelling in [singular] + _accent_variants(singular, lang):
                found = store.lemma(lang, spelling)
                if found:
                    return found
                if _known(spelling, lang):
                    return spelling
    return None


# -ant words whose -ait form belongs to an unrelated verb: avant is not a form of avoir.
NOT_PARTICIPLES = {"avant", "devant", "savant", "méchant", "garant", "surfant"}


def _participle_verb(word, lang):
    """The verb of a French present participle the word list files as an adjective: comptant -> compter.

    The verb is found through the -ait form of the same stem: comptait -> compter."""
    if lang != "fr" or not word.endswith("ant") or len(word) < 5 or word in NOT_PARTICIPLES:
        return None
    return store.lemma(lang, word[:-3] + "ait")


def _lemma(lang, word):
    """The word list's base form, followed to the end: parlées -> parlée -> parlé -> parler."""
    lemma = store.lemma(lang, word)
    for _ in range(3):
        further = lemma and store.lemma(lang, lemma)
        if not further or further == lemma:
            break
        lemma = further
    return lemma


def _unelide(lower, lang):
    """The full form of an elided French word: l -> le, lorsqu -> lorsque, jusqu -> jusque."""
    if lang != "fr":
        return lower
    if lower in ELISIONS:
        return ELISIONS[lower]
    if lower.endswith("qu") and len(lower) > 2:
        return lower + "e"
    return lower


def lemmas(word, lang):
    """Every base form a word could have, most likely first."""
    lower = word.lower()
    lower = _unelide(lower, lang)
    spellings = [lower] + _accent_variants(lower, lang)
    found = []
    for spelling in spellings:
        for lemma in AMBIGUOUS.get(lang, {}).get(spelling, []) + [_lemma(lang, spelling) or _plural_lemma(spelling, lang) or spelling]:
            if lemma not in found:
                found.append(lemma)
    return tuple(found)


@functools.lru_cache(maxsize=4000)
def related_forms(word, lang):
    """The base forms, plus the verb of an -ant word: comptant -> {comptant, compter}.

    Kept apart from lemmas, because many -ant words became words of their own:
    a volant is not a form of voler, so voler should only come close to it, not reveal it."""
    lower = word.lower()
    forms = set(lemmas(word, lang))
    for spelling in [lower] + _accent_variants(lower, lang):
        verb = _participle_verb(spelling, lang)
        if verb:
            forms.add(verb)
    return frozenset(forms)


# Feminine nouns the word list files apart from their masculine. Endings like -esse are not
# enough on their own: jeunesse, sagesse and vitesse are not feminines of jeune, sage and vite.
FEMININES = {
    "poétesse": "poète", "princesse": "prince", "comtesse": "comte", "vicomtesse": "vicomte", "duchesse": "duc",
    "archiduchesse": "archiduc", "hôtesse": "hôte", "maîtresse": "maître", "déesse": "dieu", "tigresse": "tigre",
    "ogresse": "ogre", "ânesse": "âne", "abbesse": "abbé", "chanoinesse": "chanoine", "diablesse": "diable",
    "prophétesse": "prophète", "druidesse": "druide", "traîtresse": "traître", "chasseresse": "chasseur",
    "pécheresse": "pécheur", "vengeresse": "vengeur", "enchanteresse": "enchanteur", "devineresse": "devin",
    "pauvresse": "pauvre", "mairesse": "maire", "papesse": "pape", "prêtresse": "prêtre", "ivrognesse": "ivrogne",
    "doctoresse": "docteur", "défenderesse": "défendeur", "demanderesse": "demandeur", "héroïne": "héros",
    "impératrice": "empereur", "ambassadrice": "ambassadeur", "épouse": "époux", "veuve": "veuf", "louve": "loup",
    "chatte": "chat", "amie": "ami", "copine": "copain", "compagne": "compagnon", "speakerine": "speaker",
}


NOT_FEMININES = {"matrice"}  # Not a woman mateur.


def _masculine(lower, lang):
    """The masculine of a French feminine noun: poétesse -> poète, actrice -> acteur, chanteuse -> chanteur."""
    if lang != "fr":
        return None
    for word in (lower, lower[:-1] if lower.endswith("s") else None):
        if not word:
            continue
        if word in FEMININES:
            return FEMININES[word]
        if word in NOT_FEMININES:
            return None
        for ending, masculine in (("trice", "teur"), ("euse", "eur")):
            if word.endswith(ending) and len(word) >= len(ending) + 2:
                base = word[: -len(ending)] + masculine
                if _known(base, lang):
                    return base
    return None


@functools.lru_cache(maxsize=4000)
def keys(word, lang):
    """The matching keys of a word."""
    lower = word.lower()
    out = {fold(lower)}
    if FRACTION_SLASH in fold(lower):
        out.update(fold(lower).split(FRACTION_SLASH))  # ½ matches 1 and 2.
    if _unelide(lower, lang) != lower:
        out.add(fold(_unelide(lower, lang)))
    out.update(fold(lemma) for lemma in lemmas(word, lang))
    masculine = _masculine(lower, lang)
    if masculine:
        out.add(fold(masculine))
        out.update(fold(lemma) for lemma in lemmas(masculine, lang))
    # Plurals the lemmatiser does not know: lorises -> loris.
    if len(lower) >= 4 and not _known(lower, lang):
        base = fold(lower)
        if base.endswith("es"):
            out.add(base[:-2])
        if base.endswith(("s", "x")):
            out.add(base[:-1])
    return frozenset(out)


def is_real_word(word, lang):
    lower = word.lower()
    return _known(lower, lang) or bool(_accent_variants(lower, lang)) or bool(_plural_lemma(lower, lang))


@functools.lru_cache(maxsize=4000)
def is_stopword(word, lang):
    """Words too common to be related to anything: peut, alors, celle. Real topics like guerre stay."""
    stops = STOPWORDS[lang]
    lower = word.lower()
    if lower in stops or len(lower) < 3 or any(lemma in stops for lemma in lemmas(word, lang)):
        return True
    return store.is_common(lang, lower)


ORDINAL = r"(?:er|re|ère|ème|eme|es|e|ᵉʳ|ʳᵉ|ᵉ|st|nd|rd|th)?"
DIGITS_RE = re.compile(r"(\d{1,15})" + ORDINAL)
ROMAN_WORD_RE = re.compile(r"([IVXLCDM]+)" + ORDINAL)
LOWER_ROMAN_RE = re.compile(r"([ivx]+)" + ORDINAL)
ROMAN_RE = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
# Numbers written as words are numbers of their own kind: two lights up four, but 4 does not.
# Left out: one, un and une are mostly pronouns and articles, neuf is also "new".
NUMBER_WORDS = {
    "en": dict(zip(
        "zero two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand "
        "million billion".split(),
        [0, *range(2, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000, 10**6, 10**9])),
    "fr": dict(zip(
        "zéro deux trois quatre cinq six sept huit dix onze douze treize quatorze quinze seize vingt trente "
        "quarante cinquante soixante septante huitante octante nonante cent mille million milliard".split(),
        [0, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 20, 30, 40, 50, 60, 70, 80, 80, 90, 100, 1000, 10**6, 10**9])),
}

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman(body, lang):
    if not ROMAN_RE.fullmatch(body):
        return None
    # Single letters and short acronyms are usually not numbers: English I, D', CD, MC.
    if (lang == "en" and body == "I") or (set(body) - set("IVX") and len(body) < 3):
        return None
    total = 0
    for letter, following in zip(body, body[1:] + "I"):
        value = ROMAN_VALUES[letter]
        total += -value if value < ROMAN_VALUES[following] else value
    return ("roman", total)


def number_value(word, lang, guess=False):
    """("digits", 1883) for 1883 or 1er, ("roman", 19) for XIXe, ("words", 10) for dix, None for vie.

    The kinds never match each other: X and dix are not close to 9 or 10.
    """
    word = unicodedata.normalize("NFKC", word)  # ² is the digit 2, and Ⅳ is the numeral IV.
    digits = DIGITS_RE.fullmatch(word)
    if digits:
        return ("digits", int(digits.group(1)))
    roman = ROMAN_WORD_RE.fullmatch(word)
    if roman:
        return _roman(roman.group(1), lang)
    lower = word.lower()
    words = NUMBER_WORDS.get(lang, {})
    if lower in words:
        return ("words", words[lower])
    if lower.endswith("s") and lower[:-1] in words and words[lower[:-1]] >= 20:
        return ("words", words[lower[:-1]])  # hundreds, quatre-vingts, millions
    if guess and store.lemma(lang, word.lower()) is None:
        lower = LOWER_ROMAN_RE.fullmatch(word.lower())
        if lower:
            return _roman(lower.group(1).upper(), lang)
    return None


def number_tier(a, b):
    """Tier and score of number a against number b, of the same kind. Numbers are always comparable."""
    distance, size = abs(a - b), max(abs(a), abs(b), 1)
    score = 1 - distance / size
    return ("family" if distance <= max(1, size * 0.01) else "scene"), score


LEAD_NAME_RE = re.compile(r"^([^.:;()]{2,70}?)\s*\(([^)]{1,200})\)")
LEADING_ARTICLES = {"le", "la", "les", "l", "un", "une", "des", "the", "a", "an"}
NAME_VERBS = {"est", "sont", "était", "étaient", "fut", "furent", "is", "are", "was", "were"}
MAX_NAME_WORDS = 4
TITLE_IN_PARENTHESES_WITHIN = 40


def other_name(title, first_paragraph, lang):
    """The name an article opens with when its title only follows in parentheses.

    "Les mollusques (Mollusca) sont..." gives ["mollusques"] for the title Mollusca.
    Returns the words of that name, or [] when the article doesn't open this way.
    """
    match = LEAD_NAME_RE.match(strip_marks(first_paragraph))
    if not match:
        return []
    position = fold(match.group(2)).find(fold(title))
    if position < 0 or position > TITLE_IN_PARENTHESES_WITHIN:
        return []
    words = [t["text"] for t in tokenize(match.group(1)) if t["word"]]
    while words and words[0].lower() in LEADING_ARTICLES:
        words.pop(0)
    if not words or len(words) > MAX_NAME_WORDS or fold(" ".join(words)) == fold(title):
        return []
    if any(word.lower() in NAME_VERBS for word in words):
        return []  # "Les mollusques sont un groupe (Mollusca)" is a sentence, not a name.
    if all(is_stopword(word, lang) for word in words):
        return []
    return words


NUMBER_THEN_ENDING_RE = re.compile(r"(\d{1,15}|[IVXLCDM]+)(er|re|ère|ème|eme|es|e|ᵉʳ|ʳᵉ|ᵉ|st|nd|rd|th)")


def split_ordinal(word):
    """(7, th) for 7th and (XIX, e) for XIXe, where the ending is really a superscript.

    Returns None for anything else: Les and Ces are words, not Roman numerals with an ending.
    """
    match = NUMBER_THEN_ENDING_RE.fullmatch(word)
    if not match:
        return None
    number = match.group(1)
    if not number.isdigit() and _roman(number, "fr") is None:
        return None
    return number, match.group(2)


def ordinal_ending(word):
    """The ending of a guessed number, in any case: th for 7TH, e for xixe."""
    match = re.fullmatch(r"(?:\d{1,15}|[ivxlcdm]+)(er|re|ère|ème|eme|es|e|ᵉʳ|ʳᵉ|ᵉ|st|nd|rd|th)", word.lower())
    return match.group(1) if match else None


FRACTION_RE = re.compile(r"(\d?)([¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞↉⅟])")


def strip_marks(text):
    return MARKS_RE.sub("", text)


def _plain_tokens(text, state):
    """Words and everything between them. state["script"] tracks superscripts and subscripts."""
    tokens = []

    def add(word, value, script):
        token = {"word": word, "text": value}
        if script:
            token["script"] = script
        tokens.append(token)

    def add_between(chunk):
        for piece in MARKS_RE.split(chunk):
            if piece in (SUP_OPEN, SUB_OPEN):
                state["script"] = "sup" if piece == SUP_OPEN else "sub"
            elif piece in (SUP_CLOSE, SUB_CLOSE):
                state["script"] = None
            elif piece and piece != WORD_BREAK:
                add(False, piece, state["script"])

    position = 0
    for match in WORD_RE.finditer(text):
        add_between(text[position:match.start()])
        for piece in SCRIPT_CHARACTERS_RE.split(match.group()):
            if piece:
                parts = split_ordinal(piece)
                if parts:
                    add(True, parts[0], state["script"])
                    add(True, parts[1], state["script"] or "sup")
                else:
                    add(True, piece, state["script"])
        position = match.end()
    add_between(text[position:])
    return tokens


def tokenize(text):
    """Split text into [{"word": bool, "text": str}], keeping everything else as is.

    A word in a superscript or subscript also has "script". The parts of a fraction such as ½
    have "fraction" set to the short form, and "group" to tell one fraction from the next.
    """
    tokens, state, position, group = [], {"script": None}, 0, 0
    for match in FRACTION_RE.finditer(text):
        before_end = match.start(2)
        tokens += _plain_tokens(text[position:before_end], state)
        written = unicodedata.normalize("NFKC", match.group(2)).replace(FRACTION_SLASH, "/")
        group += 1
        spaced = (" " + written) if match.group(1) else written
        for token in _plain_tokens(spaced, state):
            tokens.append({**token, "fraction": match.group(2), "group": group})
        position = match.end()
    tokens += _plain_tokens(text[position:], state)
    return tokens
