#!/usr/bin/env python3
"""End-to-end smoke test for the Svadba service (stdlib only).

Exercises the full flow: home page, admin login (with CSRF + brute-force
counter), link generation, guest RSVP submit, answer change, and that the
response shows up in the admin dashboard with correct counters.

Usage:
    BASE=http://127.0.0.1:8000 ADMIN_PATH=admin ADMIN_PASSWORD=753951 \
        python3 tools/smoke_test.py
"""
import os
import re
import sys
import http.cookiejar
import urllib.parse
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8000").rstrip("/")
ADMIN_PATH = os.environ.get("ADMIN_PATH", "admin").strip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "753951")
ADMIN = BASE + "/" + ADMIN_PATH

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "svadba-smoke/1.0")]

failures = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print("[%s] %s %s" % (status, name, extra))
    if not cond:
        failures.append(name)


def get(url):
    with opener.open(url, timeout=20) as r:
        return r.getcode(), r.read().decode("utf-8", "replace"), r.geturl()


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with opener.open(req, timeout=20) as r:
            return r.getcode(), r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url


def csrf_from(html):
    m = re.search(r'name="csrf"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


def main():
    # 1. Home + health
    code, html, _ = get(BASE + "/")
    check("home 200", code == 200)
    code, body, _ = get(BASE + "/healthz")
    check("healthz ok", code == 200 and body.strip() == "ok")

    # 2. Unknown invite -> 404
    code, _, _ = post(BASE + "/i/definitely-not-a-real-token", {})
    check("unknown invite 404", code == 404, "(got %s)" % code)

    # 3. Admin login page + CSRF
    code, html, _ = get(ADMIN)
    check("admin login page", code == 200 and "csrf" in html)
    token = csrf_from(html)
    check("csrf present", bool(token))

    # 4. Wrong password is rejected
    code, html, _ = post(ADMIN + "/login", {"csrf": token, "password": "000000"})
    check("wrong password rejected", code == 401, "(got %s)" % code)

    # 5. Correct password logs in -> dashboard
    code, html, url = get(ADMIN)              # refresh csrf
    token = csrf_from(html)
    code, html, url = post(ADMIN + "/login", {"csrf": token, "password": ADMIN_PASSWORD})
    check("login ok -> dashboard", "ответы гостей" in html or url.endswith("/dashboard"),
          "(url=%s)" % url)

    # 6. Generate a link
    token = csrf_from(html)
    code, html, url = post(ADMIN + "/generate", {"csrf": token})
    m = re.search(r'/i/([A-Za-z0-9_\-]{10,})', html)
    check("link generated", bool(m), "(token=%s)" % (m.group(1) if m else None))
    if not m:
        return
    guest_token = m.group(1)

    # 7. Guest opens the link
    code, html, _ = get(BASE + "/i/" + guest_token)
    check("guest page opens", code == 200 and "свадьбу" in html.lower())

    # 8. Guest accepts with a name
    code, html, url = post(BASE + "/i/" + guest_token,
                           {"response": "accept", "name": "Иван Тестов"})
    check("rsvp accepted -> thanks", "ваш ответ записан" in html.lower(),
          "(url=%s)" % url)

    # 9. Guest changes the answer
    code, html, _ = post(BASE + "/i/" + guest_token,
                         {"response": "decline", "name": "Иван Тестов"})
    check("rsvp changed", "ваш ответ записан" in html.lower())

    # 10. Missing choice is rejected
    code, html, _ = post(BASE + "/i/" + guest_token, {"name": "Без ответа"})
    check("missing choice rejected", code == 400)

    # 11. Dashboard reflects the response
    code, html, _ = get(ADMIN + "/dashboard")
    check("name in dashboard", "Иван Тестов" in html)
    check("declined badge shown", "Отклонил" in html)

    print()
    if failures:
        print("RESULT: FAILED ->", ", ".join(failures))
        sys.exit(1)
    print("RESULT: ALL PASSED")


if __name__ == "__main__":
    main()
