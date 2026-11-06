"""Word matching: the form you type should never matter."""
import pytest

from caviardage import text


def matches(guess, word, lang):
    return bool(text.keys(guess, lang) & text.keys(word, lang))


@pytest.mark.parametrize("guess,word", [
    ("est", "était"), ("est", "fut"), ("était", "est"), ("fut", "sera"), ("être", "est"), ("est", "être"),
    ("etait", "est"), ("etait", "était"), ("ete", "été"), ("été", "est"),
    ("a", "à"), ("à", "a"), ("a", "ont"), ("A", "à"),
    ("etat", "État"), ("ETAT", "état"),
    ("grand", "grandes"), ("primate", "primates"), ("pont", "ponts"), ("oeil", "yeux"), ("cheval", "chevaux"),
    ("suis", "suivre"), ("suis", "être"), ("de", "d"), ("le", "l"),
    ("de", "du"), ("du", "de"), ("de", "des"), ("des", "de"), ("le", "du"), ("du", "le"), ("le", "des"),
    ("le", "au"), ("au", "le"), ("le", "aux"), ("à", "au"), ("a", "au"), ("au", "à"), ("à", "aux"), ("aux", "à"),
    ("un", "des"), ("des", "un"), ("la", "du"),
])
def test_french_matches(guess, word):
    assert matches(guess, word, "fr")


@pytest.mark.parametrize("guess,word", [
    ("mer", "mère"), ("pont", "mer"), ("est", "pont"), ("mais", "mai"), ("pain", "pont"),
])
def test_french_stays_separate(guess, word):
    assert not matches(guess, word, "fr")


@pytest.mark.parametrize("guess,word", [
    ("is", "was"), ("was", "be"), ("mouse", "mice"), ("run", "ran"), ("tooth", "teeth"),
    ("primate", "primates"), ("lorises", "loris"), ("loris", "lorises"), ("cafe", "café"),
])
def test_english_matches(guess, word):
    assert matches(guess, word, "en")


@pytest.mark.parametrize("guess,word", [("monkey", "primate"), ("bridge", "river"), ("sea", "see")])
def test_english_stays_separate(guess, word):
    assert not matches(guess, word, "en")


@pytest.mark.parametrize("word,lemma,lang", [
    ("relativités", "relativité", "fr"), ("relativites", "relativité", "fr"), ("Relativités", "relativité", "fr"),
])
def test_plurals_missing_from_the_word_list_are_known(word, lemma, lang):
    assert text.is_real_word(word, lang)
    assert lemma in text.lemmas(word, lang)


@pytest.mark.parametrize("guess,word", [("relativités", "relativité"), ("relativité", "relativités"), ("relativites", "relativité")])
def test_those_plurals_match_their_singular(guess, word):
    assert matches(guess, word, "fr")


@pytest.mark.parametrize("word", ["zzzqxs", "qwertyx", "blorpes"])
def test_nonsense_with_a_plural_ending_is_still_unknown(word):
    assert not text.is_real_word(word, "fr")


def test_known_words_ending_in_s_keep_their_own_meaning():
    assert "mai" not in text.lemmas("mais", "fr")
    assert "pa" not in text.lemmas("pas", "fr")


def test_tokenize_keeps_text_intact():
    sample = "L'histoire du pont, en 1883 : c'est très-long."
    tokens = text.tokenize(sample)
    assert "".join(t["text"] for t in tokens) == sample
    assert [t["text"] for t in tokens if t["word"]][:3] == ["L", "histoire", "du"]
