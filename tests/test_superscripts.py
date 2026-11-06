"""Superscripts and subscripts are separate words, wherever Wikipedia marks them."""
import pytest

from caviardage import text
from caviardage.articles import _clean, _plain_text, _to_article
from caviardage.game import Game


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


def words(sample):
    return [t["text"] for t in text.tokenize(sample) if t["word"]]


@pytest.mark.parametrize("html,expected", [
    ("<p>Formule CO<sub>2</sub> ici</p>", ["Formule", "CO", "2", "ici"]),
    ("<p>H<sub>2</sub>O</p>", ["H", "2", "O"]),
    ("<p>Le <span>XX</span><sup>e</sup> siècle</p>", ["Le", "XX", "e", "siècle"]),
    ("<p>1<sup>er</sup> mai</p>", ["1", "er", "mai"]),
    ("<p>10 m<sup>2</sup></p>", ["10", "m", "2"]),
    ("<p>x<sup>n+1</sup></p>", ["x", "n", "1"]),
    ("<p>Mlle<sup>a</sup> Dupont</p>", ["Mlle", "a", "Dupont"]),
])
def test_marked_scripts_become_separate_words(html, expected):
    assert words(_plain_text(html)) == expected


@pytest.mark.parametrize("sample,expected", [
    ("H₂O", ["H", "₂", "O"]), ("10 m²", ["10", "m", "²"]), ("CO₂ gaz", ["CO", "₂", "gaz"]), ("XXᵉ", ["XX", "ᵉ"]),
])
def test_unicode_scripts_become_separate_words(sample, expected):
    assert words(sample) == expected


def test_breaks_are_invisible_and_text_reads_the_same():
    plain = _plain_text("<p>Le CO<sub>2</sub> et le XX<sup>e</sup>.</p>").strip()
    assert text.strip_marks(plain) == "Le CO2 et le XXe."


def test_paragraphs_and_entities_survive():
    html = '<p class="mw-empty-elt"> </p><p>Un <b>grand</b>&nbsp;pont &amp; port.</p>\n<p>Second <i>texte</i>.</p><ul><li>Item</li></ul>'
    assert _clean(_plain_text(html)) == ["Un grand pont & port.", "Second texte.", "Item"]


def test_hidden_code_is_dropped():
    assert _plain_text("<style>.a{color:red}</style><p>Texte<math><mi>x</mi></math></p>").strip() == "Texte"


def test_other_name_still_works_with_marks():
    paragraph = _plain_text("<p>Les mollusques<sup>a</sup> (Mollusca) sont un groupe.</p>").strip()
    assert text.other_name("Mollusca", paragraph, "fr")[0].startswith("mollusques")


def test_article_from_formatted_extract():
    words_html = "".join(f"mot{i} " for i in range(90))
    article = _to_article({"title": "Dioxyde (gaz)", "fullurl": "x", "extract": f"<p>Le CO<sub>2</sub> {words_html}</p>"})
    assert article["title"] == "Dioxyde"
    assert text.SUB_OPEN in article["paragraphs"][0]


def test_each_part_is_guessed_separately():
    paragraph = _plain_text("<p>Le gaz CO<sub>2</sub> et le XX<sup>e</sup> siècle.</p>").strip()
    game = Game({"title": "Gaz", "paragraphs": [paragraph], "url": "x"}, "fr", NoCloseness())
    state = game.guess("CO")["state"]
    shown = [t["text"] for t in state["tokens"] if t.get("revealed")]
    assert "CO" in shown and "2" not in shown
    shown = [t["text"] for t in game.guess("2")["state"]["tokens"] if t.get("revealed")]
    assert "2" in shown


def test_saved_plain_rounds_still_load():
    game = Game({"title": "Gaz", "paragraphs": ["Le CO2 est un gaz au XXe siècle."], "url": "x"}, "fr", NoCloseness())
    assert "XX" in [t["text"] for t in game.give_up()["tokens"]]
