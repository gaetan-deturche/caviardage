"""Hints show a hidden word one letter at a time. The last letter reveals it; for a title word, it gives up the page."""
from caviardage.game import Game
from caviardage.saves import Saves


class Scores:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


ARTICLE = {"title": "Grand Pont", "paragraphs": ["Le pont traverse la rivière. Un pont de pierre."], "url": "x"}


def game():
    return Game(ARTICLE, "fr", Scores())


def index_of(g, word):
    return next(t["i"] for t in g.words if t["text"] == word)


def shown(state):
    return [t for t in state["tokens"] if t.get("hint")]


def test_letters_come_one_at_a_time_on_every_copy():
    g = game()
    first = g.hint(index_of(g, "rivière"))
    assert first["letters"] == 1 and not first["revealed"]
    assert [t["hint"] for t in shown(first["state"])] == ["r"]
    second = g.hint(index_of(g, "rivière"))
    assert [t["hint"] for t in shown(second["state"])] == ["ri"]
    assert second["state"]["hints"] == 2 and second["state"]["count"] == 0


def test_a_hint_on_a_word_shows_on_all_its_copies_in_their_own_case():
    g = game()
    state = g.hint([t["i"] for t in g.words if t["text"] == "pont"][1])["state"]
    assert sorted(t["hint"] for t in state["tokens"] if t.get("hint")) == ["P", "p", "p"]


def test_the_last_letter_of_a_text_word_just_reveals_it():
    g = game()
    for _ in range(len("pierre")):
        result = g.hint(index_of(g, "pierre"))
    assert result["revealed"] and not result["gaveUp"]
    word = [t for t in result["state"]["tokens"] if t.get("text") == "pierre"][0]
    assert word["revealed"] and not word.get("given")
    assert not result["state"]["finished"]
    assert g.hint(index_of(g, "pierre")) == {"error": "invalid"}


def test_letters_before_the_last_give_nothing_up():
    g = game()
    for _ in range(len("grand") - 1):
        result = g.hint(index_of(g, "Grand"))
    assert not result["revealed"] and not result["state"]["finished"]


def test_the_last_letter_of_a_title_word_gives_up_the_page():
    g = game()
    for _ in range(len("grand")):
        result = g.hint(index_of(g, "Grand"))
    assert result["revealed"] and result["gaveUp"]
    assert result["state"]["finished"] and result["state"]["gaveUp"]


def test_a_text_copy_of_a_title_word_also_gives_up_the_page():
    g = game()
    body_pont = [t["i"] for t in g.words if t["text"] == "pont"][0]
    for _ in range(len("pont")):
        result = g.hint(body_pont)
    assert result["gaveUp"] and result["state"]["finished"]


def test_finding_the_title_without_hints_still_wins():
    g = game()
    g.hint(index_of(g, "rivière"))
    g.guess("grand")
    state = g.guess("pont")["state"]
    assert state["finished"] and not state["gaveUp"]


def test_guessing_a_hinted_word_reveals_it_as_found():
    g = game()
    g.hint(index_of(g, "rivière"))
    state = g.guess("rivière")["state"]
    word = [t for t in state["tokens"] if t.get("text") == "rivière"][0]
    assert word["revealed"] and not word["given"]


def test_hints_survive_a_saved_round_in_order(tmp_path):
    saves = Saves(tmp_path / "g.sqlite")
    g = game()
    g.hint(index_of(g, "rivière"))
    g.guess("traverse")
    for _ in range(len("pierre")):
        g.hint(index_of(g, "pierre"))
    saves.save(g)
    again = Game.restore(g.id, saves.load(g.id), Scores())
    assert again.state() == g.state()
    assert again.state()["version"] == 1 + 1 + len("pierre")


def test_no_hint_after_the_end():
    g = game()
    g.give_up()
    assert g.hint(index_of(g, "rivière")) == {"error": "finished"}
