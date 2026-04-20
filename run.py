"""
run.py — punct de intrare unic, rulează din root-ul proiectului:
    python run.py
"""
import sys
import os

# Root-ul proiectului în sys.path — necesar pentru importurile din backend/ și database/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from database.db import init_db
from backend.app import app, collect_reading

if __name__ == "__main__":
    print("=" * 55)
    print("  SEN România — Monitor Producție Live")
    print("  http://localhost:5000")
    print("=" * 55)

    init_db()
    collect_reading()  # prima citire imediată la pornire

    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(timezone="Europe/Bucharest")
    sched.add_job(collect_reading, "interval", seconds=20)
    sched.start()

    try:
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
        print("\nServer oprit.")
