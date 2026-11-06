"""A saved round comes back exactly as it was, and never leaks hidden text."""
from caviardage.game import Game
from caviardage.saves import Saves


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return word != "zzzq"

    def tier(self, a, b, lang):
        return ("family", 0.6) if (a, b) == ("singe", "primate") else (None, 0.0)


ARTICLE = {
    "title": "Pont de Brooklyn",
    "paragraphs": ["Le pont est un primate. Il était grand, à New York, en 1883."],
    "url": "https://example.org/pont",
}


def reload(saves, game):
    saves.save(game)
    return Game.restore(game.id, saves.load(game.id), NoCloseness())


def test_round_trip_keeps_progress(tmp_path):
    saves = Saves(tmp_path / "games.sqlite")
    game = Game(ARTICLE, "fr", NoCloseness(), level="deep")
    for word in ("fut", "singe", "1880"):
        game.guess(word)
    again = reload(saves, game)
    assert again.state() == game.state()
    assert again.state()["level"] == "deep" and again.state()["count"] == 3
    assert [g["word"] for g in again.state()["log"]] == ["fut", "singe", "1880"]


def test_id_is_kept_and_short(tmp_path):
    game = Game(ARTICLE, "fr", NoCloseness())
    assert len(game.id) == 8
    assert reload(Saves(tmp_path / "g.sqlite"), game).id == game.id


def test_rejected_guesses_are_not_saved(tmp_path):
    game = Game(ARTICLE, "fr", NoCloseness())
    game.guess("pont")
    game.guess("zzzq")
    game.guess("pont")
    assert reload(Saves(tmp_path / "g.sqlite"), game).state()["count"] == 1


def test_finished_and_given_up_rounds_stay_finished(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    won = Game(ARTICLE, "fr", NoCloseness())
    for word in ("pont", "de", "brooklyn"):
        won.guess(word)
    state = reload(saves, won).state()
    assert state["finished"] and not state["gaveUp"] and state["answer"]["title"] == "Pont de Brooklyn"
    lost = Game(ARTICLE, "fr", NoCloseness())
    lost.guess("pont")
    lost.give_up()
    state = reload(saves, lost).state()
    assert state["finished"] and state["gaveUp"] and state["count"] == 1


def test_restored_round_keeps_answer_hidden(tmp_path):
    game = Game(ARTICLE, "fr", NoCloseness())
    game.guess("est")
    state = str(reload(Saves(tmp_path / "g.sqlite"), game).state())
    assert "Brooklyn" not in state and "primate" not in state and "example.org" not in state


def test_saves_survive_reopening_the_file(tmp_path):
    path = tmp_path / "g.sqlite"
    game = Game(ARTICLE, "fr", NoCloseness())
    game.guess("pont")
    Saves(path).save(game)
    assert Saves(path).load(game.id)["guesses"] == ["pont"]
    assert Saves(path).load("000000000000") is None
