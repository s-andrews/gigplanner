import json
import os
import secrets
import sqlite3
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "gigplanner.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SMTP_SERVER"] = os.environ.get("SMTP_SERVER", "localhost")
app.config["SMTP_PORT"] = int(os.environ.get("SMTP_PORT", "25"))
app.config["SMTP_USERNAME"] = os.environ.get("SMTP_USERNAME", "")
app.config["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD", "")
app.config["SMTP_USE_TLS"] = os.environ.get("SMTP_USE_TLS", "").lower() in {"1", "true", "yes"}
app.config["MAIL_FROM"] = os.environ.get("MAIL_FROM", "noreply@gigplanner.uk")
app.config["MAIL_ENVELOPE_FROM"] = os.environ.get("MAIL_ENVELOPE_FROM", "")
app.config["MAIL_FROM_DOMAIN"] = os.environ.get("MAIL_FROM_DOMAIN", "")
app.config["BASE_URL"] = os.environ.get("BASE_URL", "https://gigplanner.uk")
app.config["EMAIL_CHALLENGE_MAX_AGE"] = int(os.environ.get("EMAIL_CHALLENGE_MAX_AGE", "1200"))


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


DEFAULT_BAND_TIMEZONE = "Europe/London"
DEFAULT_GIG_LOCATION = "TBC"
BUNDLED_TIMEZONE_OPTIONS = [
    "Europe/Andorra",
    "Asia/Dubai",
    "Asia/Kabul",
    "Europe/Tirane",
    "Asia/Yerevan",
    "Antarctica/Casey",
    "Antarctica/Davis",
    "Antarctica/Mawson",
    "Antarctica/Palmer",
    "Antarctica/Rothera",
    "Antarctica/Troll",
    "Antarctica/Vostok",
    "America/Argentina/Buenos_Aires",
    "America/Argentina/Cordoba",
    "America/Argentina/Salta",
    "America/Argentina/Jujuy",
    "America/Argentina/Tucuman",
    "America/Argentina/Catamarca",
    "America/Argentina/La_Rioja",
    "America/Argentina/San_Juan",
    "America/Argentina/Mendoza",
    "America/Argentina/San_Luis",
    "America/Argentina/Rio_Gallegos",
    "America/Argentina/Ushuaia",
    "Pacific/Pago_Pago",
    "Europe/Vienna",
    "Australia/Lord_Howe",
    "Antarctica/Macquarie",
    "Australia/Hobart",
    "Australia/Melbourne",
    "Australia/Sydney",
    "Australia/Broken_Hill",
    "Australia/Brisbane",
    "Australia/Lindeman",
    "Australia/Adelaide",
    "Australia/Darwin",
    "Australia/Perth",
    "Australia/Eucla",
    "Asia/Baku",
    "America/Barbados",
    "Asia/Dhaka",
    "Europe/Brussels",
    "Europe/Sofia",
    "Atlantic/Bermuda",
    "America/La_Paz",
    "America/Noronha",
    "America/Belem",
    "America/Fortaleza",
    "America/Recife",
    "America/Araguaina",
    "America/Maceio",
    "America/Bahia",
    "America/Sao_Paulo",
    "America/Campo_Grande",
    "America/Cuiaba",
    "America/Santarem",
    "America/Porto_Velho",
    "America/Boa_Vista",
    "America/Manaus",
    "America/Eirunepe",
    "America/Rio_Branco",
    "Asia/Thimphu",
    "Europe/Minsk",
    "America/Belize",
    "America/St_Johns",
    "America/Halifax",
    "America/Glace_Bay",
    "America/Moncton",
    "America/Goose_Bay",
    "America/Toronto",
    "America/Iqaluit",
    "America/Winnipeg",
    "America/Resolute",
    "America/Rankin_Inlet",
    "America/Regina",
    "America/Swift_Current",
    "America/Edmonton",
    "America/Cambridge_Bay",
    "America/Inuvik",
    "America/Dawson_Creek",
    "America/Fort_Nelson",
    "America/Whitehorse",
    "America/Dawson",
    "America/Vancouver",
    "Europe/Zurich",
    "Africa/Abidjan",
    "Pacific/Rarotonga",
    "America/Santiago",
    "America/Coyhaique",
    "America/Punta_Arenas",
    "Pacific/Easter",
    "Asia/Shanghai",
    "Asia/Urumqi",
    "America/Bogota",
    "America/Costa_Rica",
    "America/Havana",
    "Atlantic/Cape_Verde",
    "Asia/Nicosia",
    "Asia/Famagusta",
    "Europe/Prague",
    "Europe/Berlin",
    "America/Santo_Domingo",
    "Africa/Algiers",
    "America/Guayaquil",
    "Pacific/Galapagos",
    "Europe/Tallinn",
    "Africa/Cairo",
    "Africa/El_Aaiun",
    "Europe/Madrid",
    "Africa/Ceuta",
    "Atlantic/Canary",
    "Europe/Helsinki",
    "Pacific/Fiji",
    "Atlantic/Stanley",
    "Pacific/Kosrae",
    "Atlantic/Faroe",
    "Europe/Paris",
    "Europe/London",
    "Asia/Tbilisi",
    "America/Cayenne",
    "Europe/Gibraltar",
    "America/Nuuk",
    "America/Danmarkshavn",
    "America/Scoresbysund",
    "America/Thule",
    "Europe/Athens",
    "Atlantic/South_Georgia",
    "America/Guatemala",
    "Pacific/Guam",
    "Africa/Bissau",
    "America/Guyana",
    "Asia/Hong_Kong",
    "America/Tegucigalpa",
    "America/Port-au-Prince",
    "Europe/Budapest",
    "Asia/Jakarta",
    "Asia/Pontianak",
    "Asia/Makassar",
    "Asia/Jayapura",
    "Europe/Dublin",
    "Asia/Jerusalem",
    "Asia/Kolkata",
    "Indian/Chagos",
    "Asia/Baghdad",
    "Asia/Tehran",
    "Europe/Rome",
    "America/Jamaica",
    "Asia/Amman",
    "Asia/Tokyo",
    "Africa/Nairobi",
    "Asia/Bishkek",
    "Pacific/Tarawa",
    "Pacific/Kanton",
    "Pacific/Kiritimati",
    "Asia/Pyongyang",
    "Asia/Seoul",
    "Asia/Almaty",
    "Asia/Qyzylorda",
    "Asia/Qostanay",
    "Asia/Aqtobe",
    "Asia/Aqtau",
    "Asia/Atyrau",
    "Asia/Oral",
    "Asia/Beirut",
    "Asia/Colombo",
    "Africa/Monrovia",
    "Europe/Vilnius",
    "Europe/Riga",
    "Africa/Tripoli",
    "Africa/Casablanca",
    "Europe/Chisinau",
    "Pacific/Kwajalein",
    "Asia/Yangon",
    "Asia/Ulaanbaatar",
    "Asia/Hovd",
    "Asia/Macau",
    "America/Martinique",
    "Europe/Malta",
    "Indian/Mauritius",
    "Indian/Maldives",
    "America/Mexico_City",
    "America/Cancun",
    "America/Merida",
    "America/Monterrey",
    "America/Matamoros",
    "America/Chihuahua",
    "America/Ciudad_Juarez",
    "America/Ojinaga",
    "America/Mazatlan",
    "America/Bahia_Banderas",
    "America/Hermosillo",
    "America/Tijuana",
    "Asia/Kuching",
    "Africa/Maputo",
    "Africa/Windhoek",
    "Pacific/Noumea",
    "Pacific/Norfolk",
    "Africa/Lagos",
    "America/Managua",
    "Asia/Kathmandu",
    "Pacific/Nauru",
    "Pacific/Niue",
    "Pacific/Auckland",
    "Pacific/Chatham",
    "America/Panama",
    "America/Lima",
    "Pacific/Tahiti",
    "Pacific/Marquesas",
    "Pacific/Gambier",
    "Pacific/Port_Moresby",
    "Pacific/Bougainville",
    "Asia/Manila",
    "Asia/Karachi",
    "Europe/Warsaw",
    "America/Miquelon",
    "Pacific/Pitcairn",
    "America/Puerto_Rico",
    "Asia/Gaza",
    "Asia/Hebron",
    "Europe/Lisbon",
    "Atlantic/Madeira",
    "Atlantic/Azores",
    "Pacific/Palau",
    "America/Asuncion",
    "Asia/Qatar",
    "Europe/Bucharest",
    "Europe/Belgrade",
    "Europe/Kaliningrad",
    "Europe/Moscow",
    "Europe/Simferopol",
    "Europe/Kirov",
    "Europe/Volgograd",
    "Europe/Astrakhan",
    "Europe/Saratov",
    "Europe/Ulyanovsk",
    "Europe/Samara",
    "Asia/Yekaterinburg",
    "Asia/Omsk",
    "Asia/Novosibirsk",
    "Asia/Barnaul",
    "Asia/Tomsk",
    "Asia/Novokuznetsk",
    "Asia/Krasnoyarsk",
    "Asia/Irkutsk",
    "Asia/Chita",
    "Asia/Yakutsk",
    "Asia/Khandyga",
    "Asia/Vladivostok",
    "Asia/Ust-Nera",
    "Asia/Magadan",
    "Asia/Sakhalin",
    "Asia/Srednekolymsk",
    "Asia/Kamchatka",
    "Asia/Anadyr",
    "Asia/Riyadh",
    "Pacific/Guadalcanal",
    "Africa/Khartoum",
    "Asia/Singapore",
    "America/Paramaribo",
    "Africa/Juba",
    "Africa/Sao_Tome",
    "America/El_Salvador",
    "Asia/Damascus",
    "America/Grand_Turk",
    "Africa/Ndjamena",
    "Asia/Bangkok",
    "Asia/Dushanbe",
    "Pacific/Fakaofo",
    "Asia/Dili",
    "Asia/Ashgabat",
    "Africa/Tunis",
    "Pacific/Tongatapu",
    "Europe/Istanbul",
    "Asia/Taipei",
    "Europe/Kyiv",
    "America/New_York",
    "America/Detroit",
    "America/Kentucky/Louisville",
    "America/Kentucky/Monticello",
    "America/Indiana/Indianapolis",
    "America/Indiana/Vincennes",
    "America/Indiana/Winamac",
    "America/Indiana/Marengo",
    "America/Indiana/Petersburg",
    "America/Indiana/Vevay",
    "America/Chicago",
    "America/Indiana/Tell_City",
    "America/Indiana/Knox",
    "America/Menominee",
    "America/North_Dakota/Center",
    "America/North_Dakota/New_Salem",
    "America/North_Dakota/Beulah",
    "America/Denver",
    "America/Boise",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Juneau",
    "America/Sitka",
    "America/Metlakatla",
    "America/Yakutat",
    "America/Nome",
    "America/Adak",
    "Pacific/Honolulu",
    "America/Montevideo",
    "Asia/Samarkand",
    "Asia/Tashkent",
    "America/Caracas",
    "Asia/Ho_Chi_Minh",
    "Pacific/Efate",
    "Pacific/Apia",
    "Africa/Johannesburg",
]
BUNDLED_TIMEZONE_SET = set(BUNDLED_TIMEZONE_OPTIONS)


def get_timezone_options():
    options = sorted(BUNDLED_TIMEZONE_OPTIONS)
    if DEFAULT_BAND_TIMEZONE not in options:
        options.insert(0, DEFAULT_BAND_TIMEZONE)
    return options


TIMEZONE_OPTIONS = get_timezone_options()
WEEKDAY_OPTIONS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


def normalize_band_timezone(value):
    timezone_name = (value or "").strip() or DEFAULT_BAND_TIMEZONE
    if timezone_name in BUNDLED_TIMEZONE_SET:
        return timezone_name
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None
    return timezone_name


def load_zoneinfo(timezone_name):
    normalized_timezone = normalize_band_timezone(timezone_name) or DEFAULT_BAND_TIMEZONE
    try:
        return ZoneInfo(normalized_timezone)
    except ZoneInfoNotFoundError:
        try:
            return ZoneInfo(DEFAULT_BAND_TIMEZONE)
        except ZoneInfoNotFoundError:
            return timezone.utc


def band_local_today(timezone_name):
    return datetime.now(load_zoneinfo(timezone_name)).date()


def years_before(value, years):
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - years)


def filter_visible_gigs(gigs):
    visible_gigs = []
    for gig in gigs:
        gig_date = parse_iso_date(gig["gig_date"])
        if not gig_date:
            continue
        if gig_date >= band_local_today(gig["band_timezone"]):
            visible_gigs.append(gig)
    return visible_gigs


def build_mailto_link(subject, emails):
    unique_emails = sorted({(email or "").strip() for email in emails if (email or "").strip()})
    if not unique_emails:
        return ""
    query = f"subject={quote(subject)}&bcc={quote(','.join(unique_emails))}"
    return f"mailto:?{query}"


def parse_weekday(value):
    try:
        weekday = int(value)
    except (TypeError, ValueError):
        return None
    return weekday if 0 <= weekday <= 6 else None


def next_weekday_on_or_after(start_date, target_weekday):
    days_ahead = (target_weekday - start_date.weekday()) % 7
    return start_date + timedelta(days=days_ahead)


def generate_rehearsal_dates(start_date, target_weekday, count):
    first = next_weekday_on_or_after(start_date, target_weekday)
    return [first + timedelta(days=7 * index) for index in range(count)]


def validate_password_complexity(password):
    if len(password) < 12:
        return "Password must be at least 12 characters long."
    if not any(char.islower() for char in password):
        return "Password must include at least one lowercase letter."
    if not any(char.isupper() for char in password):
        return "Password must include at least one uppercase letter."
    if not any(char.isdigit() for char in password):
        return "Password must include at least one number."
    if not any(not char.isalnum() for char in password):
        return "Password must include at least one special character."
    return None


def ordinal(day):
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


@app.template_filter("human_date")
def human_date(value):
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value
    weekday = {
        0: "Mon",
        1: "Tues",
        2: "Weds",
        3: "Thurs",
        4: "Fri",
        5: "Sat",
        6: "Sun",
    }[parsed.weekday()]
    return f"{weekday} {ordinal(parsed.day)} {parsed.strftime('%B %Y')}"


@app.template_filter("timezone_label")
def timezone_label(value):
    if not value:
        return DEFAULT_BAND_TIMEZONE
    return str(value).replace("_", " ")


@app.template_filter("time_label")
def time_label(value):
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return value
    return parsed.strftime("%H:%M")


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
            password_hash TEXT,
            calendar_token TEXT UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS email_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purpose TEXT NOT NULL,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            payload TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'Europe/London',
            rehearsal_enabled INTEGER NOT NULL DEFAULT 0,
            rehearsal_weekday INTEGER,
            rehearsal_location TEXT,
            rehearsal_start_time TEXT,
            rehearsal_end_time TEXT,
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
            is_regular INTEGER NOT NULL DEFAULT 1,
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
            location_url TEXT,
            notes TEXT,
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

        CREATE TABLE IF NOT EXISTS rehearsal_cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            rehearsal_date TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (band_id, rehearsal_date),
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rehearsal_unavailability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            rehearsal_date TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (band_id, rehearsal_date, user_id),
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rehearsal_player_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id INTEGER NOT NULL,
            rehearsal_date TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            is_included INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (band_id, rehearsal_date, user_id),
            FOREIGN KEY(band_id) REFERENCES bands(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_challenges_lookup ON email_challenges (purpose, email, created_at)"
    )
    user_columns = {row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "instruments_played" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN instruments_played TEXT")
    if "calendar_token" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN calendar_token TEXT")
    band_columns = {row[1] for row in cur.execute("PRAGMA table_info(bands)").fetchall()}
    if "timezone" not in band_columns:
        cur.execute(
            f"ALTER TABLE bands ADD COLUMN timezone TEXT NOT NULL DEFAULT '{DEFAULT_BAND_TIMEZONE}'"
        )
    if "rehearsal_enabled" not in band_columns:
        cur.execute("ALTER TABLE bands ADD COLUMN rehearsal_enabled INTEGER NOT NULL DEFAULT 0")
    if "rehearsal_weekday" not in band_columns:
        cur.execute("ALTER TABLE bands ADD COLUMN rehearsal_weekday INTEGER")
    if "rehearsal_location" not in band_columns:
        cur.execute("ALTER TABLE bands ADD COLUMN rehearsal_location TEXT")
    if "rehearsal_start_time" not in band_columns:
        cur.execute("ALTER TABLE bands ADD COLUMN rehearsal_start_time TEXT")
    if "rehearsal_end_time" not in band_columns:
        cur.execute("ALTER TABLE bands ADD COLUMN rehearsal_end_time TEXT")
    cur.execute(
        "UPDATE bands SET timezone = ? WHERE timezone IS NULL OR TRIM(timezone) = ''",
        (DEFAULT_BAND_TIMEZONE,),
    )
    cur.execute(
        """
        UPDATE bands
        SET rehearsal_enabled = 0
        WHERE rehearsal_enabled IS NULL
        """
    )
    membership_columns = {row[1] for row in cur.execute("PRAGMA table_info(band_memberships)").fetchall()}
    if "is_regular" not in membership_columns:
        cur.execute("ALTER TABLE band_memberships ADD COLUMN is_regular INTEGER NOT NULL DEFAULT 1")
    gig_columns = {row[1] for row in cur.execute("PRAGMA table_info(gigs)").fetchall()}
    if "title" not in gig_columns:
        cur.execute("ALTER TABLE gigs ADD COLUMN title TEXT")
    if "location_url" not in gig_columns:
        cur.execute("ALTER TABLE gigs ADD COLUMN location_url TEXT")
    if "notes" not in gig_columns:
        cur.execute("ALTER TABLE gigs ADD COLUMN notes TEXT")
    users_sql_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    users_sql = users_sql_row[0] if users_sql_row else ""
    if "password_hash TEXT NOT NULL" in users_sql:
        cur.executescript(
            """
            PRAGMA foreign_keys = OFF;

            ALTER TABLE users RENAME TO users_old;

            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                instruments_played TEXT,
                password_hash TEXT,
                calendar_token TEXT UNIQUE,
                created_at TEXT NOT NULL
            );

            INSERT INTO users (id, name, email, phone, instruments_played, password_hash, calendar_token, created_at)
            SELECT id, name, email, phone, instruments_played, password_hash, calendar_token, created_at
            FROM users_old;

            DROP TABLE users_old;

            PRAGMA foreign_keys = ON;
            """
        )

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


def get_regular_player_ids(db, band_id):
    rows = db.execute(
        """
        SELECT DISTINCT pd.user_id
        FROM part_defaults pd
        JOIN parts p ON p.id = pd.part_id
        WHERE p.band_id = ?
          AND pd.user_id IS NOT NULL
        """,
        (band_id,),
    ).fetchall()
    return {row["user_id"] for row in rows}


def parse_time_value(value):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def generate_calendar_token():
    return secrets.token_urlsafe(32)


def ensure_calendar_token(user_id):
    db = get_db()
    user = db.execute("SELECT calendar_token FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["calendar_token"]:
        return user["calendar_token"]

    token = generate_calendar_token()
    while db.execute("SELECT 1 FROM users WHERE calendar_token = ?", (token,)).fetchone():
        token = generate_calendar_token()
    db.execute("UPDATE users SET calendar_token = ? WHERE id = ?", (token, user_id))
    db.commit()
    return token


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
        current_band = db.execute(
            "SELECT id, name, timezone FROM bands WHERE id = ?",
            (band_id,),
        ).fetchone()
    return {
        "current_user": user,
        "current_band": current_band,
        "default_band_timezone": DEFAULT_BAND_TIMEZONE,
    }


def generate_email_challenge_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def delete_expired_email_challenges(db):
    db.execute("DELETE FROM email_challenges WHERE expires_at <= ?", (utc_now_iso(),))


def create_email_challenge(db, purpose, email, payload):
    delete_expired_email_challenges(db)
    code = generate_email_challenge_code()
    created_at = utc_now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=app.config["EMAIL_CHALLENGE_MAX_AGE"])).isoformat()
    db.execute("DELETE FROM email_challenges WHERE purpose = ? AND email = ?", (purpose, email))
    db.execute(
        """
        INSERT INTO email_challenges (purpose, email, code, payload, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (purpose, email, code, json.dumps(payload), expires_at, created_at),
    )
    db.commit()
    return code


def get_active_email_challenge(db, purpose, email):
    delete_expired_email_challenges(db)
    row = db.execute(
        """
        SELECT * FROM email_challenges
        WHERE purpose = ? AND email = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (purpose, email),
    ).fetchone()
    if not row:
        db.commit()
        return None
    expires_at = parse_iso_datetime(row["expires_at"])
    if expires_at is None or expires_at <= datetime.now(timezone.utc):
        db.execute("DELETE FROM email_challenges WHERE id = ?", (row["id"],))
        db.commit()
        return None
    return row


def consume_email_challenge(db, purpose, email, submitted_code):
    challenge = get_active_email_challenge(db, purpose, email)
    if not challenge:
        return None, "expired"
    expected_code = (challenge["code"] or "").strip().upper()
    received_code = (submitted_code or "").strip().upper()
    if not secrets.compare_digest(expected_code, received_code):
        return None, "invalid"
    db.execute("DELETE FROM email_challenges WHERE id = ?", (challenge["id"],))
    db.commit()
    return json.loads(challenge["payload"]), None


def send_email(subject, recipients, body):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app.config["MAIL_FROM"]
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    envelope_from = get_mail_envelope_from()

    with smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"]) as smtp:
        if app.config["SMTP_USE_TLS"]:
            smtp.starttls()
        if app.config["SMTP_USERNAME"]:
            smtp.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
        smtp.send_message(message, from_addr=envelope_from, to_addrs=recipients)


def get_mail_envelope_from():
    explicit_envelope = app.config["MAIL_ENVELOPE_FROM"].strip()
    if explicit_envelope:
        return explicit_envelope

    from_domain = app.config["MAIL_FROM_DOMAIN"].strip()
    header_from = app.config["MAIL_FROM"].strip()
    if from_domain and "@" in header_from:
        local_part = header_from.split("@", 1)[0]
        return f"{local_part}@{from_domain}"

    return header_from


def challenge_expiry_minutes():
    return max(1, app.config["EMAIL_CHALLENGE_MAX_AGE"] // 60)


def send_password_reset_email(user, code):
    body = (
        f"Hi {user['name']},\n\n"
        "A password reset was requested for your Gig Planner account.\n\n"
        f"Use this code to continue: {code}\n\n"
        f"This code expires in {challenge_expiry_minutes()} minutes.\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "If you have any problems, please email contact@gigplanner.uk.\n"
    )
    send_email("Gig Planner password reset", [user["email"]], body)


def send_registration_verification_email(name, email, code):
    body = (
        f"Hi {name},\n\n"
        "Please confirm your email address to finish creating your Gig Planner account.\n\n"
        f"Use this code to continue: {code}\n\n"
        f"This code expires in {challenge_expiry_minutes()} minutes.\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "If you have any problems, please email contact@gigplanner.uk.\n"
    )
    send_email("Gig Planner email verification", [email], body)


def render_register_template(error=None, success=None, form_data=None, code_sent=False):
    return render_template(
        "register.html",
        error=error,
        success=success,
        form_data=form_data or {},
        code_sent=code_sent,
        challenge_expires_minutes=challenge_expiry_minutes(),
        show_navbar=False,
    )


def render_forgot_password_template(error=None, success=None, email="", code_sent=False):
    return render_template(
        "forgot_password.html",
        error=error,
        success=success,
        email=email,
        code_sent=code_sent,
        challenge_expires_minutes=challenge_expiry_minutes(),
        show_navbar=False,
    )


def ical_escape(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


def ical_format_local(value):
    return value.strftime("%Y%m%dT%H%M%S")


def public_url(path):
    return f"{app.config['BASE_URL'].rstrip('/')}{path}"


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("welcome.html", show_navbar=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        action = request.form.get("action", "send_code")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        instruments = request.form.get("instruments_played", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        challenge_code = request.form.get("challenge_code", "").strip().upper()
        form_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "instruments_played": instruments,
        }
        db = get_db()
        exists = db.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if exists and exists["password_hash"]:
            return render_register_template(
                error=Markup(
                    f'An account with that email already exists. It was probably created for you by a band admin, so you can <a href="{url_for("forgot_password")}">reset your password here to claim the account</a>.'
                ),
                form_data=form_data,
            )

        if action == "verify_code":
            if not all([name, email, password, confirm_password, challenge_code]):
                return render_register_template(
                    error="Name, email, both password fields, and the verification code are required.",
                    form_data=form_data,
                    code_sent=True,
                )
            if password != confirm_password:
                return render_register_template(
                    error="The passwords do not match.",
                    form_data=form_data,
                    code_sent=True,
                )
            password_error = validate_password_complexity(password)
            if password_error:
                return render_register_template(
                    error=password_error,
                    form_data=form_data,
                    code_sent=True,
                )
            payload, error_type = consume_email_challenge(db, "registration", email, challenge_code)
            if error_type == "expired":
                return render_register_template(
                    error="That verification code has expired. Please request a new one.",
                    form_data=form_data,
                )
            if error_type == "invalid":
                return render_register_template(
                    error="That verification code is not valid.",
                    form_data=form_data,
                    code_sent=True,
                )
            if (
                not payload
                or payload.get("name") != name
                or payload.get("email") != email
                or (payload.get("phone") or "") != phone
                or (payload.get("instruments_played") or "") != instruments
            ):
                return render_register_template(
                    error="Those registration details do not match the code you requested. Please request a new code.",
                    form_data=form_data,
                )
            existing_user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if existing_user and existing_user["password_hash"]:
                return render_register_template(
                    error="This account has already been created. Please log in instead.",
                    form_data=form_data,
                )
            password_hash = generate_password_hash(password)
            if existing_user:
                db.execute(
                    """
                    UPDATE users
                    SET name = ?, phone = ?, instruments_played = ?, password_hash = ?
                    WHERE id = ?
                    """,
                    (
                        payload["name"],
                        payload["phone"],
                        payload["instruments_played"],
                        password_hash,
                        existing_user["id"],
                    ),
                )
            else:
                db.execute(
                    """
                    INSERT INTO users (name, email, phone, instruments_played, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["name"],
                        payload["email"],
                        payload["phone"],
                        payload["instruments_played"],
                        password_hash,
                        utc_now_iso(),
                    ),
                )
            db.commit()
            return redirect(url_for("login", registered="success"))

        if not all([name, email, password, confirm_password]):
            return render_register_template(
                error="Name, email, and both password fields are required.",
                form_data=form_data,
            )
        if password != confirm_password:
            return render_register_template(
                error="The passwords do not match.",
                form_data=form_data,
            )
        password_error = validate_password_complexity(password)
        if password_error:
            return render_register_template(error=password_error, form_data=form_data)

        try:
            code = create_email_challenge(
                db,
                "registration",
                email,
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "instruments_played": instruments,
                },
            )
            send_registration_verification_email(name, email, code)
        except Exception:
            return render_register_template(
                error="We could not send the verification email right now. Please try again later.",
                form_data=form_data,
            )
        return render_register_template(
            success="We’ve emailed you a 6-character verification code. Enter it below to finish creating your account.",
            form_data=form_data,
            code_sent=True,
        )
    return render_register_template()


@app.route("/verify-registration/<token>")
def verify_registration(token):
    return render_register_template(
        error="Registration links are no longer used. Please register again to receive a fresh verification code.",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    success_message = None
    if request.args.get("reset") == "success":
        success_message = "Your password has been set. You can now log in."
    elif request.args.get("registered") == "success":
        success_message = "Your email has been verified and your account is ready. You can now log in."
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            return render_template("login.html", error="Invalid email or password.", show_navbar=False)
        if not user["password_hash"]:
            return render_template(
                "login.html",
                error="This account has not been claimed yet. Use Reset your password to set a password.",
                show_navbar=False,
            )
        if not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.", show_navbar=False)
        session.clear()
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    return render_template("login.html", show_navbar=False, success=success_message)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        action = request.form.get("action", "send_code")
        email = request.form.get("email", "").strip().lower()
        challenge_code = request.form.get("challenge_code", "").strip().upper()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if action == "verify_code":
            if not all([email, challenge_code, password, confirm_password]):
                return render_forgot_password_template(
                    error="Email, the challenge code, and both password fields are required.",
                    email=email,
                    code_sent=True,
                )
            if password != confirm_password:
                return render_forgot_password_template(
                    error="The passwords do not match.",
                    email=email,
                    code_sent=True,
                )
            password_error = validate_password_complexity(password)
            if password_error:
                return render_forgot_password_template(
                    error=password_error,
                    email=email,
                    code_sent=True,
                )
            payload, error_type = consume_email_challenge(db, "password-reset", email, challenge_code)
            if error_type == "expired":
                return render_forgot_password_template(
                    error="That challenge code has expired. Request a new one to continue.",
                    email=email,
                )
            if error_type == "invalid":
                return render_forgot_password_template(
                    error="That challenge code is not valid.",
                    email=email,
                    code_sent=True,
                )
            user = db.execute(
                "SELECT * FROM users WHERE id = ? AND email = ?",
                (payload.get("user_id"), email),
            ).fetchone()
            if not user:
                return render_forgot_password_template(
                    error="That password reset request is no longer valid. Request a new code to continue.",
                    email=email,
                )
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(password), user["id"]),
            )
            db.commit()
            return redirect(url_for("login", reset="success"))

        try:
            if user:
                code = create_email_challenge(
                    db,
                    "password-reset",
                    email,
                    {"user_id": user["id"]},
                )
                send_password_reset_email(user, code)
        except Exception:
            return render_forgot_password_template(
                error="We could not send the reset email right now. Please try again later.",
                email=email,
            )
        return render_forgot_password_template(
            success="If we found an account for that email, we’ve sent a 6-character challenge code.",
            email=email,
            code_sent=True,
        )
    return render_forgot_password_template()


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    return render_forgot_password_template(
        error="Password reset links are no longer used. Request a new challenge code to continue.",
    )


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
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        db = get_db()
        if any([current_password, new_password, confirm_password]):
            if not current_password:
                return render_template("profile.html", user=user, error="Enter your current password to change it.")
            if not user["password_hash"] or not check_password_hash(user["password_hash"], current_password):
                return render_template("profile.html", user=user, error="Your current password is incorrect.")
            if not new_password:
                return render_template("profile.html", user=user, error="Enter a new password.")
            if new_password != confirm_password:
                return render_template("profile.html", user=user, error="The new passwords do not match.")
            password_error = validate_password_complexity(new_password)
            if password_error:
                return render_template("profile.html", user=user, error=password_error)
            db.execute(
                "UPDATE users SET phone = ?, instruments_played = ?, password_hash = ? WHERE id = ?",
                (phone, instruments, generate_password_hash(new_password), user["id"]),
            )
            db.commit()
            return render_template(
                "profile.html",
                user=db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone(),
                success="Your details and password were updated.",
            )
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
    calendar_token = ensure_calendar_token(user["id"])
    active_tab = request.args.get("tab", "gigs").strip().lower()
    if active_tab not in {"gigs", "rehearsals"}:
        active_tab = "gigs"
    gig_band_filter = request.args.get("gig_band_id", "").strip()
    rehearsal_band_filter = request.args.get("rehearsal_band_id", "").strip()
    selected_gig_band_id = None
    if gig_band_filter:
        try:
            selected_gig_band_id = int(gig_band_filter)
        except ValueError:
            selected_gig_band_id = None
    try:
        rehearsal_page = max(int(request.args.get("rehearsal_page", "1") or 1), 1)
    except ValueError:
        rehearsal_page = 1
    rehearsal_page_size = 8
    gig_query = """
        SELECT g.*, b.name AS band_name, b.timezone AS band_timezone,
               GROUP_CONCAT(gp.part_name, ', ') AS parts,
               COALESCE(av.status, 'Unanswered') AS availability_status
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        JOIN bands b ON b.id = g.band_id
        LEFT JOIN availability av ON av.gig_id = g.id AND av.user_id = ?
        WHERE gp.assigned_user_id = ?
    """
    gig_params = [user["id"], user["id"]]
    if selected_gig_band_id:
        gig_query += "\n          AND g.band_id = ?"
        gig_params.append(selected_gig_band_id)
    gig_query += """
        GROUP BY g.id
        ORDER BY g.gig_date ASC, g.start_time ASC
    """
    gigs = db.execute(gig_query, tuple(gig_params)).fetchall()
    gigs = filter_visible_gigs(gigs)
    gig_bands = db.execute(
        """
        SELECT DISTINCT b.id, b.name
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        JOIN bands b ON b.id = g.band_id
        WHERE gp.assigned_user_id = ?
        ORDER BY b.name
        """,
        (user["id"],),
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

    rehearsal_bands = db.execute(
        """
        SELECT b.id, b.name, b.rehearsal_weekday, b.rehearsal_location,
               b.rehearsal_start_time, b.rehearsal_end_time, b.timezone
        FROM bands b
        JOIN band_memberships bm ON bm.band_id = b.id
        WHERE bm.user_id = ?
          AND b.rehearsal_enabled = 1
          AND b.rehearsal_weekday IS NOT NULL
        ORDER BY b.name
        """,
        (user["id"],),
    ).fetchall()
    selected_rehearsal_band_id = None
    if rehearsal_band_filter:
        try:
            selected_rehearsal_band_id = int(rehearsal_band_filter)
        except ValueError:
            selected_rehearsal_band_id = None

    regular_memberships = db.execute(
        """
        SELECT DISTINCT p.band_id
        FROM part_defaults pd
        JOIN parts p ON p.id = pd.part_id
        WHERE pd.user_id = ?
        """,
        (user["id"],),
    ).fetchall()
    regular_by_band = {row["band_id"]: True for row in regular_memberships}
    today = date.today()
    horizon = 52
    rehearsal_rows = []
    for band in rehearsal_bands:
        if selected_rehearsal_band_id and band["id"] != selected_rehearsal_band_id:
            continue
        rehearsal_dates = generate_rehearsal_dates(today, int(band["rehearsal_weekday"]), horizon)
        for rehearsal_day in rehearsal_dates:
            rehearsal_rows.append(
                {
                    "band_id": band["id"],
                    "band_name": band["name"],
                    "rehearsal_date": rehearsal_day.isoformat(),
                    "rehearsal_location": band["rehearsal_location"] or "",
                    "rehearsal_start_time": band["rehearsal_start_time"] or "",
                    "rehearsal_end_time": band["rehearsal_end_time"] or "",
                    "band_timezone": band["timezone"] or DEFAULT_BAND_TIMEZONE,
                    "default_included": regular_by_band.get(band["id"], False),
                }
            )
    rehearsal_rows.sort(key=lambda row: row["rehearsal_date"])
    if rehearsal_rows:
        keys = {(row["band_id"], row["rehearsal_date"]) for row in rehearsal_rows}
        band_ids = sorted({band_id for band_id, _ in keys})
        min_date = min(rehearsal_date for _, rehearsal_date in keys)
        max_date = max(rehearsal_date for _, rehearsal_date in keys)
        cancellation_rows = db.execute(
            """
            SELECT band_id, rehearsal_date
            FROM rehearsal_cancellations
            WHERE band_id IN ({placeholders}) AND rehearsal_date BETWEEN ? AND ?
            """.format(placeholders=",".join(["?"] * len(band_ids))),
            (*band_ids, min_date, max_date),
        ).fetchall()
        cancelled_set = {(row["band_id"], row["rehearsal_date"]) for row in cancellation_rows}
        unavailability_rows = db.execute(
            """
            SELECT band_id, rehearsal_date
            FROM rehearsal_unavailability
            WHERE user_id = ?
              AND band_id IN ({placeholders})
              AND rehearsal_date BETWEEN ? AND ?
            """.format(placeholders=",".join(["?"] * len(band_ids))),
            (user["id"], *band_ids, min_date, max_date),
        ).fetchall()
        unavailable_set = {(row["band_id"], row["rehearsal_date"]) for row in unavailability_rows}
        override_rows = db.execute(
            """
            SELECT band_id, rehearsal_date, is_included
            FROM rehearsal_player_overrides
            WHERE user_id = ?
              AND band_id IN ({placeholders})
              AND rehearsal_date BETWEEN ? AND ?
            """.format(placeholders=",".join(["?"] * len(band_ids))),
            (user["id"], *band_ids, min_date, max_date),
        ).fetchall()
        override_map = {
            (row["band_id"], row["rehearsal_date"]): bool(row["is_included"]) for row in override_rows
        }
        for row in rehearsal_rows:
            key = (row["band_id"], row["rehearsal_date"])
            row["is_cancelled"] = key in cancelled_set
            is_included = override_map.get(key, row["default_included"])
            row["is_included"] = is_included
            row["availability_status"] = "Not Available" if key in unavailable_set else "Available"
        rehearsal_rows = [row for row in rehearsal_rows if row["is_included"]]

    start_index = (rehearsal_page - 1) * rehearsal_page_size
    end_index = start_index + rehearsal_page_size
    paged_rehearsals = rehearsal_rows[start_index:end_index]
    has_more_rehearsals = end_index < len(rehearsal_rows)
    return render_template(
        "dashboard.html",
        active_tab=active_tab,
        gigs=gigs,
        gig_bands=gig_bands,
        selected_gig_band_id=selected_gig_band_id,
        rehearsals=paged_rehearsals,
        rehearsal_bands=rehearsal_bands,
        rehearsal_page=rehearsal_page,
        has_more_rehearsals=has_more_rehearsals,
        selected_rehearsal_band_id=selected_rehearsal_band_id,
        admin_bands=admin_bands,
        calendar_feed_url=url_for("calendar_feed_guide"),
        calendar_subscription_url=public_url(url_for("user_calendar_feed", token=calendar_token)),
    )


@app.route("/calendar-feed")
@login_required
def calendar_feed_guide():
    user = current_user()
    token = ensure_calendar_token(user["id"])
    return render_template(
        "calendar_feed.html",
        calendar_subscription_url=public_url(url_for("user_calendar_feed", token=token)),
    )


@app.route("/calendar/<token>.ics")
def user_calendar_feed(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE calendar_token = ?", (token,)).fetchone()
    if not user:
        return Response("Calendar not found.", status=404, mimetype="text/plain")

    gigs = db.execute(
        """
        SELECT g.*, b.name AS band_name, b.timezone AS band_timezone,
               GROUP_CONCAT(gp.part_name, ', ') AS parts,
               COALESCE(av.status, 'Unanswered') AS availability_status
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        JOIN bands b ON b.id = g.band_id
        LEFT JOIN availability av ON av.gig_id = g.id AND av.user_id = ?
        WHERE gp.assigned_user_id = ?
          AND COALESCE(av.status, 'Unanswered') != 'Not Available'
        GROUP BY g.id
        ORDER BY g.gig_date ASC, g.start_time ASC
        """,
        (user["id"], user["id"]),
    ).fetchall()
    rehearsal_bands = db.execute(
        """
        SELECT b.id, b.name, b.rehearsal_weekday, b.rehearsal_location,
               b.rehearsal_start_time, b.rehearsal_end_time, b.timezone
        FROM bands b
        JOIN band_memberships bm ON bm.band_id = b.id
        WHERE bm.user_id = ?
          AND b.rehearsal_enabled = 1
          AND b.rehearsal_weekday IS NOT NULL
        ORDER BY b.name
        """,
        (user["id"],),
    ).fetchall()
    regular_memberships = db.execute(
        """
        SELECT DISTINCT p.band_id
        FROM part_defaults pd
        JOIN parts p ON p.id = pd.part_id
        WHERE pd.user_id = ?
        """,
        (user["id"],),
    ).fetchall()
    regular_by_band = {row["band_id"]: True for row in regular_memberships}
    rehearsal_rows = []
    rehearsal_horizon = 52
    for band in rehearsal_bands:
        rehearsal_dates = generate_rehearsal_dates(date.today(), int(band["rehearsal_weekday"]), rehearsal_horizon)
        for rehearsal_day in rehearsal_dates:
            rehearsal_rows.append(
                {
                    "band_id": band["id"],
                    "band_name": band["name"],
                    "rehearsal_date": rehearsal_day.isoformat(),
                    "rehearsal_location": band["rehearsal_location"] or "",
                    "rehearsal_start_time": band["rehearsal_start_time"] or "",
                    "rehearsal_end_time": band["rehearsal_end_time"] or "",
                    "band_timezone": band["timezone"] or DEFAULT_BAND_TIMEZONE,
                    "default_included": regular_by_band.get(band["id"], False),
                }
            )
    rehearsal_rows.sort(key=lambda row: row["rehearsal_date"])
    if rehearsal_rows:
        keys = {(row["band_id"], row["rehearsal_date"]) for row in rehearsal_rows}
        band_ids = sorted({band_id for band_id, _ in keys})
        min_date = min(rehearsal_date for _, rehearsal_date in keys)
        max_date = max(rehearsal_date for _, rehearsal_date in keys)
        placeholders = ",".join(["?"] * len(band_ids))
        cancellation_rows = db.execute(
            f"""
            SELECT band_id, rehearsal_date
            FROM rehearsal_cancellations
            WHERE band_id IN ({placeholders}) AND rehearsal_date BETWEEN ? AND ?
            """,
            (*band_ids, min_date, max_date),
        ).fetchall()
        cancelled_set = {(row["band_id"], row["rehearsal_date"]) for row in cancellation_rows}
        unavailability_rows = db.execute(
            f"""
            SELECT band_id, rehearsal_date
            FROM rehearsal_unavailability
            WHERE user_id = ?
              AND band_id IN ({placeholders})
              AND rehearsal_date BETWEEN ? AND ?
            """,
            (user["id"], *band_ids, min_date, max_date),
        ).fetchall()
        unavailable_set = {(row["band_id"], row["rehearsal_date"]) for row in unavailability_rows}
        override_rows = db.execute(
            f"""
            SELECT band_id, rehearsal_date, is_included
            FROM rehearsal_player_overrides
            WHERE user_id = ?
              AND band_id IN ({placeholders})
              AND rehearsal_date BETWEEN ? AND ?
            """,
            (user["id"], *band_ids, min_date, max_date),
        ).fetchall()
        override_map = {
            (row["band_id"], row["rehearsal_date"]): bool(row["is_included"]) for row in override_rows
        }
        for row in rehearsal_rows:
            key = (row["band_id"], row["rehearsal_date"])
            row["is_cancelled"] = key in cancelled_set
            row["is_included"] = override_map.get(key, row["default_included"])
            row["availability_status"] = "Not Available" if key in unavailable_set else "Available"
        rehearsal_rows = [
            row
            for row in rehearsal_rows
            if row["is_included"] and row["availability_status"] != "Not Available"
        ]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gig Planner//Gig Planner Calendar//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{ical_escape(user['name'] + ' - Gig Planner')}",
        "X-PUBLISHED-TTL:PT6H",
    ]

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for gig in gigs:
        start_dt = datetime.strptime(f"{gig['gig_date']} {gig['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{gig['gig_date']} {gig['end_time']}", "%Y-%m-%d %H:%M")
        band_timezone = normalize_band_timezone(gig["band_timezone"]) or DEFAULT_BAND_TIMEZONE
        summary_target = gig["title"] or gig["location"]
        summary = f"{gig['band_name']} - {summary_target}"
        description_parts = []
        if gig["parts"]:
            description_parts.append(f"Your parts: {gig['parts']}")
        if gig["status"]:
            description_parts.append(f"Status: {gig['status']}")
        if gig["notes"]:
            description_parts.append(f"Notes: {gig['notes']}")
        description = "\\n".join(description_parts)

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:gig-{gig['id']}-user-{user['id']}@gigplanner.uk",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;TZID={ical_escape(band_timezone)}:{ical_format_local(start_dt)}",
                f"DTEND;TZID={ical_escape(band_timezone)}:{ical_format_local(end_dt)}",
                f"SUMMARY:{ical_escape(summary)}",
                f"LOCATION:{ical_escape(gig['location'])}",
                f"DESCRIPTION:{ical_escape(description)}",
                "END:VEVENT",
            ]
        )

    for rehearsal in rehearsal_rows:
        band_timezone = normalize_band_timezone(rehearsal["band_timezone"]) or DEFAULT_BAND_TIMEZONE
        summary = f"{rehearsal['band_name']} Rehearsal"
        if rehearsal["is_cancelled"]:
            summary = f"{summary} (Cancelled)"
        has_times = bool(rehearsal["rehearsal_start_time"] and rehearsal["rehearsal_end_time"])
        description_parts = [f"Availability: {rehearsal['availability_status']}"]
        if has_times:
            description_parts.append(
                f"Time: {rehearsal['rehearsal_start_time']} - {rehearsal['rehearsal_end_time']}"
            )
        else:
            description_parts.append("Time: Not configured")
        if rehearsal["rehearsal_location"]:
            description_parts.insert(0, f"Location: {rehearsal['rehearsal_location']}")
        description = "\\n".join(description_parts)

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:rehearsal-{rehearsal['band_id']}-{rehearsal['rehearsal_date']}-user-{user['id']}@gigplanner.uk",
            f"DTSTAMP:{now_stamp}",
            f"SUMMARY:{ical_escape(summary)}",
            f"LOCATION:{ical_escape(rehearsal['rehearsal_location'])}",
            f"DESCRIPTION:{ical_escape(description)}",
        ]
        if has_times:
            start_dt = datetime.strptime(
                f"{rehearsal['rehearsal_date']} {rehearsal['rehearsal_start_time']}",
                "%Y-%m-%d %H:%M",
            )
            end_dt = datetime.strptime(
                f"{rehearsal['rehearsal_date']} {rehearsal['rehearsal_end_time']}",
                "%Y-%m-%d %H:%M",
            )
            event_lines.extend(
                [
                    f"DTSTART;TZID={ical_escape(band_timezone)}:{ical_format_local(start_dt)}",
                    f"DTEND;TZID={ical_escape(band_timezone)}:{ical_format_local(end_dt)}",
                ]
            )
        else:
            rehearsal_date = datetime.strptime(rehearsal["rehearsal_date"], "%Y-%m-%d").date()
            next_day = rehearsal_date + timedelta(days=1)
            event_lines.extend(
                [
                    f"DTSTART;VALUE=DATE:{rehearsal_date.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}",
                ]
            )
        if rehearsal["is_cancelled"]:
            event_lines.append("STATUS:CANCELLED")
        event_lines.append("END:VEVENT")
        lines.extend(event_lines)

    lines.append("END:VCALENDAR")
    return Response(
        "\r\n".join(lines) + "\r\n",
        mimetype="text/calendar",
        headers={
            "Content-Disposition": 'inline; filename="gigplanner.ics"',
            "Cache-Control": "no-cache, max-age=0",
        },
    )


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
        (gig_id, user["id"], status, utc_now_iso()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/band/create", methods=["GET", "POST"])
@login_required
def create_band():
    selected_timezone = DEFAULT_BAND_TIMEZONE
    rehearsal_enabled = False
    rehearsal_weekday = None
    rehearsal_location = ""
    rehearsal_start_time = ""
    rehearsal_end_time = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected_timezone = request.form.get("timezone", "")
        rehearsal_enabled = request.form.get("rehearsal_enabled") == "on"
        rehearsal_weekday = parse_weekday(request.form.get("rehearsal_weekday"))
        rehearsal_location = request.form.get("rehearsal_location", "").strip()
        rehearsal_start_time = (request.form.get("rehearsal_start_time") or "").strip()
        rehearsal_end_time = (request.form.get("rehearsal_end_time") or "").strip()
        parsed_rehearsal_start_time = parse_time_value(rehearsal_start_time)
        parsed_rehearsal_end_time = parse_time_value(rehearsal_end_time)
        timezone_name = normalize_band_timezone(selected_timezone)
        if not name:
            return render_template(
                "create_band.html",
                error="Band name is required.",
                timezone_options=TIMEZONE_OPTIONS,
                selected_timezone=selected_timezone,
                weekday_options=WEEKDAY_OPTIONS,
                rehearsal_enabled=rehearsal_enabled,
                rehearsal_weekday=rehearsal_weekday,
                rehearsal_location=rehearsal_location,
                rehearsal_start_time=rehearsal_start_time,
                rehearsal_end_time=rehearsal_end_time,
            )
        if not timezone_name:
            return render_template(
                "create_band.html",
                error="Please choose a valid timezone for the band.",
                timezone_options=TIMEZONE_OPTIONS,
                selected_timezone=selected_timezone,
                weekday_options=WEEKDAY_OPTIONS,
                rehearsal_enabled=rehearsal_enabled,
                rehearsal_weekday=rehearsal_weekday,
                rehearsal_location=rehearsal_location,
                rehearsal_start_time=rehearsal_start_time,
                rehearsal_end_time=rehearsal_end_time,
            )
        if rehearsal_enabled and rehearsal_weekday is None:
            return render_template(
                "create_band.html",
                error="Choose a rehearsal day of the week when rehearsals are enabled.",
                timezone_options=TIMEZONE_OPTIONS,
                selected_timezone=selected_timezone,
                weekday_options=WEEKDAY_OPTIONS,
                rehearsal_enabled=rehearsal_enabled,
                rehearsal_weekday=rehearsal_weekday,
                rehearsal_location=rehearsal_location,
                rehearsal_start_time=rehearsal_start_time,
                rehearsal_end_time=rehearsal_end_time,
            )
        if rehearsal_enabled and (parsed_rehearsal_start_time is None or parsed_rehearsal_end_time is None):
            return render_template(
                "create_band.html",
                error="Choose valid rehearsal start and end times when rehearsals are enabled.",
                timezone_options=TIMEZONE_OPTIONS,
                selected_timezone=selected_timezone,
                weekday_options=WEEKDAY_OPTIONS,
                rehearsal_enabled=rehearsal_enabled,
                rehearsal_weekday=rehearsal_weekday,
                rehearsal_location=rehearsal_location,
                rehearsal_start_time=rehearsal_start_time,
                rehearsal_end_time=rehearsal_end_time,
            )
        if rehearsal_enabled and parsed_rehearsal_start_time >= parsed_rehearsal_end_time:
            return render_template(
                "create_band.html",
                error="Rehearsal end time must be later than the start time.",
                timezone_options=TIMEZONE_OPTIONS,
                selected_timezone=selected_timezone,
                weekday_options=WEEKDAY_OPTIONS,
                rehearsal_enabled=rehearsal_enabled,
                rehearsal_weekday=rehearsal_weekday,
                rehearsal_location=rehearsal_location,
                rehearsal_start_time=rehearsal_start_time,
                rehearsal_end_time=rehearsal_end_time,
            )
        db = get_db()
        uid = session["user_id"]
        cur = db.execute(
            """
            INSERT INTO bands (
                name, timezone, rehearsal_enabled, rehearsal_weekday, rehearsal_location,
                rehearsal_start_time, rehearsal_end_time, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                timezone_name,
                1 if rehearsal_enabled else 0,
                rehearsal_weekday if rehearsal_enabled else None,
                rehearsal_location if rehearsal_enabled else "",
                parsed_rehearsal_start_time if rehearsal_enabled else None,
                parsed_rehearsal_end_time if rehearsal_enabled else None,
                uid,
                utc_now_iso(),
            ),
        )
        band_id = cur.lastrowid
        db.execute("INSERT INTO band_admins (band_id, user_id) VALUES (?, ?)", (band_id, uid))
        db.execute(
            "INSERT INTO band_memberships (band_id, user_id, instruments_played, is_co_admin) VALUES (?, ?, ?, 1)",
            (band_id, uid, "",),
        )
        db.commit()
        return redirect(url_for("band_setup", band_id=band_id))
    return render_template(
        "create_band.html",
        timezone_options=TIMEZONE_OPTIONS,
        selected_timezone=selected_timezone,
        weekday_options=WEEKDAY_OPTIONS,
        rehearsal_enabled=rehearsal_enabled,
        rehearsal_weekday=rehearsal_weekday,
        rehearsal_location=rehearsal_location,
        rehearsal_start_time=rehearsal_start_time,
        rehearsal_end_time=rehearsal_end_time,
    )


@app.route("/band/<int:band_id>/setup/complete")
@login_required
def complete_band_setup(band_id):
    if not is_band_admin(band_id, session["user_id"]):
        return redirect(url_for("dashboard"))
    return redirect(url_for("band_admin", band_id=band_id))


@app.route("/band/<int:band_id>/edit", methods=["GET", "POST"])
@login_required
def edit_band(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return redirect(url_for("dashboard"))

    db = get_db()
    band = db.execute("SELECT * FROM bands WHERE id = ?", (band_id,)).fetchone()
    if not band:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected_timezone = request.form.get("timezone", "")
        rehearsal_enabled = request.form.get("rehearsal_enabled") == "on"
        rehearsal_weekday = parse_weekday(request.form.get("rehearsal_weekday"))
        rehearsal_location = request.form.get("rehearsal_location", "").strip()
        rehearsal_start_time = (request.form.get("rehearsal_start_time") or "").strip()
        rehearsal_end_time = (request.form.get("rehearsal_end_time") or "").strip()
        parsed_rehearsal_start_time = parse_time_value(rehearsal_start_time)
        parsed_rehearsal_end_time = parse_time_value(rehearsal_end_time)
        timezone_name = normalize_band_timezone(selected_timezone)
        if not name:
            error = "Band name is required."
        elif not timezone_name:
            error = "Please choose a valid timezone for the band."
        elif rehearsal_enabled and rehearsal_weekday is None:
            error = "Choose a rehearsal day of the week when rehearsals are enabled."
        elif rehearsal_enabled and (parsed_rehearsal_start_time is None or parsed_rehearsal_end_time is None):
            error = "Choose valid rehearsal start and end times when rehearsals are enabled."
        elif rehearsal_enabled and parsed_rehearsal_start_time >= parsed_rehearsal_end_time:
            error = "Rehearsal end time must be later than the start time."
        else:
            db.execute(
                """
                UPDATE bands
                SET name = ?, timezone = ?, rehearsal_enabled = ?, rehearsal_weekday = ?, rehearsal_location = ?,
                    rehearsal_start_time = ?, rehearsal_end_time = ?
                WHERE id = ?
                """,
                (
                    name,
                    timezone_name,
                    1 if rehearsal_enabled else 0,
                    rehearsal_weekday if rehearsal_enabled else None,
                    rehearsal_location if rehearsal_enabled else "",
                    parsed_rehearsal_start_time if rehearsal_enabled else None,
                    parsed_rehearsal_end_time if rehearsal_enabled else None,
                    band_id,
                ),
            )
            db.commit()
            return redirect(url_for("dashboard"))
        band = {
            **dict(band),
            "name": name,
            "timezone": selected_timezone,
            "rehearsal_enabled": 1 if rehearsal_enabled else 0,
            "rehearsal_weekday": rehearsal_weekday,
            "rehearsal_location": rehearsal_location,
            "rehearsal_start_time": rehearsal_start_time,
            "rehearsal_end_time": rehearsal_end_time,
        }

    return render_template(
        "edit_band.html",
        band=band,
        error=error,
        timezone_options=TIMEZONE_OPTIONS,
        weekday_options=WEEKDAY_OPTIONS,
    )


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
        SELECT bm.user_id, bm.is_co_admin, u.name, u.email, u.phone,
               COALESCE(NULLIF(bm.instruments_played, ''), u.instruments_played, '') AS instruments_played
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    return render_template(
        "band_setup.html",
        band=band,
        parts=parts,
        players=players,
        weekday_options=WEEKDAY_OPTIONS,
        timezone_options=TIMEZONE_OPTIONS,
    )


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


@app.route("/api/band/<int:band_id>/name", methods=["POST"])
@login_required
def update_band_name(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403

    payload = request.json or {}
    name = payload.get("name", "").strip()
    timezone_name = normalize_band_timezone(payload.get("timezone"))
    if not name:
        return jsonify({"ok": False, "error": "Band name is required"}), 400
    if not timezone_name:
        return jsonify({"ok": False, "error": "Please choose a valid timezone for the band"}), 400

    db = get_db()
    band = db.execute("SELECT id FROM bands WHERE id = ?", (band_id,)).fetchone()
    if not band:
        return jsonify({"ok": False, "error": "Band not found"}), 404

    db.execute("UPDATE bands SET name = ?, timezone = ? WHERE id = ?", (name, timezone_name, band_id))
    db.commit()
    return jsonify({"ok": True, "name": name, "timezone": timezone_name})


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
        cur = db.execute(
            """
            INSERT INTO users (name, email, phone, instruments_played, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, phone, instruments, None, utc_now_iso()),
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
    db.execute(
        "DELETE FROM rehearsal_unavailability WHERE band_id = ? AND user_id = ?",
        (band_id, user_id),
    )
    db.execute(
        "DELETE FROM rehearsal_player_overrides WHERE band_id = ? AND user_id = ?",
        (band_id, user_id),
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


@app.route("/api/band/<int:band_id>/rehearsal-settings", methods=["POST"])
@login_required
def update_rehearsal_settings(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403
    enabled = bool(request.json.get("enabled"))
    weekday = parse_weekday(request.json.get("weekday"))
    location = (request.json.get("location") or "").strip()
    start_time = parse_time_value(request.json.get("start_time"))
    end_time = parse_time_value(request.json.get("end_time"))
    if enabled and weekday is None:
        return jsonify({"ok": False, "error": "Weekday is required when rehearsals are enabled."}), 400
    if enabled and (start_time is None or end_time is None):
        return jsonify({"ok": False, "error": "Start and end times are required when rehearsals are enabled."}), 400
    if enabled and start_time >= end_time:
        return jsonify({"ok": False, "error": "Rehearsal end time must be later than the start time."}), 400
    db = get_db()
    db.execute(
        """
        UPDATE bands
        SET rehearsal_enabled = ?, rehearsal_weekday = ?, rehearsal_location = ?,
            rehearsal_start_time = ?, rehearsal_end_time = ?
        WHERE id = ?
        """,
        (
            1 if enabled else 0,
            weekday if enabled else None,
            location if enabled else "",
            start_time if enabled else None,
            end_time if enabled else None,
            band_id,
        ),
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
    gig_rows = db.execute(
        """
        SELECT g.*,
               SUM(CASE WHEN assigned_players.user_id IS NOT NULL AND COALESCE(av.status, 'Unanswered') = 'Available' THEN 1 ELSE 0 END) AS available_count,
               SUM(CASE WHEN assigned_players.user_id IS NOT NULL AND COALESCE(av.status, 'Unanswered') = 'Not Available' THEN 1 ELSE 0 END) AS not_available_count,
               SUM(CASE WHEN assigned_players.user_id IS NOT NULL AND COALESCE(av.status, 'Unanswered') = 'Unsure yet' THEN 1 ELSE 0 END) AS unsure_count,
               SUM(CASE WHEN assigned_players.user_id IS NOT NULL AND COALESCE(av.status, 'Unanswered') = 'Unanswered' THEN 1 ELSE 0 END) AS unanswered_count
        FROM gigs g
        LEFT JOIN (
            SELECT DISTINCT gig_id, assigned_user_id AS user_id
            FROM gig_parts
            WHERE assigned_user_id IS NOT NULL
        ) assigned_players ON assigned_players.gig_id = g.id
        LEFT JOIN availability av ON av.gig_id = g.id AND av.user_id = assigned_players.user_id
        WHERE g.band_id = ?
        GROUP BY g.id
        ORDER BY g.gig_date ASC, g.start_time ASC
        """,
        (band_id,),
    ).fetchall()
    gig_assignee_rows = db.execute(
        """
        SELECT gp.gig_id, u.email
        FROM gig_parts gp
        JOIN users u ON u.id = gp.assigned_user_id
        JOIN gigs g ON g.id = gp.gig_id
        WHERE g.band_id = ?
          AND gp.assigned_user_id IS NOT NULL
          AND COALESCE(TRIM(u.email), '') <> ''
        """,
        (band_id,),
    ).fetchall()
    gig_emails_by_id = {}
    for row in gig_assignee_rows:
        gig_emails_by_id.setdefault(row["gig_id"], set()).add(row["email"].strip())
    whole_band_email_rows = db.execute(
        """
        SELECT DISTINCT u.email
        FROM parts p
        JOIN part_defaults pd ON pd.part_id = p.id
        JOIN users u ON u.id = pd.user_id
        WHERE p.band_id = ?
          AND pd.user_id IS NOT NULL
          AND COALESCE(TRIM(u.email), '') <> ''
        """,
        (band_id,),
    ).fetchall()
    whole_band_mailto = build_mailto_link(
        f"[GigPlanner] {band['name']}",
        [row["email"] for row in whole_band_email_rows],
    )
    band_timezone = band["timezone"] or DEFAULT_BAND_TIMEZONE
    today_in_band_timezone = band_local_today(band_timezone)
    previous_gig_cutoff = years_before(today_in_band_timezone, 2)
    gigs = []
    previous_gigs = []
    for gig_row in gig_rows:
        gig = dict(gig_row)
        gig_name = gig["title"] or gig["location"] or f"Gig {gig['id']}"
        gig["email_players_mailto"] = build_mailto_link(
            f"[GigPlanner] {band['name']} - {gig_name}",
            gig_emails_by_id.get(gig["id"], set()),
        )
        gig_date = parse_iso_date(gig["gig_date"])
        if not gig_date:
            continue
        if gig_date >= today_in_band_timezone:
            gigs.append(gig)
        elif gig_date >= previous_gig_cutoff:
            previous_gigs.append(gig)
    previous_gigs.sort(key=lambda gig: (gig["gig_date"], gig["start_time"] or ""), reverse=True)
    players = db.execute(
        """
        SELECT u.id, u.name,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM part_defaults pd
                   JOIN parts p ON p.id = pd.part_id
                   WHERE p.band_id = bm.band_id
                     AND pd.user_id = u.id
               ) THEN 1 ELSE 0 END AS is_regular
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    parts = db.execute("SELECT * FROM parts WHERE band_id = ? ORDER BY name", (band_id,)).fetchall()
    rehearsal_rows = []
    has_rehearsals = band["rehearsal_enabled"] and band["rehearsal_weekday"] is not None
    if has_rehearsals:
        rehearsal_dates = generate_rehearsal_dates(date.today(), int(band["rehearsal_weekday"]), 12)
        date_values = [entry.isoformat() for entry in rehearsal_dates]
        placeholders = ",".join(["?"] * len(date_values))
        regular_player_ids = get_regular_player_ids(db, band_id)
        cancellations = db.execute(
            f"""
            SELECT rehearsal_date
            FROM rehearsal_cancellations
            WHERE band_id = ? AND rehearsal_date IN ({placeholders})
            """,
            (band_id, *date_values),
        ).fetchall()
        cancellation_set = {row["rehearsal_date"] for row in cancellations}
        override_rows = db.execute(
            f"""
            SELECT rehearsal_date,
                   SUM(CASE WHEN is_included = 1 THEN 1 ELSE 0 END) AS added_count,
                   SUM(CASE WHEN is_included = 0 THEN 1 ELSE 0 END) AS removed_count
            FROM rehearsal_player_overrides
            WHERE band_id = ? AND rehearsal_date IN ({placeholders})
            GROUP BY rehearsal_date
            """,
            (band_id, *date_values),
        ).fetchall()
        override_map = {
            row["rehearsal_date"]: {"added_count": row["added_count"], "removed_count": row["removed_count"]}
            for row in override_rows
        }
        detail_override_rows = db.execute(
            f"""
            SELECT rehearsal_date, user_id, is_included
            FROM rehearsal_player_overrides
            WHERE band_id = ? AND rehearsal_date IN ({placeholders})
            """,
            (band_id, *date_values),
        ).fetchall()
        included_players_by_date = {rehearsal_date: set(regular_player_ids) for rehearsal_date in date_values}
        for row in detail_override_rows:
            scheduled_players = included_players_by_date.setdefault(row["rehearsal_date"], set(regular_player_ids))
            if row["is_included"]:
                scheduled_players.add(row["user_id"])
            else:
                scheduled_players.discard(row["user_id"])
        unavailable_rows = db.execute(
            f"""
            SELECT rehearsal_date, user_id
            FROM rehearsal_unavailability
            WHERE band_id = ? AND rehearsal_date IN ({placeholders})
            """,
            (band_id, *date_values),
        ).fetchall()
        unavailable_by_date = {}
        for row in unavailable_rows:
            unavailable_by_date.setdefault(row["rehearsal_date"], set()).add(row["user_id"])
        for rehearsal_date in date_values:
            counts = override_map.get(rehearsal_date, {"added_count": 0, "removed_count": 0})
            scheduled_players = included_players_by_date.get(rehearsal_date, set(regular_player_ids))
            unavailable_players = unavailable_by_date.get(rehearsal_date, set())
            not_available_count = sum(1 for user_id in scheduled_players if user_id in unavailable_players)
            available_count = len(scheduled_players) - not_available_count
            rehearsal_rows.append(
                {
                    "rehearsal_date": rehearsal_date,
                    "is_cancelled": rehearsal_date in cancellation_set,
                    "added_count": counts["added_count"] or 0,
                    "removed_count": counts["removed_count"] or 0,
                    "available_count": available_count,
                    "not_available_count": not_available_count,
                }
            )
    return render_template(
        "band_admin.html",
        band=band,
        has_rehearsals=has_rehearsals,
        gigs=gigs,
        previous_gigs=previous_gigs,
        whole_band_mailto=whole_band_mailto,
        rehearsals=rehearsal_rows,
        players=[dict(player) for player in players],
        parts=parts,
        weekday_options=WEEKDAY_OPTIONS,
    )


@app.route("/band/<int:band_id>/gig/<int:gig_id>/responses")
@login_required
def gig_responses_page(band_id, gig_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return redirect(url_for("dashboard"))

    db = get_db()
    gig = db.execute(
        """
        SELECT g.*, b.name AS band_name, b.timezone AS band_timezone
        FROM gigs g
        JOIN bands b ON b.id = g.band_id
        WHERE g.id = ? AND g.band_id = ?
        """,
        (gig_id, band_id),
    ).fetchone()
    if not gig:
        return redirect(url_for("band_admin", band_id=band_id))

    responses = db.execute(
        """
        SELECT u.id AS user_id,
               u.name AS player_name,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM gig_parts gp2
                   WHERE gp2.gig_id = ?
                     AND gp2.assigned_user_id = u.id
               ) THEN 1 ELSE 0 END AS is_assigned,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM part_defaults pd
                   JOIN parts p ON p.id = pd.part_id
                   WHERE p.band_id = bm.band_id
                     AND pd.user_id = u.id
               ) THEN 1 ELSE 0 END AS is_regular,
               COALESCE(av.status, 'Unanswered') AS availability_status,
               av.updated_at
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        LEFT JOIN availability av ON av.gig_id = ? AND av.user_id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (gig_id, gig_id, band_id),
    ).fetchall()
    part_rows = db.execute(
        """
        SELECT gp.id,
               gp.part_name,
               gp.assigned_user_id,
               u.name AS assigned_user_name,
               COALESCE(av.status, 'Unanswered') AS availability_status,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM part_defaults pd
                   JOIN parts p ON p.id = pd.part_id
                   WHERE p.band_id = g.band_id
                     AND pd.user_id = gp.assigned_user_id
               ) THEN 1 ELSE 0 END AS assigned_user_is_regular
        FROM gig_parts gp
        JOIN gigs g ON g.id = gp.gig_id
        LEFT JOIN users u ON u.id = gp.assigned_user_id
        LEFT JOIN availability av ON av.gig_id = gp.gig_id AND av.user_id = gp.assigned_user_id
        WHERE gp.gig_id = ?
        ORDER BY gp.part_name
        """,
        (gig_id,),
    ).fetchall()
    band_players = db.execute(
        """
        SELECT u.id, u.name,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM part_defaults pd
                   JOIN parts p ON p.id = pd.part_id
                   WHERE p.band_id = bm.band_id
                     AND pd.user_id = u.id
               ) THEN 1 ELSE 0 END AS is_regular
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    summary = {
        "available": 0,
        "not_available": 0,
        "unsure": 0,
        "unanswered": 0,
    }
    for response in responses:
        status = response["availability_status"]
        if status == "Available":
            summary["available"] += 1
        elif status == "Not Available":
            summary["not_available"] += 1
        elif status == "Unsure yet":
            summary["unsure"] += 1
        else:
            summary["unanswered"] += 1
    response_rows = [dict(response) for response in responses]
    return render_template(
        "gig_responses.html",
        band_id=band_id,
        gig=gig,
        responses=responses,
        response_rows=response_rows,
        parts=part_rows,
        players=[dict(player) for player in band_players],
        response_options=["Unanswered", "Available", "Not Available", "Unsure yet"],
        summary=summary,
    )


@app.route("/api/band/<int:band_id>/gig", methods=["POST"])
@login_required
def create_gig(band_id):
    uid = session["user_id"]
    if not is_band_admin(band_id, uid):
        return jsonify({"ok": False}), 403
    data = request.json
    required = ["gig_date", "start_time", "end_time", "status"]
    if not all(data.get(k) for k in required):
        return jsonify({"ok": False, "error": "Missing required fields"}), 400
    location = (data.get("location") or "").strip() or DEFAULT_GIG_LOCATION

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO gigs (band_id, title, gig_date, start_time, end_time, location, location_url, notes, fee_per_player, fee_for_band, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            band_id,
            data.get("title", "").strip(),
            data["gig_date"],
            data["start_time"],
            data["end_time"],
            location,
            data.get("location_url", "").strip() or None,
            data.get("notes", "").strip() or None,
            data.get("fee_per_player") or None,
            data.get("fee_for_band") or None,
            data["status"],
            utc_now_iso(),
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
    timestamp = utc_now_iso()
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
            title = ?,
            gig_date = ?,
            start_time = ?,
            end_time = ?,
            location = ?,
            location_url = ?,
            notes = ?,
            fee_per_player = ?,
            fee_for_band = ?,
            status = ?
        WHERE id = ?
        """,
        (
            data.get("title", gig["title"] or "").strip(),
            data.get("gig_date", gig["gig_date"]),
            data.get("start_time", gig["start_time"]),
            data.get("end_time", gig["end_time"]),
            (data.get("location", gig["location"]) or "").strip() or DEFAULT_GIG_LOCATION,
            data.get("location_url", gig["location_url"] or "").strip() or None,
            data.get("notes", gig["notes"] or "").strip() or None,
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


@app.route("/api/gig/<int:gig_id>/response/<int:user_id>", methods=["POST"])
@login_required
def update_gig_response_for_player(gig_id, user_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if not gig or not is_band_admin(gig["band_id"], session["user_id"]):
        return jsonify({"ok": False}), 403

    membership = db.execute(
        "SELECT 1 FROM band_memberships WHERE band_id = ? AND user_id = ?",
        (gig["band_id"], user_id),
    ).fetchone()
    if not membership:
        return jsonify({"ok": False, "error": "Player not found"}), 404

    status = request.json.get("status")
    allowed = {"Available", "Not Available", "Unsure yet", "Unanswered"}
    if status not in allowed:
        return jsonify({"ok": False, "error": "Invalid status"}), 400

    updated_at = utc_now_iso()
    db.execute(
        """
        INSERT INTO availability (gig_id, user_id, status, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(gig_id, user_id)
        DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (gig_id, user_id, status, updated_at),
    )
    db.commit()
    return jsonify({"ok": True, "updated_at": updated_at})


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


@app.route("/api/rehearsal/availability", methods=["POST"])
@login_required
def update_rehearsal_availability():
    user = current_user()
    band_id = request.json.get("band_id")
    rehearsal_date = (request.json.get("rehearsal_date") or "").strip()
    is_available = bool(request.json.get("is_available"))
    db = get_db()
    membership = db.execute(
        "SELECT 1 FROM band_memberships WHERE band_id = ? AND user_id = ?",
        (band_id, user["id"]),
    ).fetchone()
    if not membership:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    if is_available:
        db.execute(
            "DELETE FROM rehearsal_unavailability WHERE band_id = ? AND rehearsal_date = ? AND user_id = ?",
            (band_id, rehearsal_date, user["id"]),
        )
    else:
        db.execute(
            """
            INSERT INTO rehearsal_unavailability (band_id, rehearsal_date, user_id, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(band_id, rehearsal_date, user_id)
            DO UPDATE SET updated_at = excluded.updated_at
            """,
            (band_id, rehearsal_date, user["id"], utc_now_iso()),
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/rehearsal/<rehearsal_date>", methods=["GET"])
@login_required
def rehearsal_detail(band_id, rehearsal_date):
    if not is_band_admin(band_id, session["user_id"]):
        return jsonify({"ok": False}), 403
    db = get_db()
    players = db.execute(
        """
        SELECT u.id, u.name,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM part_defaults pd
                   JOIN parts p ON p.id = pd.part_id
                   WHERE p.band_id = bm.band_id
                     AND pd.user_id = u.id
               ) THEN 1 ELSE 0 END AS is_regular,
               COALESCE((
                   SELECT GROUP_CONCAT(p2.name, ', ')
                   FROM part_defaults pd2
                   JOIN parts p2 ON p2.id = pd2.part_id
                   WHERE p2.band_id = bm.band_id
                     AND pd2.user_id = u.id
               ), '') AS default_parts
        FROM band_memberships bm
        JOIN users u ON u.id = bm.user_id
        WHERE bm.band_id = ?
        ORDER BY u.name
        """,
        (band_id,),
    ).fetchall()
    overrides = db.execute(
        """
        SELECT user_id, is_included
        FROM rehearsal_player_overrides
        WHERE band_id = ? AND rehearsal_date = ?
        """,
        (band_id, rehearsal_date),
    ).fetchall()
    override_map = {row["user_id"]: bool(row["is_included"]) for row in overrides}
    unavailable_rows = db.execute(
        """
        SELECT user_id
        FROM rehearsal_unavailability
        WHERE band_id = ? AND rehearsal_date = ?
        """,
        (band_id, rehearsal_date),
    ).fetchall()
    unavailable_user_ids = {row["user_id"] for row in unavailable_rows}
    player_rows = []
    for player in players:
        scheduled = override_map.get(player["id"], bool(player["is_regular"]))
        player_rows.append(
            {
                "id": player["id"],
                "name": player["name"],
                "is_regular": bool(player["is_regular"]),
                "default_parts": player["default_parts"] or "",
                "is_scheduled": scheduled,
                "is_unavailable": player["id"] in unavailable_user_ids,
            }
        )
    player_rows.sort(key=lambda row: (0 if row["is_regular"] else 1, row["name"].lower()))
    cancellation = db.execute(
        """
        SELECT 1
        FROM rehearsal_cancellations
        WHERE band_id = ? AND rehearsal_date = ?
        """,
        (band_id, rehearsal_date),
    ).fetchone()
    return jsonify({"ok": True, "is_cancelled": bool(cancellation), "players": player_rows})


@app.route("/api/band/<int:band_id>/rehearsal/<rehearsal_date>/cancel", methods=["POST"])
@login_required
def set_rehearsal_cancellation(band_id, rehearsal_date):
    if not is_band_admin(band_id, session["user_id"]):
        return jsonify({"ok": False}), 403
    is_cancelled = bool(request.json.get("is_cancelled"))
    db = get_db()
    if is_cancelled:
        db.execute(
            """
            INSERT INTO rehearsal_cancellations (band_id, rehearsal_date, created_by, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(band_id, rehearsal_date) DO UPDATE SET created_by = excluded.created_by, created_at = excluded.created_at
            """,
            (band_id, rehearsal_date, session["user_id"], utc_now_iso()),
        )
    else:
        db.execute(
            "DELETE FROM rehearsal_cancellations WHERE band_id = ? AND rehearsal_date = ?",
            (band_id, rehearsal_date),
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/band/<int:band_id>/rehearsal/<rehearsal_date>/players", methods=["POST"])
@login_required
def save_rehearsal_players(band_id, rehearsal_date):
    if not is_band_admin(band_id, session["user_id"]):
        return jsonify({"ok": False}), 403
    scheduled_player_ids = request.json.get("scheduled_player_ids") or []
    scheduled_player_ids = {int(player_id) for player_id in scheduled_player_ids}
    db = get_db()
    regular_player_ids = get_regular_player_ids(db, band_id)
    members = db.execute(
        "SELECT user_id FROM band_memberships WHERE band_id = ?",
        (band_id,),
    ).fetchall()
    for member in members:
        user_id = member["user_id"]
        default_included = user_id in regular_player_ids
        desired_included = user_id in scheduled_player_ids
        if desired_included == default_included:
            db.execute(
                "DELETE FROM rehearsal_player_overrides WHERE band_id = ? AND rehearsal_date = ? AND user_id = ?",
                (band_id, rehearsal_date, user_id),
            )
        else:
            db.execute(
                """
                INSERT INTO rehearsal_player_overrides (band_id, rehearsal_date, user_id, is_included, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(band_id, rehearsal_date, user_id)
                DO UPDATE SET is_included = excluded.is_included, updated_at = excluded.updated_at
                """,
                (band_id, rehearsal_date, user_id, 1 if desired_included else 0, utc_now_iso()),
            )
    db.commit()
    return jsonify({"ok": True})

init_db()


if __name__ == "__main__":
    app.run(debug=True)
