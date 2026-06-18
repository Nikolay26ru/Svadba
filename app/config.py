"""Application configuration, read entirely from environment variables.

No secrets live in this file or anywhere in the repository — real values
(SECRET_KEY, admin password hash, mailbox password) are provided on the
server through an environment file referenced by the systemd unit.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# --- Storage -------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR.parent / "data" / "svadba.db"))

# --- Security ------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
# Secret URL segment for the admin panel (acts as a second factor).
ADMIN_PATH = os.environ.get("ADMIN_PATH", "admin").strip("/") or "admin"
COOKIE_SECURE = _bool("COOKIE_SECURE", True)

# Public base URL used to build the personal invite links shown in admin.
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

# --- Login brute-force protection ---------------------------------------
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "900"))

# --- Event ---------------------------------------------------------------
WEDDING_DATE = os.environ.get("WEDDING_DATE", "26.06.2026")
DISPLAY_TZ = os.environ.get("DISPLAY_TZ", "Europe/Moscow")

# --- E-mail notifications ------------------------------------------------
MAIL_ENABLED = _bool("MAIL_ENABLED", False)
MAIL_USER = os.environ.get("MAIL_USER", "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
MAIL_TO = os.environ.get("MAIL_TO", MAIL_USER)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.beget.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_MODE = os.environ.get("SMTP_MODE", "ssl")  # "ssl" or "starttls"
