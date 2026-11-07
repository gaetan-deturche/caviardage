"""Caviardage local server. Run with: .venv\\Scripts\\python app.py"""
import re
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

from caviardage.articles import ArticleError, Articles
from caviardage.closeness import Closeness
from caviardage.game import Game
from caviardage.saves import Saves

PORT = 5180
STATIC = Path(__file__).resolve().parent / "static"
MAX_GAMES = 20  # Rounds kept in memory. Older ones are reloaded from disk when needed.
GAME_ID = re.compile(r"[0-9a-f]{8}|[0-9a-f]{12}")
PLAYER_ID = re.compile(r"[0-9a-f]{8}")

app = Flask(__name__)
closeness = Closeness()
articles = Articles()
saves = Saves()
games = {}
lock = threading.Lock()


def _remember(game):
    games[game.id] = game
    while len(games) > MAX_GAMES:
        games.pop(next(iter(games)))


def _game(game_id):
    """A round from memory or from disk. Call with the lock held."""
    game_id = re.sub(r"[^0-9a-f]", "", str(game_id or "").lower())
    if not GAME_ID.fullmatch(game_id):
        return None
    if game_id in games:
        return games[game_id]
    saved = saves.load(game_id)
    if not saved:
        return None
    game = Game.restore(game_id, saved, closeness)
    _remember(game)
    return game


def _player(value):
    """A valid player code, in any case and with or without its dash, or None."""
    player = re.sub(r"[^0-9a-f]", "", str(value or "").lower())
    return player if PLAYER_ID.fullmatch(player) else None


def _add_play(value, game):
    player = _player(value)
    if player:
        saves.add_play(player, game.id)


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.post("/api/new")
def new_game():
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") if body.get("lang") in ("fr", "en") else "fr"
    level = body.get("level") if body.get("level") in ("famous", "wide", "deep") else "famous"
    try:
        article = articles.next(lang, level)
    except ArticleError as error:
        return jsonify({"error": str(error)}), 503
    game = Game(article, lang, closeness, level=level)
    with lock:
        saves.save(game)
        _add_play(body.get("player"), game)
        _remember(game)
        return jsonify(game.state())


@app.get("/api/game/<game_id>")
def load_game(game_id):
    with lock:
        game = _game(game_id)
        if not game:
            return jsonify({"error": "expired"}), 404
        # Other players' browsers ask often, so answer briefly when nothing has changed.
        known = request.args.get("known", type=int)
        if known == len(game.guesses) and not game.finished:
            return jsonify({"same": True})
        if known is None:
            _add_play(request.args.get("player"), game)
        return jsonify(game.state())


@app.get("/api/history/<player_id>")
def history(player_id):
    player = _player(player_id)
    if not player:
        return jsonify({"error": "invalid"}), 400
    with lock:
        for game_id in saves.unknown_status(player):
            game = _game(game_id)
            if game:
                saves.set_finished(game.id, game.finished)
        return jsonify({"player": player, "rounds": saves.history(player)})


@app.post("/api/guess")
def guess():
    body = request.get_json(silent=True) or {}
    with lock:
        game = _game(body.get("id"))
        if not game:
            return jsonify({"error": "expired"}), 404
        result = game.guess(str(body.get("word", "")))
        if "error" not in result:
            saves.save(game)
            _add_play(body.get("player"), game)
        return jsonify(result)


@app.post("/api/giveup")
def give_up():
    body = request.get_json(silent=True) or {}
    with lock:
        game = _game(body.get("id"))
        if not game:
            return jsonify({"error": "expired"}), 404
        state = game.give_up()
        saves.save(game)
        return jsonify(state)


if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=PORT, threads=4)
