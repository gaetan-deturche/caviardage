"""Numbers compare by value, only within their own kind, and words stay words."""
import pytest

from caviardage import text
from caviardage.game import Game


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


@pytest.mark.parametrize("word,kind,value", [
    ("1883", "digits", 1883), ("0", "digits", 0), ("1er", "digits", 1), ("2e", "digits", 2), ("3ème", "digits", 3),
    ("IV", "roman", 4), ("IX", "roman", 9), ("XIXe", "roman", 19), ("XXe", "roman", 20),
    ("Ier", "roman", 1), ("XIV", "roman", 14), ("MCMXC", "roman", 1990), ("XLV", "roman", 45),
])
def test_article_numbers(word, kind, value):
    assert text.number_value(word, "fr") == (kind, value)


@pytest.mark.parametrize("word", [
    "dix", "vie", "Vie", "pont", "De", "Le", "Me", "Ce", "D", "L", "M", "C", "CD", "DC", "MC", "CM", "XL", "IIII", "VX", "IC", "mix",
])
def test_not_numbers_in_articles(word):
    assert text.number_value(word, "fr") is None


def test_english_i_is_a_word():
    assert text.number_value("I", "en") is None
    assert text.number_value("I", "fr") == ("roman", 1)


@pytest.mark.parametrize("word,kind,value", [
    ("xix", "roman", 19), ("xixe", "roman", 19), ("Xix", "roman", 19), ("iv", "roman", 4),
    ("xx", "roman", 20), ("XX", "roman", 20), ("20", "digits", 20),
])
def test_guesses(word, kind, value):
    assert text.number_value(word, "fr", guess=True) == (kind, value)


@pytest.mark.parametrize("word", ["vie", "dix", "mi", "ci", "di", "pont"])
def test_words_stay_words_in_guesses(word):
    assert text.number_value(word, "fr", guess=True) is None


@pytest.mark.parametrize("a,b,tier", [
    (1880, 1883, "family"), (1870, 1883, "family"), (1800, 1883, "scene"), (1500, 1883, None),
    (19, 20, "family"), (18, 20, "scene"), (15, 20, None), (5, 6, "family"), (5, 7, "scene"), (1, 1000, None),
])
def test_tiers(a, b, tier):
    assert text.number_tier(a, b)[0] == tier


def test_closer_scores_higher():
    assert text.number_tier(1882, 1883)[1] > text.number_tier(1880, 1883)[1] > text.number_tier(1800, 1883)[1]
    assert 0 < text.number_tier(1800, 1883)[1] < 1


ARTICLE = {
    "title": "Pont",
    "paragraphs": ["Ouvert en 1883, au XIXe siècle, avec X arches et 9 piles. D'autres dix ponts, Louis XIV."],
    "url": "x",
}


def game():
    return Game(ARTICLE, "fr", NoCloseness())


def slots(state, near):
    return [t for t in state["tokens"] if t.get("near") == near]


def shown(state):
    return {t["text"] for t in state["tokens"] if t.get("revealed")}


def test_roman_and_digits_never_match_each_other():
    assert "XIXe" not in shown(game().guess("19")["state"])
    assert "1883" not in shown(game().guess("MDCCCLXXXIII")["state"])
    # 10 is one away from the digit 9 only, and never touches the Roman X.
    state = game().guess("10")["state"]
    assert len(slots(state, "10")) == 1 and "X" not in shown(state)
    # IX is next to the Roman X only, and never touches the digit 9.
    state = game().guess("IX")["state"]
    assert len(slots(state, "IX")) == 1 and "9" not in shown(state)


def test_same_kind_reveals_every_form():
    assert "XIX" in shown(game().guess("xix")["state"])
    assert "XIX" in shown(game().guess("XIXe")["state"])
    assert "1883" in shown(game().guess("1883")["state"])


def test_closest_number_stays_in_slot():
    g = game()
    assert slots(g.guess("1800")["state"], "1800")[0]["tier"] == "scene"
    state = g.guess("1880")["state"]
    assert slots(state, "1880")[0]["tier"] == "family" and not slots(state, "1800")
    state = g.guess("1881")["state"]
    assert slots(state, "1881") and not slots(state, "1880")
    state = g.guess("1700")["state"]
    assert slots(state, "1881") and not slots(state, "1700")


def test_number_stays_hidden_while_close():
    assert "1883" not in str(game().guess("1880")["state"])


def test_elided_letter_before_an_apostrophe_is_not_a_number():
    article = {"title": "Pont", "paragraphs": ["V'la un pont. Le roi V arrive."], "url": "x"}
    g = Game(article, "fr", NoCloseness())
    assert [t["number"] for t in g.words if t["text"] == "V"] == [None, ("roman", 5)]


def test_words_are_not_treated_as_numbers():
    result = game().guess("dix")
    assert result["hits"] == 1 and result["near"] == 0


def test_any_number_is_a_valid_guess():
    result = game().guess("987654")
    assert "error" not in result and result["hits"] == 0
