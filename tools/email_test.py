#!/usr/bin/env python3
"""Standalone connectivity test for the BeGet mailbox.

Confirms the mailbox exists (IMAP login), finds a working SMTP transport,
sends a test message to itself, and verifies delivery via IMAP search.
Credentials are read from the environment so nothing is hard-coded.
"""
import os
import ssl
import sys
import time
import imaplib
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

USER = os.environ["MAIL_USER"]
PASS = os.environ["MAIL_PASS"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.beget.com")
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.beget.com")
TO = os.environ.get("MAIL_TO", USER)
MARKER = "svadba-selftest-" + str(int(time.time()))


def imap_login():
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=25)
    M.login(USER, PASS)
    return M


def step_mailbox_exists():
    try:
        M = imap_login()
        M.select("INBOX")
        print("[1] IMAP login OK -> mailbox exists:", USER)
        M.logout()
        return True
    except Exception as e:
        print("[1] IMAP login FAILED ->", repr(e))
        return False


def build_message():
    m = EmailMessage()
    m["From"] = USER
    m["To"] = TO
    m["Subject"] = "Svadba SMTP self-test " + MARKER
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain="kostya-i-gera.ru")
    m.set_content(
        "Автотест отправки почты сайта-приглашения.\n"
        "marker=%s\n" % MARKER
    )
    return m


def step_smtp_send():
    ctx = ssl.create_default_context()
    attempts = [(465, "ssl"), (587, "starttls"), (2525, "starttls"), (25, "starttls")]
    for port, mode in attempts:
        try:
            if mode == "ssl":
                s = smtplib.SMTP_SSL(SMTP_HOST, port, timeout=25, context=ctx)
            else:
                s = smtplib.SMTP(SMTP_HOST, port, timeout=25)
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
            s.login(USER, PASS)
            s.send_message(build_message())
            s.quit()
            print("[2] SMTP send OK via %s port %d" % (mode.upper(), port))
            return (port, mode)
        except Exception as e:
            print("[2] SMTP %s port %d FAILED -> %s" % (mode.upper(), port, repr(e)))
    return None


def step_verify_delivery():
    for attempt in range(6):
        time.sleep(6)
        try:
            M = imap_login()
            M.select("INBOX")
            typ, data = M.search(None, '(SUBJECT "%s")' % MARKER)
            ids = data[0].split() if data and data[0] else []
            M.logout()
            if ids:
                print("[3] Delivery VERIFIED -> %d message(s) with marker in INBOX" % len(ids))
                return True
            print("[3] ...not yet visible (try %d/6)" % (attempt + 1))
        except Exception as e:
            print("[3] IMAP verify error ->", repr(e))
    print("[3] Delivery NOT verified within timeout")
    return False


if __name__ == "__main__":
    ok_box = step_mailbox_exists()
    transport = step_smtp_send() if ok_box else None
    ok_deliver = step_verify_delivery() if transport else False
    print("\nRESULT mailbox=%s transport=%s delivered=%s"
          % (ok_box, transport, ok_deliver))
    sys.exit(0 if (ok_box and transport and ok_deliver) else 1)
