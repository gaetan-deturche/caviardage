"""A finished round can be seen again as it looked while playing."""
from caviardage.game import Game
from caviardage.saves import Saves


class Scores:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return ("family", 0.6) if (a, b) == ("singe", "primate") else (None, 0.0)


ARTICLE = {"title": "Pont", "paragraphs": ["Le primate marbre, soit ½ part, au XXe siècle."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", Scores())


def bars(tokens):
    return [t for t in tokens if t.get("word") and not t.get("revealed")]


def test_not_sent_before_the_end():
    g = game()
    g.guess("singe")
    assert "guessView" not in g.state()


def test_guess_view_after_giving_up_keeps_bars_and_guesses():
    g = game()
    g.guess("singe")
    g.guess("le")
    state = g.give_up()
    view = state["guessView"]
    close = [t for t in view if t.get("near") == "singe"]
    assert len(close) == 1 and close[0]["shade"] > 0.5 and "text" not in close[0]
    assert "Le" in [t.get("text") for t in view if t.get("revealed")]
    assert bars(view) and not bars(state["tokens"])


def test_guess_view_after_winning():
    g = game()
    g.guess("singe")
    state = g.guess("pont")["state"]
    assert state["finished"] and [t for t in state["guessView"] if t.get("near") == "singe"]


def test_found_scripts_and_fractions_stay_as_they_were():
    g = game()
    g.guess("1")
    view = g.give_up()["guessView"]
    assert "/" in [t.get("text") for t in view]
    assert "1" in [t.get("text") for t in view if t.get("revealed")]
    assert "½" not in [t.get("text") for t in view]
    g = game()
    g.guess("1")
    g.guess("2")
    assert "½" in [t.get("text") for t in g.give_up()["guessView"]]


def test_view_survives_a_saved_round(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = game()
    g.guess("singe")
    g.give_up()
    saves.save(g)
    again = Game.restore(g.id, saves.load(g.id), Scores())
    assert again.state()["guessView"] == g.state()["guessView"]


def test_view_does_not_change_the_normal_tokens():
    g = game()
    g.guess("singe")
    state = g.give_up()
    assert all(t.get("revealed") for t in state["tokens"] if t.get("word"))
