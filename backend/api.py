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
@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    jobs = supabase.table("jobs")\
        .select("*")\
        .eq("is_dismissed", False)\
        .order("date_found", desc=True)\
        .execute()
    return jsonify(jobs.data)

# ── get single job ────────────────────────────────────────────────────────────
@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = supabase.table("jobs")\
        .select("*")\
        .eq("id", job_id)\
        .single()\
        .execute()
    return jsonify(job.data)

# ── generate cover letter ─────────────────────────────────────────────────────
@app.route("/api/jobs/<job_id>/cover-letter", methods=["POST"])
def create_cover_letter(job_id):
    job = supabase.table("jobs")\
        .select("*")\
        .eq("id", job_id)\
        .single()\
        .execute()

    cover_letter = generate_cover_letter(job.data)

    application = supabase.table("applications").insert({
        "job_id": job_id,
        "cover_letter": cover_letter,
        "status": "draft",
    }).execute()

    return jsonify({
        "cover_letter": cover_letter,
        "application_id": application.data[0]["id"],
    })

# ── update cover letter ───────────────────────────────────────────────────────
@app.route("/api/applications/<app_id>", methods=["PATCH"])
def update_application(app_id):
    data = request.json
    result = supabase.table("applications")\
        .update(data)\
        .eq("id", app_id)\
        .execute()
    return jsonify(result.data)

# ── dismiss job ───────────────────────────────────────────────────────────────
@app.route("/api/jobs/<job_id>/dismiss", methods=["POST"])
def dismiss_job(job_id):
    supabase.table("jobs")\
        .update({"is_dismissed": True})\
        .eq("id", job_id)\
        .execute()
    return jsonify({"success": True})

# ── mark applied ──────────────────────────────────────────────────────────────
@app.route("/api/jobs/<job_id>/applied", methods=["POST"])
def mark_applied(job_id):
    data = request.json
    supabase.table("jobs")\
        .update({"is_applied": True})\
        .eq("id", job_id)\
        .execute()
    supabase.table("applications")\
        .update({
            "status": "sent",
            "date_sent": data.get("date_sent"),
            "notes": data.get("notes"),
        })\
        .eq("job_id", job_id)\
        .execute()
    return jsonify({"success": True})

# ── health check ──────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
