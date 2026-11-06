"""Ordinal endings are superscripts on Wikipedia, so they are words of their own."""
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


@pytest.mark.parametrize("sample,expected", [
    ("7th century", ["7", "th", "century"]),
    ("1st and 2nd, 3rd", ["1", "st", "and", "2", "nd", "3", "rd"]),
    ("XIXe siècle", ["XIX", "e", "siècle"]),
    ("François Ier", ["François", "I", "er"]),
    ("1re et 2e et 3ème", ["1", "re", "et", "2", "e", "et", "3", "ème"]),
    ("XXᵉ", ["XX", "ᵉ"]),
])
def test_endings_are_separate_words(sample, expected):
    assert words(sample) == expected


@pytest.mark.parametrize("word", [
    "Les", "Des", "Ces", "Mes", "Le", "De", "Ce", "Me", "Vie", "Xavier", "Cette", "Dès", "Mère",
    "1883", "XIX", "Ire2", "the", "CDe", "IIIIe",
])
def test_other_words_stay_whole(word):
    assert words(word) == [word]


def test_text_is_kept_intact_after_splitting():
    sample = "Au XIXe siècle, le 7th et 1er."
    assert "".join(t["text"] for t in text.tokenize(sample)) == sample


ARTICLE = {"title": "Pont", "paragraphs": ["In the 7th and 9th century, the XIXe and XXe, and the 1er."], "url": "x"}


def game():
    return Game(ARTICLE, "en", NoCloseness())


def shown(state):
    return [t["text"] for t in state["tokens"] if t.get("revealed")]


def test_guessing_the_ending_reveals_every_ending_only():
    result = game().guess("th")
    assert shown(result["state"]).count("th") == 2 and "7" not in shown(result["state"])


def test_guessing_the_number_leaves_the_ending_hidden():
    state = game().guess("7")["state"]
    assert "7" in shown(state) and "th" not in shown(state)


def test_guessing_number_and_ending_reveals_both():
    state = game().guess("7th")["state"]
    assert "7" in shown(state) and "th" in shown(state)
    state = game().guess("xixe")["state"]
    assert "XIX" in shown(state) and "e" in shown(state)


@pytest.mark.parametrize("word,ending", [("7th", "th"), ("7TH", "th"), ("xixe", "e"), ("XIXe", "e"), ("Ier", "er")])
def test_ordinal_ending_in_any_case(word, ending):
    assert text.ordinal_ending(word) == ending


def test_neighbouring_number_is_still_close():
    state = game().guess("8")["state"]
    assert [t for t in state["tokens"] if t.get("near") == "8"]


def test_digits_and_roman_stay_apart_after_splitting():
    state = game().guess("19")["state"]
    assert "XIX" not in shown(state)
