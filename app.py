import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "gigplanner.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    cur = db.cursor()
    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            instruments_played TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS band_admins (
            band_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (band_id, user_id),
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS band_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            instruments_played TEXT,
            is_co_admin INTEGER NOT NULL DEFAULT 0,
            UNIQUE (band_id, user_id),
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS part_defaults (
            part_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY(part_id) REFERENCES parts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS gigs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            title TEXT,
            gig_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT NOT NULL,
            fee_per_player REAL,
            fee_for_band REAL,
            status TEXT NOT NULL CHECK(status IN ('Confirmed','Unconfirmed')),
            created_at TEXT NOT NULL,
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS gig_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            part_name TEXT NOT NULL,
            assigned_user_id INTEGER,
            FOREIGN KEY(gig_id) REFERENCES gigs(id) ON DELETE CASCADE,
            FOREIGN KEY(assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Available','Not Available','Unsure yet','Unanswered')),
            updated_at TEXT NOT NULL,
            UNIQUE(gig_id, user_id),
            FOREIGN KEY(gig_id) REFERENCES gigs(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    user_columns = {row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "instruments_played" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN instruments_played TEXT")

    availability_sql_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'availability'"
    ).fetchone()
    availability_sql = availability_sql_row[0] if availability_sql_row else ""
    if "Unanswered" not in availability_sql:
        cur.executescript(
            """
            ALTER TABLE availability RENAME TO availability_old;

            CREATE TABLE availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gig_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Available','Not Available','Unsure yet','Unanswered')),
                updated_at TEXT NOT NULL,
                UNIQUE(gig_id, user_id),
                FOREIGN KEY(gig_id) REFERENCES gigs(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            INSERT INTO availability (id, gig_id, user_id, status, updated_at)
            SELECT id, gig_id, user_id, status, updated_at
            FROM availability_old;

            DROP TABLE availability_old;
            """
        )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def is_band_admin(band_id, user_id):
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM band_admins WHERE band_id = ? AND user_id = ?", (band_id, user_id)
    ).fetchone()
    return row is not None


@app.context_processor
def inject_user():
    user = current_user()
    current_band = None
    band_id = request.view_args.get("band_id") if request.view_args else None
    if user and band_id and is_band_admin(band_id, user["id"]):
        db = get_db()
        current_band = db.execute("SELECT id, name FROM bands WHERE id = ?", (band_id,)).fetchone()
    return {"current_user": user, "current_band": current_band}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("welcome.html", show_navbar=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not all([name, email, password]):
            return render_template("register.html", error="Name, email and password are required.")
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            return render_template("register.html", error="An account with that email already exists.")
        db.execute(
            "INSERT INTO users (name, email, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, generate_password_hash(password), datetime.utcnow().isoformat()),
        )
        db.commit()
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")
        session.clear()
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    return render_template("login.html", show_navbar=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        instruments = request.form.get("instruments_played", "").strip()
        db = get_db()
        db.execute(
            "UPDATE users SET phone = ?, instruments_played = ? WHERE id = ?",
            (phone, instruments, user["id"]),
        )
        db.commit()
        return render_template(
            "profile.html",
            user=db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone(),
            success="Your details were updated.",
        )
    return render_template("profile.html", user=user)


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    db = get_db()
    gigs = db.execute(
        """
        SELECT g.*, b.name AS band_name,
               GROUP_CONCAT(gp.part_name, ', ') AS parts,
               av.status AS availability_status
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        JOIN bands b ON b.id = g.band_id
        LEFT JOIN availability av ON av.gig_id = g.id AND av.user_id = ?
        WHERE gp.assigned_user_id = ?
        GROUP BY g.id
        ORDER BY g.gig_date DESC, g.start_time DESC
        """,
        (user["id"], user["id"]),
    ).fetchall()

    admin_bands = db.execute(
        """
        SELECT b.*
        FROM bands b
        JOIN band_admins ba ON ba.band_id = b.id
        WHERE ba.user_id = ?
        ORDER BY b.name
        """,
        (user["id"],),
    ).fetchall()
    return render_template("dashboard.html", gigs=gigs, admin_bands=admin_bands)


@app.route("/api/gig/<int:gig_id>/availability", methods=["POST"])
@login_required
def update_availability(gig_id):
    user = current_user()
    status = request.json.get("status")
    allowed = {"Available", "Not Available", "Unsure yet", "Unanswered"}
    if status not in allowed:
        return jsonify({"ok": False, "error": "Invalid status"}), 400

    db = get_db()
    can_see = db.execute(
        "SELECT 1 FROM gig_parts WHERE gig_id = ? AND assigned_user_id = ?", (gig_id, user["id"])
    ).fetchone()
    if not can_see:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    db.execute(
        """
        INSERT INTO availability (gig_id, user_id, status, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(gig_id, user_id)
        DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (gig_id, user["id"], status, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/band/create", methods=["GET", "POST"])
@login_required
def create_band():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            return render_template("create_band.html", error="Band name is required.")
        db = get_db()
        uid = session["user_id"]
        cur = db.execute(
            "INSERT INTO bands (name, created_by, created_at) VALUES (?, ?, ?)",
            (name, uid, datetime.utcnow().isoformat()),
        )
        band_id = cur.lastrowid
        db.execute("INSERT INTO band_admins (band_id, user_id) VALUES (?, ?)", (band_id, uid))
        db.execute(
            "INSERT INTO band_memberships (band_id, user_id, instruments_played, is_co_admin) VALUES (?, ?, ?, 1)",
            (band_id, uid, "",),
        )
        db.commit()
        return redirect(url_for("band_setup", band_id=band_id))
    return render_template("create_band.html")


@app.route("/band/<int:band_id>/setup/complete")
@login_required
def complete_band_setup(band_id):
    if not is_band_admin(band_id, session["user_id"]):
        return redirect(url_for("dashboard"))
    return redirect(url_for("band_admin", band_id=band_id))


@app.route("/band/<int:band_id>/setup")
@login_required
def band_setup(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return redirect(url_for("dashboard"))

    db = get_db()
    band = db.execute("SELECT * FROM bands WHERE id = ?", (band_id,)).fetchone()
    parts = db.execute(
        """
        SELECT p.*, pd.user_id AS default_user_id, u.name AS default_player_name
        FROM parts p
        LEFT JOIN part_defaults pd ON pd.part_id = p.id
        LEFT JOIN users u ON u.id = pd.user_id
        WHERE p.band_id = ?
        ORDER BY p.name
        """,
        (band_id,),
    ).fetchall()
    players = db.execute(
        """
        SELECT bm.*, u.name, u.email, u.phone,
               COALESCE(NULLIF(bm.instruments_played, ''), u.instruments_played, '') AS instruments_played
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    return render_template("band_setup.html", band=band, parts=parts, players=players)


@app.route("/api/band/<int:band_id>/part", methods=["POST"])
@login_required
def add_part(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Part name required"}), 400
    db = get_db()
    db.execute("INSERT INTO parts (band_id, name) VALUES (?, ?)", (band_id, name))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/part/<int:part_id>", methods=["DELETE"])
@login_required
def delete_part(band_id, part_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403

    db = get_db()
    part = db.execute("SELECT id FROM parts WHERE id = ? AND band_id = ?", (part_id, band_id)).fetchone()
    if not part:
        return jsonify({"ok": False, "error": "Part not found"}), 404

    db.execute("DELETE FROM parts WHERE id = ?", (part_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/player", methods=["POST"])
@login_required
def add_player_to_band(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403

    payload = request.json
    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip().lower()
    phone = payload.get("phone", "").strip()
    instruments = payload.get("instruments_played", "").strip()
    if not all([name, email]):
        return jsonify({"ok": False, "error": "Name and email are required"}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None:
        default_password = generate_password_hash("changeme123")
        cur = db.execute(
            """
            INSERT INTO users (name, email, phone, instruments_played, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, phone, instruments, default_password, datetime.utcnow().isoformat()),
        )
        user_id = cur.lastrowid
    else:
        user_id = user["id"]
        db.execute(
            """
            UPDATE users
            SET phone = CASE WHEN ? <> '' THEN ? ELSE phone END,
                instruments_played = CASE WHEN ? <> '' THEN ? ELSE instruments_played END
            WHERE id = ?
            """,
            (phone, phone, instruments, instruments, user_id),
        )

    db.execute(
        """
        INSERT INTO band_memberships (band_id, user_id, instruments_played, is_co_admin)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(band_id, user_id)
        DO UPDATE SET instruments_played = excluded.instruments_played
        """,
        (band_id, user_id, instruments or (user["instruments_played"] if user else "")),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/player/<int:user_id>", methods=["DELETE"])
@login_required
def delete_player_from_band(band_id, user_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403

    db = get_db()
    membership = db.execute(
        "SELECT id FROM band_memberships WHERE band_id = ? AND user_id = ?",
        (band_id, user_id),
    ).fetchone()
    if not membership:
        return jsonify({"ok": False, "error": "Player not found"}), 404

    db.execute("DELETE FROM band_admins WHERE band_id = ? AND user_id = ?", (band_id, user_id))
    db.execute(
        """
        DELETE FROM availability
        WHERE user_id = ?
          AND gig_id IN (SELECT id FROM gigs WHERE band_id = ?)
        """,
        (user_id, band_id),
    )
    db.execute(
        """
        DELETE FROM part_defaults
        WHERE user_id = ?
          AND part_id IN (SELECT id FROM parts WHERE band_id = ?)
        """,
        (user_id, band_id),
    )
    db.execute(
        """
        UPDATE gig_parts
        SET assigned_user_id = NULL
        WHERE assigned_user_id = ?
          AND gig_id IN (SELECT id FROM gigs WHERE band_id = ?)
        """,
        (user_id, band_id),
    )
    db.execute("DELETE FROM band_memberships WHERE band_id = ? AND user_id = ?", (band_id, user_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/player/<int:user_id>/coadmin", methods=["POST"])
@login_required
def set_coadmin(band_id, user_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403

    enabled = bool(request.json.get("is_co_admin"))
    db = get_db()
    db.execute(
        "UPDATE band_memberships SET is_co_admin = ? WHERE band_id = ? AND user_id = ?",
        (1 if enabled else 0, band_id, user_id),
    )
    if enabled:
        db.execute(
            "INSERT OR IGNORE INTO band_admins (band_id, user_id) VALUES (?, ?)", (band_id, user_id)
        )
    else:
        db.execute(
            "DELETE FROM band_admins WHERE band_id = ? AND user_id = ?",
            (band_id, user_id),
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/part/<int:part_id>/default", methods=["POST"])
@login_required
def set_part_default(band_id, part_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403
    user_id = request.json.get("user_id")
    db = get_db()
    db.execute(
        "INSERT INTO part_defaults (part_id, user_id) VALUES (?, ?) ON CONFLICT(part_id) DO UPDATE SET user_id = excluded.user_id",
        (part_id, user_id),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/band/<int:band_id>/admin")
@login_required
def band_admin(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return redirect(url_for("dashboard"))
    db = get_db()
    band = db.execute("SELECT * FROM bands WHERE id = ?", (band_id,)).fetchone()
    gigs = db.execute(
        """
        SELECT g.*,
               SUM(CASE WHEN COALESCE(av.status, 'Unanswered') = 'Available' THEN 1 ELSE 0 END) AS available_count,
               SUM(CASE WHEN COALESCE(av.status, 'Unanswered') = 'Not Available' THEN 1 ELSE 0 END) AS not_available_count,
               SUM(CASE WHEN COALESCE(av.status, 'Unanswered') = 'Unsure yet' THEN 1 ELSE 0 END) AS unsure_count,
               SUM(CASE WHEN COALESCE(av.status, 'Unanswered') = 'Unanswered' THEN 1 ELSE 0 END) AS unanswered_count
        FROM gigs g
        LEFT JOIN band_memberships bm ON bm.band_id = g.band_id
        LEFT JOIN availability av ON av.gig_id = g.id AND av.user_id = bm.user_id
        WHERE g.band_id = ?
        GROUP BY g.id
        ORDER BY g.gig_date DESC, g.start_time DESC
        """,
        (band_id,),
    ).fetchall()
    players = db.execute(
        """
        SELECT u.id, u.name
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    parts = db.execute("SELECT * FROM parts WHERE band_id = ? ORDER BY name", (band_id,)).fetchall()
    return render_template(
        "band_admin.html",
        band=band,
        gigs=gigs,
        players=[dict(player) for player in players],
        parts=parts,
    )


@app.route("/api/band/<int:band_id>/gig", methods=["POST"])
@login_required
def create_gig(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403
    data = request.json
    required = ["gig_date", "start_time", "end_time", "location", "status"]
    if not all(data.get(k) for k in required):
        return jsonify({"ok": False, "error": "Missing required fields"}), 400

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO gigs (band_id, title, gig_date, start_time, end_time, location, fee_per_player, fee_for_band, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            band_id,
            data.get("title", "").strip(),
            data["gig_date"],
            data["start_time"],
            data["end_time"],
            data["location"],
            data.get("fee_per_player") or None,
            data.get("fee_for_band") or None,
            data["status"],
            datetime.utcnow().isoformat(),
        ),
    )
    gig_id = cur.lastrowid

    defaults = db.execute(
        """
        SELECT p.name, pd.user_id
        FROM parts p
        LEFT JOIN part_defaults pd ON pd.part_id = p.id
        WHERE p.band_id = ?
        """,
        (band_id,),
    ).fetchall()
    for row in defaults:
        db.execute(
            "INSERT INTO gig_parts (gig_id, part_name, assigned_user_id) VALUES (?, ?, ?)",
            (gig_id, row["name"], row["user_id"]),
        )

    band_players = db.execute(
        """
        SELECT user_id
        FROM band_memberships
        WHERE band_id = ?
        """,
        (band_id,),
    ).fetchall()
    timestamp = datetime.utcnow().isoformat()
    for player in band_players:
        db.execute(
            """
            INSERT OR IGNORE INTO availability (gig_id, user_id, status, updated_at)
            VALUES (?, ?, 'Unanswered', ?)
            """,
            (gig_id, player["user_id"], timestamp),
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gig/<int:gig_id>", methods=["POST", "DELETE"])
@login_required
def update_gig(gig_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if not gig or not is_band_admin(gig["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    if request.method == "DELETE":
        db.execute("DELETE FROM gigs WHERE id = ?", (gig_id,))
        db.commit()
        return jsonify({"ok": True})

    data = request.json
    db.execute(
        """
        UPDATE gigs SET
            gig_date = ?,
            start_time = ?,
            end_time = ?,
            location = ?,
            fee_per_player = ?,
            fee_for_band = ?,
            status = ?
        WHERE id = ?
        """,
        (
            data.get("gig_date", gig["gig_date"]),
            data.get("start_time", gig["start_time"]),
            data.get("end_time", gig["end_time"]),
            data.get("location", gig["location"]),
            data.get("fee_per_player", gig["fee_per_player"]),
            data.get("fee_for_band", gig["fee_for_band"]),
            data.get("status", gig["status"]),
            gig_id,
        ),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gig/<int:gig_id>/parts")
@login_required
def gig_parts(gig_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if not gig or not is_band_admin(gig["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    rows = db.execute(
        """
        SELECT gp.id, gp.part_name, gp.assigned_user_id, u.name AS assigned_user_name,
               av.status AS availability_status
        FROM gig_parts gp
        LEFT JOIN users u ON u.id = gp.assigned_user_id
        LEFT JOIN availability av ON av.gig_id = gp.gig_id AND av.user_id = gp.assigned_user_id
        WHERE gp.gig_id = ?
        ORDER BY gp.part_name
        """,
        (gig_id,),
    ).fetchall()
    return jsonify({"ok": True, "parts": [dict(r) for r in rows]})


@app.route("/api/gig/<int:gig_id>/responses")
@login_required
def gig_responses(gig_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if not gig or not is_band_admin(gig["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    rows = db.execute(
        """
        SELECT u.id AS user_id,
               u.name AS player_name,
               COALESCE(av.status, 'Unanswered') AS availability_status,
               av.updated_at
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        LEFT JOIN availability av ON av.gig_id = ? AND av.user_id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (gig_id, gig["band_id"]),
    ).fetchall()
    return jsonify({"ok": True, "responses": [dict(r) for r in rows]})


@app.route("/api/gig/<int:gig_id>/part", methods=["POST"])
@login_required
def add_gig_part(gig_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if not gig or not is_band_admin(gig["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    part_name = request.json.get("part_name", "").strip()
    assigned_user_id = request.json.get("assigned_user_id")
    if not part_name:
        return jsonify({"ok": False, "error": "part_name required"}), 400
    db.execute(
        "INSERT INTO gig_parts (gig_id, part_name, assigned_user_id) VALUES (?, ?, ?)",
        (gig_id, part_name, assigned_user_id or None),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gig/part/<int:gp_id>", methods=["POST", "DELETE"])
@login_required
def update_gig_part(gp_id):
    db = get_db()
    row = db.execute(
        """
        SELECT gp.*, g.band_id
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        WHERE gp.id = ?
        """,
        (gp_id,),
    ).fetchone()
    if not row or not is_band_admin(row["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    if request.method == "DELETE":
        db.execute("DELETE FROM gig_parts WHERE id = ?", (gp_id,))
    else:
        data = request.json
        db.execute(
            "UPDATE gig_parts SET part_name = ?, assigned_user_id = ? WHERE id = ?",
            (data.get("part_name", row["part_name"]), data.get("assigned_user_id") or None, gp_id),
        )
    db.commit()
    return jsonify({"ok": True})

init_db()


if __name__ == "__main__":
    app.run(debug=True)
