"""A round from start to finish, with a fixed article and fake closeness."""
from caviardage.game import Game


class FakeCloseness:
    def in_vocabulary(self, word, lang):
        return word != "zzzq"

    def tier(self, a, b, lang):
        pairs = {("singe", "primate"): ("family", 0.6), ("mammifere", "primate"): ("scene", 0.3)}
        return pairs.get((a, b), (None, 0.0))


ARTICLE = {
    "title": "Pont de Brooklyn",
    "paragraphs": ["Le pont est un primate. Il était grand, à New York."],
    "url": "https://example.org/pont",
}


def new_game():
    return Game(ARTICLE, "fr", FakeCloseness())


def word_tokens(state):
    return [t for t in state["tokens"] if t.get("word")]


def test_hidden_text_is_not_sent():
    state = new_game().state()
    assert not any("text" in t for t in word_tokens(state))
    assert "answer" not in state
    assert "primate" not in str(state)


def test_conjugated_guess_reveals_all_forms():
    result = new_game().guess("fut")
    shown = {t["text"] for t in word_tokens(result["state"]) if t.get("revealed")}
    assert {"est", "était"} <= shown
    assert result["tier"] == "same"


def test_accent_free_guess_reveals_a_grave():
    result = new_game().guess("a")
    assert "à" in {t["text"] for t in word_tokens(result["state"]) if t.get("revealed")}


def test_closer_guess_replaces_weaker_one_and_keeps_word_hidden():
    game = new_game()
    game.guess("mammifere")
    state = game.guess("singe")["state"]
    slot = next(t for t in word_tokens(state) if t.get("near"))
    assert slot["near"] == "singe" and slot["tier"] == "family" and "text" not in slot
    weaker = game.guess("mammifère")
    assert weaker["error"] == "duplicate"


def test_duplicate_and_unknown_do_not_count():
    game = new_game()
    game.guess("pont")
    assert game.guess("PONT")["error"] == "duplicate"
    assert game.guess("zzzq")["error"] == "unknown"
    assert game.state()["count"] == 1


def test_overlong_guess_is_rejected_and_not_counted():
    game = new_game()
    assert game.guess("e" * 41)["error"] == "invalid"
    assert game.state()["count"] == 0


def test_win_needs_every_title_word():
    game = new_game()
    game.guess("pont")
    game.guess("de")
    assert not game.state()["finished"]
    state = game.guess("Brooklyn")["state"]
    assert state["finished"] and not state["gaveUp"]
    assert state["answer"]["title"] == "Pont de Brooklyn"


def test_finished_round_marks_the_words_not_found():
    game = new_game()
    game.guess("est")
    for word in ("pont", "de", "brooklyn"):
        game.guess(word)
    tokens = word_tokens(game.state())
    assert game.state()["finished"]
    found = {t["text"] for t in tokens if not t["missed"]}
    missed = {t["text"] for t in tokens if t["missed"]}
    assert {"Pont", "de", "Brooklyn", "est", "était"} <= found
    assert {"primate", "York"} <= missed


def test_give_up_marks_only_unfound_words_as_missed():
    game = new_game()
    game.guess("pont")
    tokens = word_tokens(game.give_up())
    assert not [t for t in tokens if t["text"] == "pont" and t["missed"]]
    assert [t for t in tokens if t["text"] == "primate" and t["missed"]]


def test_missed_is_not_sent_before_the_end():
    game = new_game()
    game.guess("pont")
    assert not [t for t in word_tokens(game.state()) if t.get("missed")]


def test_give_up_shows_everything():
    state = new_game().give_up()
    assert state["gaveUp"] and all(t.get("revealed") for t in word_tokens(state))
