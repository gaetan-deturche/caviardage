"""A player's list of rounds, which never gives away an unfinished page."""
import sqlite3

from caviardage.game import Game
from caviardage.saves import Saves


class NoCloseness:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


ARTICLE = {"title": "Pont de Brooklyn", "paragraphs": ["Le pont est grand."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", NoCloseness(), level="wide")


def saved(saves, g, player="aaaa1111"):
    saves.save(g)
    saves.add_play(player, g.id)
    return g


def test_empty_history(tmp_path):
    assert Saves(tmp_path / "g.sqlite").history("aaaa1111") == []


def test_title_hidden_until_the_round_is_over(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = game()
    g.guess("pont")
    saved(saves, g)
    row = saves.history("aaaa1111")[0]
    assert row["title"] is None and not row["finished"] and row["count"] == 1 and row["level"] == "wide"
    assert "Brooklyn" not in str(saves.history("aaaa1111"))
    g.give_up()
    saves.save(g)
    row = saves.history("aaaa1111")[0]
    assert row["title"] == "Pont de Brooklyn" and row["finished"] and row["gaveUp"]


def test_solved_round_shows_its_title(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = game()
    for word in ("pont", "de", "brooklyn"):
        g.guess(word)
    saved(saves, g)
    row = saves.history("aaaa1111")[0]
    assert row["title"] == "Pont de Brooklyn" and row["finished"] and not row["gaveUp"]


def test_hints_used_are_counted(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = game()
    assert saved(saves, g) and saves.history("aaaa1111")[0]["hints"] == 0
    grand = next(t["i"] for t in g.words if t["text"] == "grand")
    g.hint(grand)
    g.hint(grand)
    saves.save(g)
    assert saves.history("aaaa1111")[0]["hints"] == 2


def test_players_only_see_their_own_rounds(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    mine, theirs = game(), game()
    saved(saves, mine, "aaaa1111")
    saved(saves, theirs, "bbbb2222")
    assert [r["id"] for r in saves.history("aaaa1111")] == [mine.id]
    assert [r["id"] for r in saves.history("bbbb2222")] == [theirs.id]


def test_shared_round_appears_for_both_once(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = saved(saves, game(), "aaaa1111")
    saves.add_play("bbbb2222", g.id)
    saves.add_play("bbbb2222", g.id)
    assert len(saves.history("bbbb2222")) == 1 and len(saves.history("aaaa1111")) == 1


def test_newest_first(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    first, second = saved(saves, game()), saved(saves, game())
    first.guess("pont")
    saves.save(first)
    assert [r["id"] for r in saves.history("aaaa1111")] == [first.id, second.id]


def test_saves_made_before_history_keep_working(tmp_path):
    path = tmp_path / "old.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE games(id TEXT PRIMARY KEY, lang TEXT, level TEXT, article TEXT, guesses TEXT, gave_up INTEGER, updated REAL)")
    db.execute("INSERT INTO games VALUES ('abcd1234','fr','famous','{\"title\": \"Pont\", \"paragraphs\": []}','[\"le\"]',0,9999999999)")
    db.commit(); db.close()
    saves = Saves(path)
    assert saves.load("abcd1234")["guesses"] == ["le"]
    saves.add_play("aaaa1111", "abcd1234")
    assert saves.unknown_status("aaaa1111") == ["abcd1234"]
    assert saves.history("aaaa1111")[0]["title"] is None
    saves.set_finished("abcd1234", True)
    assert saves.unknown_status("aaaa1111") == [] and saves.history("aaaa1111")[0]["title"] == "Pont"
