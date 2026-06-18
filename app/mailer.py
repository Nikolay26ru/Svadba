"""Best-effort e-mail notifications.

Sending happens in a background thread so a slow or unavailable SMTP server
never delays the guest's confirmation. Failures are logged, never raised.
"""
import ssl
import smtplib
import logging
import threading
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import config

log = logging.getLogger("svadba.mailer")


def _send_sync(subject, body):
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
        msg["To"] = config.MAIL_TO
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


def notify(subject, body):
    """Fire-and-forget notification e-mail."""
    if not config.MAIL_ENABLED:
        return

    def run():
        try:
            _send_sync(subject, body)
            log.info("notification e-mail sent to %s", config.MAIL_TO)
        except Exception as e:  # pragma: no cover - network dependent
            log.warning("notification e-mail failed: %r", e)

    threading.Thread(target=run, daemon=True).start()
