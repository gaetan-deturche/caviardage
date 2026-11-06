"""Saved rounds, so a reload, a server restart or another computer can resume them."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

KEEP_DAYS = 180
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "games.sqlite"


class Saves:
    def __init__(self, path=None):
        path = path or os.environ.get("CAVIARDAGE_SAVES") or DEFAULT_PATH
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock, self.db:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS games("
                "id TEXT PRIMARY KEY, lang TEXT, level TEXT, article TEXT, guesses TEXT, gave_up INTEGER, updated REAL)"
            )
            self.db.execute("DELETE FROM games WHERE updated < ?", (time.time() - KEEP_DAYS * 86400,))

    def save(self, game):
        row = (
            game.id, game.lang, game.level, json.dumps(game.article, ensure_ascii=False),
            json.dumps([g["word"] for g in game.guesses.values()], ensure_ascii=False),
            int(game.gave_up), time.time(),
        )
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO games VALUES (?,?,?,?,?,?,?)", row)

    def load(self, game_id):
        """The saved round as a dict, or None."""
        with self.lock:
            row = self.db.execute(
                "SELECT lang, level, article, guesses, gave_up FROM games WHERE id=?", (game_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "lang": row[0], "level": row[1], "article": json.loads(row[2]),
            "guesses": json.loads(row[3]), "gave_up": bool(row[4]),
        }
