"""A saved round reopens from its snapshot, exactly as it was, without replaying its guesses."""
from caviardage.game import Game
from caviardage.saves import Saves


class Scores:
    def __init__(self):
        self.calls = 0

    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        self.calls += 1
        return ("family", 0.6) if (a, b) == ("singe", "primate") else (None, 0.0)


ARTICLE = {"title": "Grand Pont", "paragraphs": ["Le primate traverse le pont de pierre en 1914."], "url": "x"}


def played():
    g = Game(ARTICLE, "fr", Scores())
    g.guess("singe")
    g.guess("pont")
    g.guess("1900")
    pierre = next(t["i"] for t in g.words if t["text"] == "pierre")
    for _ in range(len("pierre")):
        g.hint(pierre)
    g.hint(next(t["i"] for t in g.words if t["text"] == "traverse"))
    return g


def reopen(g, tmp_path, scores=None):
    saves = Saves(tmp_path / "g.sqlite")
    saves.save(g)
    return Game.restore(g.id, saves.load(g.id), scores or Scores())


def test_reopens_exactly_without_replaying(tmp_path):
    g = played()
    scores = Scores()
    again = reopen(g, tmp_path, scores)
    assert again.state() == g.state()
    assert scores.calls == 0


def test_play_goes_on_the_same_after_reopening(tmp_path):
    g = played()
    again = reopen(g, tmp_path)
    assert again.guess("singe") == {"error": "duplicate", "word": "singe"}
    assert again.guess("grand")["state"] == g.guess("grand")["state"]


def test_a_finished_round_reopens_finished(tmp_path):
    g = played()
    g.guess("grand")
    again = reopen(g, tmp_path)
    assert again.state()["finished"] and again.state() == g.state()


def test_falls_back_to_replay_when_the_page_splits_differently(tmp_path):
    g = played()
    saves = Saves(tmp_path / "g.sqlite")
    saves.save(g)
    saved = saves.load(g.id)
    saved["snapshot"]["tokens"] += 1
    scores = Scores()
    again = Game.restore(g.id, saved, scores)
    assert scores.calls > 0
    assert again.state() == g.state()


def test_old_saves_without_a_snapshot_still_replay(tmp_path):
    g = played()
    saves = Saves(tmp_path / "g.sqlite")
    saves.save(g)
    saved = saves.load(g.id)
    saved["snapshot"] = None
    assert Game.restore(g.id, saved, Scores()).state() == g.state()
