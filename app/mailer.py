"""E-mail notifications.

`notify()` is fire-and-forget (background thread) so a slow SMTP server never
delays the guest's confirmation. `send_now()` sends synchronously and returns
a (ok, error) tuple — used by the admin "test" / "summary" buttons so the
result can be shown immediately.
"""
import ssl
import smtplib
import logging
import threading
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import config

log = logging.getLogger("svadba.mailer")


def _send(subject, body, recipients):
    """Send one message to a list of recipients. Raises on failure."""
    if not recipients:
        return
    ctx = ssl.create_default_context()
    if config.SMTP_MODE == "ssl":
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT,
                                  timeout=15, context=ctx)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
    try:
        server.login(config.MAIL_USER, config.MAIL_PASS)
        msg = EmailMessage()
        msg["From"] = config.MAIL_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="kostya-i-gera.ru")
        msg.set_content(body)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def notify(subject, body, recipients):
    """Fire-and-forget notification to the given recipients."""
    if not config.MAIL_ENABLED or not recipients:
        return

    def run():
        try:
            _send(subject, body, recipients)
            log.info("notification e-mail sent to %s", recipients)
        except Exception as e:  # pragma: no cover - network dependent
            log.warning("notification e-mail failed: %r", e)

    threading.Thread(target=run, daemon=True).start()


def send_now(subject, body, recipients):
    """Send synchronously. Returns (ok: bool, error: str|None)."""
    if not config.MAIL_ENABLED:
        return False, "Отправка почты отключена на сервере."
    if not recipients:
        return False, "Не указан адрес получателя."
    try:
        _send(subject, body, recipients)
        return True, None
    except Exception as e:
        return False, str(e)
