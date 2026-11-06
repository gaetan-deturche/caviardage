"""A page whose title is a scientific name can be solved with the name it opens with."""
import pytest

from caviardage import text
from caviardage.game import Game


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


@pytest.mark.parametrize("title,paragraph,lang,expected", [
    ("Mollusca", "Les mollusques (Mollusca) sont un embranchement.", "fr", ["mollusques"]),
    ("Canis lupus", "Le loup gris (Canis lupus) est un mammifère.", "fr", ["loup", "gris"]),
    ("Quercus", "Oaks (from Latin, genus Quercus) are trees.", "en", ["Oaks"]),
    ("Felis catus", "The domestic cat (Felis catus) is small.", "en", ["domestic", "cat"]),
])
def test_finds_the_other_name(title, paragraph, lang, expected):
    assert text.other_name(title, paragraph, lang) == expected


@pytest.mark.parametrize("title,paragraph,lang", [
    ("Sigmund Freud", "Sigmund Freud (né Sigismund Schlomo Freud), le 6 mai 1856, est un neurologue.", "fr"),
    ("Pont de Brooklyn", "Le pont de Brooklyn (en anglais Brooklyn Bridge), est l'un des plus anciens.", "fr"),
    ("Paris", "Paris (prononcé ici) est la capitale de la France.", "fr"),
    ("Eau", "L'eau (H2O) est un corps.", "fr"),
    ("Mollusca", "Les mollusques sont un embranchement (Mollusca).", "fr"),
    ("Mollusca", "Ce groupe est vaste. Les mollusques (Mollusca) sont connus.", "fr"),
    ("Mollusca", "", "fr"),
    ("Loup", "Le loup (Loup) est un animal.", "fr"),
    ("Sigle", "Le (Sigle) est court.", "fr"),
    ("Mollusca", "Un très long nom de groupe vraiment trop long (Mollusca) est ici.", "fr"),
])
def test_ignores_everything_else(title, paragraph, lang):
    assert text.other_name(title, paragraph, lang) == []


ARTICLE = {"title": "Canis lupus", "paragraphs": ["Le loup gris (Canis lupus) est un mammifère. Le loup chasse."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", NoCloseness())


def test_one_word_of_the_name_is_not_enough():
    g = game()
    assert not g.guess("loups")["state"]["finished"]
    assert g.guess("gris")["state"]["finished"]


def test_any_form_and_order_of_the_name_wins():
    g = game()
    g.guess("GRIS")
    assert g.guess("loup")["state"]["finished"]


def test_exact_title_still_wins():
    g = game()
    g.guess("canis")
    assert g.guess("lupus")["state"]["finished"]


def test_half_a_title_and_half_a_name_does_not_win():
    g = game()
    g.guess("canis")
    assert not g.guess("gris")["state"]["finished"]


def test_saved_round_with_the_name_already_guessed_finishes_when_restored():
    g = game()
    g.guess("loup")
    g.guess("gris")
    saved = {"lang": "fr", "level": "famous", "article": ARTICLE, "guesses": ["loup", "gris"], "gave_up": False}
    assert Game.restore(g.id, saved, NoCloseness()).state()["finished"]


def test_the_name_is_never_sent_while_hidden():
    assert "gris" not in str(game().state())
