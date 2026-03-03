import os
import threading
import schedule
import time
from flask import Flask, jsonify, request
from supabase import create_client
from job_searcher import generate_cover_letter, run_search
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

# ── scheduler (runs in background thread) ────────────────────────────────────
def run_scheduler():
    schedule.every(30).minutes.do(run_search)
    run_search()
    while True:
        schedule.run_pending()
        time.sleep(60)

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ── get all jobs ──────────────────────────────────────────────────────────────
