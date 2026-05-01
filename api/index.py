import sys
import os

# Vercel runs from api/ — add the project root so our modules are importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask, jsonify, render_template, request, send_from_directory

from wumpus_game import GameConfig, WumpusGame
from kb_logic import KnowledgeBase

# Create Flask app with correct template and static paths
app = Flask(
    __name__,
    template_folder=os.path.join(ROOT, "templates"),
    static_folder=os.path.join(ROOT, "static"),
    static_url_path="/static",
)

_game = None
_stats = {"wins": 0, "losses": 0, "total_episodes": 0}


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/state")
def api_state():
    global _game
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
        _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.post("/api/new")
def api_new():
    global _game
    data = request.get_json(silent=True) or {}
    rows = max(3, min(12, int(data.get("rows", 4))))
    cols = max(3, min(12, int(data.get("cols", 4))))
    pits = max(1, min(30, int(data.get("pits", 3))))
    _game = WumpusGame(GameConfig(rows=rows, cols=cols, pits=pits))
    _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.post("/api/step")
def api_step():
    global _game, _stats
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
        _game.start_new_episode()
    was_over = _game.game_over
    _game.step()
    if _game.game_over and not was_over:
        _stats["total_episodes"] += 1
        if _game.status in ("Fell into pit", "Eaten by wumpus"):
            _stats["losses"] += 1
        else:
            _stats["wins"] += 1
    return jsonify(_game.to_public_state())


@app.post("/api/reset")
def api_reset():
    global _game
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
    _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.get("/api/stats")
def api_stats():
    return jsonify(_stats)


@app.get("/api/kb_clauses")
def api_kb_clauses():
    if _game is None:
        return jsonify({"clauses": []})
    return jsonify({"clauses": _game.get_kb_clauses()})


@app.get("/api/resolution_trace")
def api_resolution_trace():
    if _game is None:
        return jsonify({"trace": [], "query": ""})
    return jsonify(_game.get_resolution_trace())
