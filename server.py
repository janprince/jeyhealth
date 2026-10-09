"""JeyHealth Report: dependency-free local web application with SQLite persistence."""
import argparse
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("JEYHEALTH_DB", ROOT / "data" / "jeyhealth.sqlite3"))
DEMO_PASSWORD = "JeyHealth2026!"
ROLES = {"official": "District Health Official", "chv": "Community Health Volunteer", "clinic": "Clinic Health Worker", "resident": "Resident"}
CATEGORIES = ["Acute watery diarrhoea", "Fever and vomiting", "Respiratory symptoms", "Skin rash", "Other symptoms"]
ACTIVE = ("pending", "investigating", "escalated")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def today_date():
    # Africa/Accra is UTC, independent of the host's time zone.
    return datetime.now(timezone.utc).date()


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}${digest}"


def check_password(password, encoded):
    salt, _ = encoded.split("$", 1)
    return hmac.compare_digest(password_hash(password, salt), encoded)


def event(conn, kind, entity_id, action, actor, notes=""):
    conn.execute("INSERT INTO events(kind,entity_id,action,actor_id,notes,created_at) VALUES(?,?,?,?,?,?)", (kind, entity_id, action, actor, notes, now()))


def detect_clusters(conn, actor=None, today=None):
    """Count trusted, non-dismissed encounters in an inclusive rolling calendar window.

    Citizen tips count only after official verification. A reviewed episode cannot
    re-alert on the same evidence. New evidence can open a subsequent episode.
    """
    today = today or today_date()
    settings = dict(conn.execute("SELECT key,value FROM settings").fetchall())
    threshold, days = int(settings["threshold"]), int(settings["window_days"])
    start = (today - timedelta(days=days - 1)).isoformat()
    rows = conn.execute("""SELECT r.*, u.role FROM reports r JOIN users u ON u.id=r.submitted_by
      WHERE r.observed_on BETWEEN ? AND ? AND r.status != 'dismissed'
      AND (u.role IN ('chv','clinic') OR r.status='verified') ORDER BY r.id""", (start, today.isoformat())).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault((r["locality_id"], r["category"]), []).append(r)
    current = conn.execute("SELECT * FROM clusters WHERE status IN ('pending','investigating','escalated')").fetchall()
    current_by_key = {(c["locality_id"], c["category"]): c for c in current}
    for key, reports in groups.items():
        count = sum(r["case_count"] for r in reports)
        existing = current_by_key.get(key)
        if existing:
            cluster_id = existing["id"]
            # Preserve the evidence that prompted an alert even after it ages out.
            conn.execute("UPDATE clusters SET rolling_count=? WHERE id=?", (count, cluster_id))
        elif count >= threshold:
            previous = conn.execute("SELECT * FROM clusters WHERE locality_id=? AND category=? ORDER BY id DESC LIMIT 1", key).fetchone()
            if previous and not any(r["created_at"] > previous["updated_at"] or r["updated_at"] > previous["updated_at"] for r in reports):
                continue
            cur = conn.execute("""INSERT INTO clusters(locality_id,category,status,threshold,window_days,rolling_count,created_at,updated_at)
                VALUES(?,?,'pending',?,?,?,?,?)""", (*key, threshold, days, count, now(), now()))
            cluster_id = cur.lastrowid
            event(conn, "cluster", cluster_id, "Cluster flagged", actor, f"{count} cases in {days} days met the threshold of {threshold}.")
        else:
            continue
        for report in reports:
            conn.execute("INSERT OR IGNORE INTO cluster_reports(cluster_id,report_id) VALUES(?,?)", (cluster_id, report["id"]))
    for key, existing in current_by_key.items():
        if key not in groups:
            conn.execute("UPDATE clusters SET rolling_count=0 WHERE id=?", (existing["id"],))


def init_db(seed=True):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('official','chv','clinic','resident')));
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires_at REAL NOT NULL,csrf TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(identity TEXT PRIMARY KEY,attempts INTEGER NOT NULL,last_attempt REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS localities(id INTEGER PRIMARY KEY,name TEXT NOT NULL,district TEXT NOT NULL,lat REAL NOT NULL,lng REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY,locality_id INTEGER NOT NULL REFERENCES localities(id),category TEXT NOT NULL,
          case_count INTEGER NOT NULL CHECK(case_count BETWEEN 1 AND 50),observed_on TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',
          submitted_by INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL DEFAULT 'submitted',
          submission_key TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS clusters(id INTEGER PRIMARY KEY,locality_id INTEGER NOT NULL REFERENCES localities(id),category TEXT NOT NULL,
          status TEXT NOT NULL,threshold INTEGER NOT NULL,window_days INTEGER NOT NULL,rolling_count INTEGER NOT NULL,
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL,reviewed_by INTEGER REFERENCES users(id));
        CREATE UNIQUE INDEX IF NOT EXISTS active_cluster ON clusters(locality_id,category) WHERE status IN ('pending','investigating','escalated');
        CREATE TABLE IF NOT EXISTS cluster_reports(cluster_id INTEGER REFERENCES clusters(id),report_id INTEGER REFERENCES reports(id),PRIMARY KEY(cluster_id,report_id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,entity_id INTEGER NOT NULL,action TEXT NOT NULL,
          actor_id INTEGER REFERENCES users(id),notes TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS advisories(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,locality_id INTEGER REFERENCES localities(id),
          published_by INTEGER REFERENCES users(id),created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS report_window ON reports(locality_id,category,observed_on);
        """)
        conn.execute("INSERT OR IGNORE INTO settings VALUES('threshold','5')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES('window_days','3')")
        if not seed or conn.execute("SELECT count(*) FROM users").fetchone()[0]:
            return
        users = [("Dr. Kwabena Sarpong", "official@jeyhealth.local", "official"), ("Abena Owusu", "chv@jeyhealth.local", "chv"),
                 ("Esi Mensah", "clinic@jeyhealth.local", "clinic"), ("Ama Boateng", "resident@jeyhealth.local", "resident")]
        for name, email, role in users:
            conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", (name, email, password_hash(DEMO_PASSWORD), role))
        # Approximate town centres, not household or patient locations.
        localities = [("Ablekuma", 5.651, -0.310), ("Oduman", 5.666, -0.364), ("Afuaman", 5.693, -0.339),
                      ("Amasaman", 5.704, -0.299), ("Pokuase", 5.685, -0.276), ("Manhean", 5.641, -0.340),
                      ("Nsakina", 5.667, -0.327), ("Ayikai Doblo", 5.758, -0.332)]
        conn.executemany("INSERT INTO localities(name,district,lat,lng) VALUES(?,'Ga West',?,?)", localities)
        today = today_date()
        # Clearly fictional demonstration records. Three current clusters and eight weeks of trends.
        for week in range(8, 0, -1):
            for i in range(3 + week % 4):
                d = today - timedelta(days=week * 7 + i)
                conn.execute("""INSERT INTO reports(locality_id,category,case_count,observed_on,notes,submitted_by,status,submission_key,created_at,updated_at)
                 VALUES(?,?,?,?,?,?,'verified',?,?,?)""", (i % 8 + 1, CATEGORIES[(week + i) % 5], 1 + i % 2, d.isoformat(),
                 "Fictional record for project demonstration.", 2 + i % 2, secrets.token_hex(16), d.isoformat()+"T09:00:00+00:00", d.isoformat()+"T10:00:00+00:00"))
        samples = [(1,0,2,0,2), (1,0,2,1,3), (1,0,3,2,2), (2,1,2,0,3), (2,1,3,1,2),
                   (5,2,2,0,2), (5,2,2,1,3), (5,2,2,2,2), (3,3,1,0,2), (4,0,2,1,3), (6,1,1,2,2), (7,4,1,0,2)]
        for loc, cat, count, ago, submitter in samples:
            d = (today - timedelta(days=ago)).isoformat()
            cur = conn.execute("""INSERT INTO reports(locality_id,category,case_count,observed_on,notes,submitted_by,submission_key,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?)""", (loc,CATEGORIES[cat],count,d,"Fictional household encounter. No patient identifiers collected.",submitter,secrets.token_hex(16),d+"T08:30:00+00:00",d+"T08:30:00+00:00"))
            event(conn, "report", cur.lastrowid, "Report submitted", submitter, "Trusted health worker report.")
        conn.execute("""INSERT INTO reports(locality_id,category,case_count,observed_on,notes,submitted_by,status,submission_key,created_at,updated_at)
          VALUES(1,?,1,?,'Fictional resident tip awaiting review.',4,'unverified',?,?,?)""", (CATEGORIES[0],today.isoformat(),secrets.token_hex(16),now(),now()))
        detect_clusters(conn)
        conn.execute("INSERT INTO advisories(title,body,locality_id,published_by,created_at) VALUES(?,?,NULL,1,?)", (
            "Welcome to the community reporting pilot", "Demonstration advisory: report unusual symptom patterns through this portal. Tips are reviewed by district staff. This sample notice does not describe a real health event.", now()))


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def text_field(data, key, maximum=2000, required=False):
    value = data.get(key, "")
    if not isinstance(value, str):
        raise APIError(400, f"{key.replace('_',' ').capitalize()} must be text.")
    value = value.strip()
    if len(value) > maximum or (required and not value):
        raise APIError(400, f"Enter {key.replace('_',' ')} (up to {maximum} characters).")
    return value


def integer(data, key, low, high):
    value = data.get(key)
    if type(value) is not int or not low <= value <= high:
        raise APIError(400, f"{key.replace('_',' ').capitalize()} must be a whole number from {low} to {high}.")
    return value


def joined_reports(conn, user):
    where, args = ("", ()) if user["role"] == "official" else ("WHERE r.submitted_by=?", (user["id"],))
    return [dict(r) for r in conn.execute(f"""SELECT r.*,l.name locality,u.name reporter,u.role reporter_role
        FROM reports r JOIN localities l ON l.id=r.locality_id JOIN users u ON u.id=r.submitted_by {where}
        ORDER BY r.observed_on DESC,r.id DESC""", args)]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "public"), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        # OSM requires a web Referer. Share only our origin with cross-origin services.
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def do_GET(self):
        if urlparse(self.path).path.startswith("/api/"):
            return self.api("GET")
        if urlparse(self.path).path in ("/", "/index.html"):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        self.api("POST")

    def send_json(self, status, data, cookie=None):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 20000:
                raise APIError(413, "Request is empty or too large.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, json.JSONDecodeError):
            raise APIError(400, "Send a valid JSON object.")

    def session(self, conn):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
            token = jar["jey_session"].value
        except (KeyError, cookies.CookieError):
            raise APIError(401, "Please sign in to continue.")
        hashed = hashlib.sha256(token.encode()).hexdigest()
        row = conn.execute("""SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE token_hash=? AND expires_at>?""", (hashed,time.time())).fetchone()
        if not row:
            raise APIError(401, "Your session ended. Please sign in again.")
        return dict(row), hashed

    def api(self, method):
        try:
            with connect() as conn:
                self.route(conn, method)
        except APIError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except sqlite3.IntegrityError:
            self.send_json(400, {"error": "This record conflicts with an existing record. Refresh and try again."})
        except Exception as exc:
            print(f"Request error: {type(exc).__name__}: {exc}", flush=True)
            self.send_json(500, {"error": "The request could not be completed. Please try again."})

    def route(self, conn, method):
        path = urlparse(self.path).path
        if method == "POST":
            # Same-origin guard applies to login as well as authenticated mutations.
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://{self.headers.get('Host')}",f"https://{self.headers.get('Host')}"):
                raise APIError(403, "This request must come from JeyHealth Report.")
            data = self.body()
        else:
            data = {}
        if path == "/api/login" and method == "POST":
            email = text_field(data,"email",120,True).lower()
            password = text_field(data,"password",200,True)
            identity = self.client_address[0] + ":" + email
            attempt = conn.execute("SELECT * FROM login_attempts WHERE identity=?", (identity,)).fetchone()
            if attempt and attempt["attempts"] >= 8 and time.time()-attempt["last_attempt"] < 300:
                raise APIError(429, "Too many sign-in attempts. Try again in five minutes.")
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not user or not check_password(password,user["password_hash"]):
                count = attempt["attempts"]+1 if attempt and time.time()-attempt["last_attempt"]<300 else 1
                conn.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)",(identity,count,time.time()))
                conn.commit()
                raise APIError(401,"The email or password is incorrect.")
            conn.execute("DELETE FROM login_attempts WHERE identity=?",(identity,))
            conn.execute("DELETE FROM sessions WHERE expires_at<?",(time.time(),))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),user["id"],time.time()+8*3600,csrf))
            conn.commit()
            return self.send_json(200,{"ok":True},f"jey_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800")
        user, session_hash = self.session(conn)
        if method == "POST" and not hmac.compare_digest(self.headers.get("X-CSRF-Token",""),user["csrf"]):
            raise APIError(403,"Refresh this page before saving your changes.")
        if path == "/api/logout" and method == "POST":
            conn.execute("DELETE FROM sessions WHERE token_hash=?",(session_hash,))
            conn.commit()
            return self.send_json(200,{"ok":True},"jey_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
        if path == "/api/state" and method == "GET":
            detect_clusters(conn)
            reports = joined_reports(conn,user)
            clusters = []
            if user["role"] == "official":
                clusters = [dict(c) for c in conn.execute("""SELECT c.*,l.name locality,u.name reviewer,
                  (SELECT sum(r.case_count) FROM cluster_reports cr JOIN reports r ON r.id=cr.report_id WHERE cr.cluster_id=c.id) evidence_count
                  FROM clusters c JOIN localities l ON l.id=c.locality_id LEFT JOIN users u ON u.id=c.reviewed_by ORDER BY c.id DESC""")]
                for c in clusters:
                    c["report_ids"] = [r[0] for r in conn.execute("SELECT report_id FROM cluster_reports WHERE cluster_id=?",(c["id"],))]
            ids = [r["id"] for r in reports]
            events = []
            for row in conn.execute("SELECT e.*,u.name actor FROM events e LEFT JOIN users u ON u.id=e.actor_id ORDER BY e.id DESC"):
                if user["role"] == "official" or (row["kind"]=="report" and row["entity_id"] in ids):
                    events.append(dict(row))
            advisories = [dict(a) for a in conn.execute("""SELECT a.*,l.name locality,u.name author FROM advisories a
                LEFT JOIN localities l ON l.id=a.locality_id JOIN users u ON u.id=a.published_by ORDER BY a.id DESC""")]
            conn.commit()
            return self.send_json(200,{"user":{k:user[k] for k in ("id","name","email","role","csrf")},
                "roles":ROLES,"categories":CATEGORIES,"localities":[dict(l) for l in conn.execute("SELECT * FROM localities")],
                "reports":reports,"clusters":clusters,"events":events,"advisories":advisories,
                "settings":dict(conn.execute("SELECT key,value FROM settings").fetchall()),"today":today_date().isoformat(),"demo":True})
        if path == "/api/reports" and method == "POST":
            if user["role"] == "official":
                raise APIError(403,"Use a health worker or resident account to submit encounters.")
            loc = integer(data,"locality_id",1,100000)
            if not conn.execute("SELECT id FROM localities WHERE id=?",(loc,)).fetchone():
                raise APIError(400,"Select an available locality.")
            category = text_field(data,"category",100,True)
            if category not in CATEGORIES:
                raise APIError(400,"Select a symptom category.")
            count = integer(data,"case_count",1,50)
            observed = text_field(data,"observed_on",10,True)
            try:
                parsed = date.fromisoformat(observed)
                if parsed.isoformat()!=observed or not today_date()-timedelta(days=365) <= parsed <= today_date():
                    raise ValueError()
            except ValueError:
                raise APIError(400,"Choose an observation date within the past year, up to today.")
            notes = text_field(data,"notes",2000)
            key = text_field(data,"submission_key",100,True)
            previous = conn.execute("SELECT id,submitted_by FROM reports WHERE submission_key=?",(key,)).fetchone()
            if previous:
                if previous["submitted_by"] != user["id"]:
                    raise APIError(409,"This submission identifier is already in use.")
                return self.send_json(200,{"id":previous["id"],"duplicate":True})
            status = "unverified" if user["role"]=="resident" else "submitted"
            timestamp=now()
            cur=conn.execute("""INSERT INTO reports(locality_id,category,case_count,observed_on,notes,submitted_by,status,submission_key,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",(loc,category,count,observed,notes,user["id"],status,key,timestamp,timestamp))
            event(conn,"report",cur.lastrowid,"Tip submitted" if status=="unverified" else "Report submitted",user["id"],"Awaiting verification." if status=="unverified" else "Trusted health worker report.")
            detect_clusters(conn,user["id"])
            conn.commit()
            return self.send_json(201,{"id":cur.lastrowid})
        if user["role"] != "official":
            raise APIError(403,"District official access is required for this action.")
        if path == "/api/reports/review" and method == "POST":
            report_id=integer(data,"id",1,100000000)
            report=conn.execute("SELECT * FROM reports WHERE id=?",(report_id,)).fetchone()
            if not report:
                raise APIError(404,"Report not found.")
            status=text_field(data,"status",20,True)
            if status not in ("verified","dismissed"):
                raise APIError(400,"Choose verify or dismiss.")
            if report["status"] in ("verified","dismissed"):
                raise APIError(409,"This report has already been reviewed.")
            notes=text_field(data,"notes",2000,True)
            conn.execute("UPDATE reports SET status=?,updated_at=? WHERE id=?",(status,now(),report_id))
            event(conn,"report",report_id,"Report "+status,user["id"],notes)
            detect_clusters(conn,user["id"])
            conn.commit()
            return self.send_json(200,{"ok":True})
        if path == "/api/clusters/review" and method == "POST":
            cluster_id=integer(data,"id",1,100000000)
            cluster=conn.execute("SELECT * FROM clusters WHERE id=?",(cluster_id,)).fetchone()
            if not cluster:
                raise APIError(404,"Cluster not found.")
            status=text_field(data,"status",20,True)
            allowed={"pending":{"investigating","escalated","dismissed"},"investigating":{"escalated","dismissed"},"escalated":{"resolved"},"resolved":set(),"dismissed":set()}
            if status not in allowed.get(cluster["status"],set()):
                raise APIError(409,"This cluster changed or the requested transition is not available. Refresh the page.")
            notes=text_field(data,"notes",2000,True)
            conn.execute("UPDATE clusters SET status=?,updated_at=?,reviewed_by=? WHERE id=?",(status,now(),user["id"],cluster_id))
            event(conn,"cluster",cluster_id,"Cluster "+status,user["id"],notes)
            conn.commit()
            return self.send_json(200,{"ok":True})
        if path == "/api/settings" and method == "POST":
            threshold=integer(data,"threshold",2,100)
            days=integer(data,"window_days",1,30)
            notes=text_field(data,"notes",2000,True)
            conn.execute("UPDATE settings SET value=? WHERE key='threshold'",(str(threshold),))
            conn.execute("UPDATE settings SET value=? WHERE key='window_days'",(str(days),))
            event(conn,"settings",1,"Detection rules updated",user["id"],f"Threshold {threshold}, window {days} days. {notes}")
            detect_clusters(conn,user["id"])
            conn.commit()
            return self.send_json(200,{"ok":True})
        if path == "/api/advisories" and method == "POST":
            title=text_field(data,"title",120,True)
            body=text_field(data,"body",3000,True)
            loc=data.get("locality_id")
            if loc is not None:
                loc=integer(data,"locality_id",1,100000)
                if not conn.execute("SELECT id FROM localities WHERE id=?",(loc,)).fetchone():
                    raise APIError(400,"Select an available locality.")
            cur=conn.execute("INSERT INTO advisories(title,body,locality_id,published_by,created_at) VALUES(?,?,?,?,?)",(title,body,loc,user["id"],now()))
            event(conn,"advisory",cur.lastrowid,"Advisory published",user["id"],title)
            conn.commit()
            return self.send_json(201,{"id":cur.lastrowid})
        if path == "/api/export" and method == "GET":
            out=io.StringIO();writer=csv.writer(out)
            writer.writerow(["Report ID","Locality","Symptoms","Cases","Observed on","Source role","Status"])
            for r in joined_reports(conn,user):
                cells=[r["id"],r["locality"],r["category"],r["case_count"],r["observed_on"],r["reporter_role"],r["status"]]
                writer.writerow(["'"+c if isinstance(c,str) and c.startswith(("=","+","-","@")) else c for c in cells])
            body=out.getvalue().encode()
            self.send_response(200)
            self.send_header("Content-Type","text/csv; charset=utf-8")
            self.send_header("Content-Disposition",'attachment; filename="jeyhealth-reports.csv"')
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers();self.wfile.write(body)
            return
        raise APIError(404,"This action is not available.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8000)
    parser.add_argument("--host",default="127.0.0.1")
    args=parser.parse_args()
    init_db()
    print(f"JeyHealth Report running at http://{args.host}:{args.port}",flush=True)
    print("Fictional demo data. See README.md for the four demo accounts.",flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
