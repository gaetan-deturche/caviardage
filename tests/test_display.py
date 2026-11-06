"""Found fractions, superscripts and subscripts go back to how the page writes them."""
import pytest

from caviardage import text
from caviardage.articles import _plain_text
from caviardage.game import Game


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


def game(html="<p>Du CO<sub>2</sub> au XX<sup>e</sup> siècle, soit ½ ou 3¼ litre.</p>", title="Pont"):
    return Game({"title": title, "paragraphs": [_plain_text(html).strip()], "url": "x"}, "fr", NoCloseness())


def shown(state):
    return [t for t in state["tokens"] if t.get("revealed")]


def texts(state):
    return [t["text"] for t in shown(state)]


def test_tokens_know_their_script():
    tokens = {t["text"]: t.get("script") for t in text.tokenize(_plain_text("<p>CO<sub>2</sub> XX<sup>e</sup> H<sup>+</sup></p>")) if t["text"].strip()}
    assert tokens["2"] == "sub" and tokens["e"] == "sup" and tokens["+"] == "sup" and tokens["CO"] is None and tokens["XX"] is None


def test_marks_never_appear_in_text():
    for t in text.tokenize(_plain_text("<p>CO<sub>2</sub> et XX<sup>e</sup>.</p>")):
        assert not text.MARKS_RE.search(t["text"])


def test_plain_ordinal_endings_count_as_superscript():
    tokens = {t["text"]: t.get("script") for t in text.tokenize("7th XXe") if t["word"]}
    assert tokens == {"7": None, "th": "sup", "XX": None, "e": "sup"}


def test_found_script_is_sent_with_its_type():
    state = game().guess("2")["state"]
    assert [t.get("script") for t in shown(state) if t["text"] == "2"][0] == "sub"
    assert [t.get("script") for t in shown(game().guess("du")["state"]) if t["text"] == "Du"] == [None]


def test_hidden_bars_do_not_reveal_their_script():
    for t in game().state()["tokens"]:
        if t.get("word"):
            assert "script" not in t and "fraction" not in t and "text" not in t


def test_fraction_stays_written_out_until_both_parts_are_found():
    g = game()
    state = g.guess("1")["state"]
    assert "½" not in texts(state) and "1" in texts(state) and "/" in [t.get("text") for t in state["tokens"]]
    state = g.guess("2")["state"]
    assert "½" in texts(state) and "2" in texts(state)  # The 2 of CO2 stays, the fraction collapses.
    assert sum(1 for t in state["tokens"] if t.get("text") == "/") == 1  # Only the slash of 3 1/4.


def test_mixed_number_goes_back_without_the_space():
    g = game("<p>Soit 3¼ litre.</p>")
    for word in ("1", "4"):
        state = g.guess(word)["state"]
    written = "".join(t.get("text", "#") for t in state["tokens"] if t["part"] == "body")
    assert "#¼" in written and "# ¼" not in written


def test_finished_round_shows_short_form_and_marks_unfound_fractions():
    state = game().give_up()
    fraction = [t for t in state["tokens"] if t.get("text") == "½"][0]
    assert fraction["missed"]
    assert "/" not in [t["text"] for t in state["tokens"] if "text" in t]
    g = game()
    g.guess("1")
    g.guess("2")
    assert not [t for t in g.give_up()["tokens"] if t.get("text") == "½"][0]["missed"]


def test_half_found_fraction_is_marked_missed_at_the_end():
    g = game()
    g.guess("1")
    assert [t for t in g.give_up()["tokens"] if t.get("text") == "½"][0]["missed"]


def test_short_form_is_never_sent_early():
    assert "½" not in str(game().state())
    assert "¼" not in str(game().guess("1")["state"])


def test_rounds_saved_with_old_marks_still_load():
    g = Game({"title": "Pont", "paragraphs": ["Du CO" + text.WORD_BREAK + "2" + text.WORD_BREAK + " ici."], "url": "x"}, "fr", NoCloseness())
    assert texts(g.give_up()) == ["Pont", "Du", "CO", "2", "ici"]
