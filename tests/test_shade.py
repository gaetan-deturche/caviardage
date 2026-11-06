"""The closer the guess, the whiter its text, and the message counts every match."""
import pytest

from caviardage.game import Game, _shade, _word_shade


class Scores:
    SCORES = {
        ("loin", "primate"): ("scene", 0.21), ("mieux", "primate"): ("scene", 0.38),
        ("direct", "primate"): ("family", 0.45), ("tres", "primate"): ("family", 0.85),
        ("faible", "primate"): ("family", 0.12), ("mieux", "marbre"): ("scene", 0.3),
    }

    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return self.SCORES.get((a, b), (None, 0.0))


ARTICLE = {"title": "Pont", "paragraphs": ["Le primate marbre, un primate, en 1883 et 1900."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", Scores())


def slots(state, word):
    return [t for t in state["tokens"] if t.get("near") == word]


def test_shade_stays_in_range_and_family_is_always_closer():
    assert _shade("scene", 0) == 0.12 and _shade("scene", 1) == 0.55 and _shade("family", 0) == 0.55 and _shade("family", 1) == 1
    assert _shade("scene", 5) == 0.55 and _shade("family", -3) == 0.55
    assert _word_shade("family", 0.12) >= _word_shade("scene", 0.39)


def test_closer_word_is_whiter():
    g = game()
    far = slots(g.guess("loin")["state"], "loin")[0]["shade"]
    near = slots(g.guess("mieux")["state"], "mieux")[0]["shade"]
    direct = slots(g.guess("direct")["state"], "direct")[0]["shade"]
    best = slots(g.guess("tres")["state"], "tres")[0]["shade"]
    assert far < near < direct < best == 1


def test_closer_number_is_whiter():
    g = game()
    far = [t for t in g.guess("1700")["state"]["tokens"] if t.get("near") == "1700"][0]["shade"]
    near = [t for t in g.guess("1880")["state"]["tokens"] if t.get("near") == "1880"][0]["shade"]
    assert far < near


def test_message_counts_every_match_and_only_real_improvements():
    g = game()
    first = g.guess("direct")
    assert first["matches"] == 2 and first["near"] == 2
    weaker = g.guess("loin")
    assert weaker["matches"] == 2 and weaker["near"] == 0
    better = g.guess("mieux")
    assert better["matches"] == 3 and better["near"] == 1


def test_shade_does_not_leak_the_hidden_word():
    state = str(game().guess("direct")["state"])
    assert "primate" not in state and "shade" in state
