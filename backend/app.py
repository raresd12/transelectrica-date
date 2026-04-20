"""
backend/app.py
Flask app cu API REST.
Schedularul și init DB sunt gestionate din run.py.
"""

import sys
import os
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request

# Root-ul proiectului în path (backend/ e cu un nivel mai jos)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    insert_reading, get_latest,
    get_history_aggregated, get_raw_recent,
)
from backend.scraper import fetch_data

logger = logging.getLogger("sen_monitor.app")

# Flask servește frontend-ul din ../frontend/
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, static_folder=os.path.join(_root, "frontend"), static_url_path="")

# Stare globală — actualizată de collect_reading()
_status = {
    "source": "initializing",
    "last_sync": None,
    "error_msg": None,
    "total_readings": 0,
}


# ─── Funcție colectare (apelată din run.py prin scheduler) ────────────────────

def collect_reading():
    """Preia o citire de la Transelectrica și o salvează în DB."""
    global _status
    data = fetch_data()
    if data:
        try:
            insert_reading(data)
            _status["source"] = "online"
            _status["last_sync"] = data["timestamp"]
            _status["error_msg"] = None
            _status["total_readings"] += 1
            logger.info("Citire salvată. Total: %d", _status["total_readings"])
        except Exception as e:
            logger.error("Eroare salvare DB: %s", e)
            _status["source"] = "error"
            _status["error_msg"] = str(e)
    else:
        _status["source"] = "error"
        _status["error_msg"] = "Citire eșuată de la Transelectrica"
        logger.warning("Citire eșuată — se va reîncerca la următorul interval.")


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/latest")
def api_latest():
    row = get_latest()
    if row is None:
        return jsonify({"error": "Nicio citire disponibilă încă."}), 404
    return jsonify(row)


@app.route("/api/history")
def api_history():
    try:
        minutes = min(int(request.args.get("minutes", 15)), 60)
    except ValueError:
        minutes = 15
    return jsonify(get_history_aggregated(minutes))


@app.route("/api/status")
def api_status():
    return jsonify({
        "source":         _status["source"],
        "last_sync":      _status["last_sync"],
        "error_msg":      _status["error_msg"],
        "total_readings": _status["total_readings"],
        "server_time":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    })


@app.route("/api/raw-recent")
def api_raw_recent():
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50
    return jsonify(get_raw_recent(limit))


@app.route("/")
def index():
    return app.send_static_file("index.html")
