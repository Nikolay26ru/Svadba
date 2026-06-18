"""Wedding invitation service: public RSVP pages + password-protected admin."""
import logging
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, request, session, redirect, url_for, render_template,
                   abort, Response)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

import config
import db
import mailer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("svadba")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.COOKIE_SECURE,
    MAX_CONTENT_LENGTH=64 * 1024,
)
# Trust one proxy hop (nginx) so request.remote_addr is the real client IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)

db.init_db()

TZ = ZoneInfo(config.DISPLAY_TZ)
ADMIN = "/" + config.ADMIN_PATH


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fmt_dt(iso):
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso


app.jinja_env.filters["dt"] = fmt_dt


def invite_url(token):
    if config.BASE_URL:
        return "%s/i/%s" % (config.BASE_URL, token)
    return request.url_root.rstrip("/") + "/i/" + token


app.jinja_env.globals["invite_url"] = invite_url


def csrf_token():
    t = session.get("csrf")
    if not t:
        t = secrets.token_urlsafe(24)
        session["csrf"] = t
    return t


app.jinja_env.globals["csrf_token"] = csrf_token


def check_csrf():
    sent = request.form.get("csrf", "")
    good = session.get("csrf", "")
    if not good or not secrets.compare_digest(sent, good):
        abort(400)


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(ADMIN)
        return f(*a, **kw)
    return wrapper


def get_invite(token):
    if not token or len(token) > 100:
        return None
    conn = db.connect()
    try:
        return conn.execute("SELECT * FROM invites WHERE token=?", (token,)).fetchone()
    finally:
        conn.close()


# --------- login throttling (shared across workers via SQLite) ------------
def _window_start_iso():
    start = datetime.now(timezone.utc) - timedelta(seconds=config.LOGIN_WINDOW_SECONDS)
    return start.replace(microsecond=0).isoformat()


def recent_failures(ip):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM login_attempts "
            "WHERE ip=? AND success=0 AND ts >= ?",
            (ip, _window_start_iso()),
        ).fetchone()
        return row["c"]
    finally:
        conn.close()


def record_attempt(ip, success):
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO login_attempts (ip, ts, success) VALUES (?,?,?)",
            (ip, now_iso(), 1 if success else 0),
        )
        cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        conn.execute("DELETE FROM login_attempts WHERE ts < ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Public routes
# --------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html", wedding_date=config.WEDDING_DATE)


@app.route("/healthz")
def healthz():
    return Response("ok\n", mimetype="text/plain")


@app.route("/i/<token>", methods=["GET"])
def invite(token):
    inv = get_invite(token)
    if not inv:
        abort(404)
    return render_template(
        "invite.html",
        inv=inv,
        token=token,
        saved=request.args.get("saved") == "1",
        wedding_date=config.WEDDING_DATE,
    )


@app.route("/i/<token>", methods=["POST"])
def invite_submit(token):
    inv = get_invite(token)
    if not inv:
        abort(404)
    response = (request.form.get("response") or "").strip()
    name = (request.form.get("name") or "").strip()[:120]

    def rerender(error):
        return render_template(
            "invite.html", inv=inv, token=token, saved=False, error=error,
            form_response=response, form_name=name,
            wedding_date=config.WEDDING_DATE,
        ), 400

    if response not in ("accept", "decline"):
        return rerender("Пожалуйста, выберите «Принять» или «Отклонить».")
    if not name:
        return rerender("Пожалуйста, укажите имя и фамилию.")

    conn = db.connect()
    try:
        conn.execute(
            "UPDATE invites SET response=?, guest_name=?, responded_at=? WHERE token=?",
            (response, name, now_iso(), token),
        )
        conn.commit()
    finally:
        conn.close()

    human = "Принял(а) приглашение" if response == "accept" else "Отклонил(а) приглашение"
    mailer.notify(
        subject="Свадьба: ответ гостя — %s (%s)" % (name, "Принял" if response == "accept" else "Отклонил"),
        body="Гость: %s\nОтвет: %s\nВремя (МСК): %s\nСсылка: %s\n"
             % (name, human, fmt_dt(now_iso()), invite_url(token)),
    )
    return redirect(url_for("invite", token=token, saved="1"))


# --------------------------------------------------------------------------
# Admin routes (mounted under the secret ADMIN path)
# --------------------------------------------------------------------------
@app.route(ADMIN, methods=["GET"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")


@app.route(ADMIN + "/login", methods=["POST"])
def admin_do_login():
    check_csrf()
    ip = request.remote_addr or "unknown"
    if recent_failures(ip) >= config.LOGIN_MAX_ATTEMPTS:
        record_attempt(ip, False)
        return render_template(
            "admin_login.html",
            error="Слишком много попыток. Подождите 15 минут и попробуйте снова.",
        ), 429

    password = request.form.get("password", "")
    if config.ADMIN_PASSWORD_HASH and check_password_hash(config.ADMIN_PASSWORD_HASH, password):
        record_attempt(ip, True)
        session.clear()
        session["admin"] = True
        csrf_token()
        return redirect(url_for("admin_dashboard"))

    record_attempt(ip, False)
    left = max(0, config.LOGIN_MAX_ATTEMPTS - recent_failures(ip))
    return render_template(
        "admin_login.html",
        error="Неверный пароль. Осталось попыток: %d." % left,
    ), 401


@app.route(ADMIN + "/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    conn = db.connect()
    try:
        invites = conn.execute("SELECT * FROM invites ORDER BY id DESC").fetchall()
    finally:
        conn.close()
    accepted = sum(1 for i in invites if i["response"] == "accept")
    declined = sum(1 for i in invites if i["response"] == "decline")
    responses = [i for i in invites if i["response"] in ("accept", "decline")]
    return render_template(
        "admin.html",
        invites=invites,
        responses=responses,
        total=len(invites),
        accepted=accepted,
        declined=declined,
        pending=len(invites) - accepted - declined,
        new_token=request.args.get("new"),
    )


@app.route(ADMIN + "/generate", methods=["POST"])
@admin_required
def admin_generate():
    check_csrf()
    conn = db.connect()
    try:
        token = secrets.token_urlsafe(12)
        while conn.execute("SELECT 1 FROM invites WHERE token=?", (token,)).fetchone():
            token = secrets.token_urlsafe(12)
        conn.execute("INSERT INTO invites (token, created_at) VALUES (?, ?)",
                     (token, now_iso()))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard", new=token))


@app.route(ADMIN + "/logout", methods=["POST"])
@admin_required
def admin_logout():
    check_csrf()
    session.clear()
    return redirect(ADMIN)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           message="Страница не найдена или ссылка недействительна."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400,
                           message="Некорректный запрос. Обновите страницу и попробуйте снова."), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
