"""Symbols are always visible, and special letters and numbers count as what they stand for."""
import pytest

from caviardage import text
from caviardage.game import Game


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


def words(sample):
    return [t["text"] for t in text.tokenize(sample) if t["word"]]


def matches(guess, word):
    return bool(text.keys(guess, "fr") & text.keys(word, "fr"))


@pytest.mark.parametrize("char", list("µº°①②⑳⓪Ⓐ❶㉑㊿%&+=€©™→") + [".", ",", "(", "-", "_"])
def test_symbols_are_never_hidden(char):
    assert words(char) == []


@pytest.mark.parametrize("sample,expected", [
    ("5 µm", ["5", "m"]), ("n° 5", ["n", "5"]), ("nº 5", ["n", "5"]), ("① Paris", ["Paris"]), ("20 °C", ["20", "C"]),
])
def test_words_around_symbols(sample, expected):
    assert words(sample) == expected


@pytest.mark.parametrize("char", list("²³¹₂₃ªⅣⅧ"))
def test_special_letters_and_numbers_stay_hidden(char):
    assert words(char) == [char]


@pytest.mark.parametrize("guess,word", [
    ("2", "²"), ("²", "2"), ("2", "₂"), ("₂", "²"), ("3", "³"), ("1", "¹"), ("3", "₃"),
    ("1", "½"), ("2", "½"), ("½", "½"), ("1", "¼"), ("4", "¼"), ("½", "1"), ("a", "ª"), ("IV", "Ⅳ"), ("iv", "Ⅳ"), ("Ⅳ", "IV"),
    ("VIII", "Ⅷ"), ("e", "ᵉ"), ("er", "ᵉʳ"),
])
def test_they_match_what_they_stand_for(guess, word):
    assert matches(guess, word)


@pytest.mark.parametrize("guess,word", [("3", "²"), ("3", "½"), ("V", "Ⅳ"), ("5", "⁴")])
def test_they_do_not_match_anything_else(guess, word):
    assert not matches(guess, word)


@pytest.mark.parametrize("word,kind,value", [
    ("²", "digits", 2), ("₂", "digits", 2), ("³", "digits", 3), ("Ⅳ", "roman", 4), ("Ⅷ", "roman", 8),
])
def test_they_count_as_numbers_of_the_right_kind(word, kind, value):
    assert text.number_value(word, "fr") == (kind, value)


@pytest.mark.parametrize("sample,expected", [
    ("½", "1/2"), ("¼ de", "1/4 de"), ("¾", "3/4"), ("⅔", "2/3"), ("⅛", "1/8"), ("3½ litres", "3 1/2 litres"), ("x½", "x1/2"),
])
def test_fractions_read_as_written_out(sample, expected):
    assert "".join(t["text"] for t in text.tokenize(sample)) == expected


@pytest.mark.parametrize("sample,expected", [("½", ["1", "2"]), ("¼", ["1", "4"]), ("3½", ["3", "1", "2"])])
def test_fraction_numbers_are_hidden_words_and_the_slash_is_visible(sample, expected):
    tokens = text.tokenize(sample)
    assert [t["text"] for t in tokens if t["word"]] == expected
    assert "/" in [t["text"] for t in tokens if not t["word"]]


def test_accents_and_case_still_match():
    assert text.fold("Été") == "ete" and text.fold("ŒUVRE") == "oeuvre"


ARTICLE = {"title": "Pont", "paragraphs": ["Une aire de 10 m² et Louis Ⅳ, soit ½ part, à 5 µm : ① ici."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", NoCloseness())


def shown(state):
    return [t["text"] for t in state["tokens"] if t.get("revealed")]


def test_guessing_two_reveals_the_square():
    assert "²" in shown(game().guess("2")["state"])


def test_guessing_iv_reveals_the_numeral_and_not_digits():
    state = game().guess("IV")["state"]
    assert "Ⅳ" in shown(state) and "4" not in shown(state)


def test_close_number_reaches_the_square():
    state = game().guess("3")["state"]
    assert [t for t in state["tokens"] if t.get("near") == "3" and t.get("length") == 1]


def test_fraction_parts_are_found_separately_and_get_closeness():
    g = game()
    state = g.guess("1")["state"]
    assert "2" not in shown(state) and "1" in shown(state)
    assert [t for t in state["tokens"] if t.get("near") == "1"]
    assert "½" in shown(g.guess("2")["state"])


def test_typing_the_fraction_itself_finds_it():
    assert "½" in shown(game().guess("½")["state"])


def test_symbols_are_visible_from_the_start():
    tokens = game().state()["tokens"]
    visible = "".join(t["text"] for t in tokens if not t.get("word"))
    assert "µ" in visible and "①" in visible
