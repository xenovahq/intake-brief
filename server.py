import os
import sqlite3
import uuid
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from generate_brief import generate_markdown, calculate_completeness, determine_next_step
from ai_enrichment import get_ai_notes

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
DATABASE = "briefs.db"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # Create table with session_id included from the start
    conn.execute("""
        CREATE TABLE IF NOT EXISTS briefs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id           TEXT NOT NULL DEFAULT '',
            company_name         TEXT,
            industry             TEXT,
            project_description  TEXT,
            timeline             TEXT,
            budget               TEXT,
            existing_tools       TEXT,
            constraints          TEXT,
            current_pain_point   TEXT,
            desired_outcome      TEXT,
            decision_maker_name  TEXT,
            markdown_content     TEXT,
            completeness_score   INTEGER,
            total_fields         INTEGER,
            missing_fields       TEXT,
            vague_fields         TEXT,
            ai_notes             TEXT,
            created_at           TEXT
        )
    """)

    # Migration-safe: add column to pre-existing databases without it
    try:
        conn.execute("ALTER TABLE briefs ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # Column already exists — safe to ignore

    conn.commit()
    conn.close()


def get_session_id() -> str:
    """Return the visitor's session UUID, creating one on first visit (7-day cookie)."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.permanent = True
    return session["session_id"]


def purge_expired(conn):
    """Delete all rows older than 24 hours. Called on every dashboard/index load."""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM briefs WHERE created_at < ?", (cutoff,))
    conn.commit()


# Initialise DB at import time so gunicorn workers have the schema ready
init_db()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    sid = get_session_id()

    conn = get_db()
    purge_expired(conn)

    briefs = conn.execute(
        "SELECT * FROM briefs WHERE session_id = ? ORDER BY created_at DESC",
        (sid,),
    ).fetchall()
    conn.close()

    total = len(briefs)
    avg_score = (
        round(sum(b["completeness_score"] for b in briefs) / total, 1)
        if total else 0
    )

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    briefs_this_week = sum(
        1 for b in briefs if b["created_at"][:10] >= week_ago
    )

    return render_template(
        "dashboard.html",
        briefs=briefs,
        total=total,
        avg_score=avg_score,
        briefs_this_week=briefs_this_week,
    )


@app.route("/intake", methods=["GET"])
def intake_form():
    get_session_id()  # Ensure cookie is set before the form is shown
    return render_template("intake.html")


@app.route("/intake", methods=["POST"])
@limiter.limit("5 per hour")
def submit_intake():
    sid = get_session_id()

    # Core fields (aligned with generate_brief.py's required fields)
    intake_data = {
        "company_name":        request.form.get("company_name", "").strip(),
        "industry":            request.form.get("industry", "").strip(),
        "project_description": request.form.get("project_description", "").strip(),
        "timeline":            request.form.get("timeline", "").strip(),
        "budget":              request.form.get("budget", "").strip(),
        "existing_tools":      request.form.get("existing_tools", "").strip(),
        "constraints":         request.form.get("constraints", "").strip(),
    }

    # Extended fields (stored but not scored by generate_brief.py)
    extra_data = {
        "current_pain_point":  request.form.get("current_pain_point", "").strip(),
        "desired_outcome":     request.form.get("desired_outcome", "").strip(),
        "decision_maker_name": request.form.get("decision_maker_name", "").strip(),
    }

    # --- Existing generate_brief logic — unchanged ---
    markdown_content, company_name = generate_markdown(intake_data)
    score, total, missing, vague = calculate_completeness(intake_data)

    # --- AI enrichment layer ---
    ai_notes = get_ai_notes({**intake_data, **extra_data})

    if ai_notes:
        markdown_content += f"\n\n## AI Consultant Notes\n\n{ai_notes}"

    created_at = datetime.now().isoformat(timespec="seconds")

    conn = get_db()
    cursor = conn.execute(
        """
        INSERT INTO briefs (
            session_id,
            company_name, industry, project_description, timeline, budget,
            existing_tools, constraints, current_pain_point, desired_outcome,
            decision_maker_name, markdown_content, completeness_score,
            total_fields, missing_fields, vague_fields, ai_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid,
            intake_data["company_name"],
            intake_data["industry"],
            intake_data["project_description"],
            intake_data["timeline"],
            intake_data["budget"],
            intake_data["existing_tools"],
            intake_data["constraints"],
            extra_data["current_pain_point"],
            extra_data["desired_outcome"],
            extra_data["decision_maker_name"],
            markdown_content,
            score,
            total,
            ",".join(missing),
            ",".join(vague),
            ai_notes,
            created_at,
        ),
    )
    brief_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for("view_brief", id=brief_id))


@app.route("/brief/<int:id>")
def view_brief(id):
    sid = get_session_id()

    conn = get_db()
    # WHERE session_id = ? ensures a visitor can only read their own briefs
    brief = conn.execute(
        "SELECT * FROM briefs WHERE id = ? AND session_id = ?", (id, sid)
    ).fetchone()
    conn.close()

    if not brief:
        return render_template("404.html"), 404

    missing = [f for f in brief["missing_fields"].split(",") if f] if brief["missing_fields"] else []
    vague   = [f for f in brief["vague_fields"].split(",")   if f] if brief["vague_fields"]   else []

    pct = round((brief["completeness_score"] / brief["total_fields"]) * 100)

    next_step = determine_next_step(missing, vague)

    return render_template(
        "brief.html",
        brief=brief,
        missing=missing,
        vague=vague,
        pct=pct,
        next_step=next_step,
    )


@app.route("/brief/<int:id>/edit", methods=["GET"])
def edit_brief_form(id):
    sid = get_session_id()
    conn = get_db()
    brief = conn.execute(
        "SELECT * FROM briefs WHERE id = ? AND session_id = ?", (id, sid)
    ).fetchone()
    conn.close()
    if not brief:
        return render_template("404.html"), 404
    return render_template("edit.html", brief=brief)


@app.route("/brief/<int:id>/edit", methods=["POST"])
def edit_brief_submit(id):
    sid = get_session_id()
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM briefs WHERE id = ? AND session_id = ?", (id, sid)
    ).fetchone()
    if not existing:
        conn.close()
        return render_template("404.html"), 404

    intake_data = {
        "company_name":        request.form.get("company_name", "").strip(),
        "industry":            request.form.get("industry", "").strip(),
        "project_description": request.form.get("project_description", "").strip(),
        "timeline":            request.form.get("timeline", "").strip(),
        "budget":              request.form.get("budget", "").strip(),
        "existing_tools":      request.form.get("existing_tools", "").strip(),
        "constraints":         request.form.get("constraints", "").strip(),
    }
    extra_data = {
        "current_pain_point":  request.form.get("current_pain_point", "").strip(),
        "desired_outcome":     request.form.get("desired_outcome", "").strip(),
        "decision_maker_name": request.form.get("decision_maker_name", "").strip(),
    }

    markdown_content, _ = generate_markdown(intake_data)
    score, total, missing, vague = calculate_completeness(intake_data)

    ai_notes = existing["ai_notes"]
    if ai_notes:
        markdown_content += f"\n\n## AI Consultant Notes\n\n{ai_notes}"

    conn.execute(
        """
        UPDATE briefs SET
            company_name=?, industry=?, project_description=?, timeline=?,
            budget=?, existing_tools=?, constraints=?, current_pain_point=?,
            desired_outcome=?, decision_maker_name=?, markdown_content=?,
            completeness_score=?, total_fields=?, missing_fields=?, vague_fields=?
        WHERE id=? AND session_id=?
        """,
        (
            intake_data["company_name"],
            intake_data["industry"],
            intake_data["project_description"],
            intake_data["timeline"],
            intake_data["budget"],
            intake_data["existing_tools"],
            intake_data["constraints"],
            extra_data["current_pain_point"],
            extra_data["desired_outcome"],
            extra_data["decision_maker_name"],
            markdown_content,
            score,
            total,
            ",".join(missing),
            ",".join(vague),
            id,
            sid,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("view_brief", id=id))


@app.route("/brief/<int:id>/delete", methods=["POST"])
def delete_brief(id):
    sid = get_session_id()
    conn = get_db()
    conn.execute(
        "DELETE FROM briefs WHERE id = ? AND session_id = ?", (id, sid)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return render_template("429.html"), 429


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.permanent_session_lifetime = timedelta(days=7)
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=3002)
