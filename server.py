"""Optional web UI:  python server.py   ->  http://localhost:8000

Shows the same dashboard as out/index.html, plus a box to submit or upload new messages.
A submitted message goes through EXACTLY the same pipeline as `python main.py`
(main.process), so the trace, limits and rejection rules are identical.
Login: email one-time code (planner/auth.py). Set LOGIN=off in .env to switch it off.
Standard library only.
"""
import contextlib
import io
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402
from planner import auth  # noqa: E402

LOCK = threading.Lock()
PORT = int(os.environ.get("PORT", "8000"))
LOGIN_PAGE = open(os.path.join("web", "login.html"), encoding="utf-8").read()
COOKIE = "hp_session={}; Max-Age={}; Path=/; HttpOnly; SameSite=Strict"


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj, headers=()):
        self._send(code, json.dumps(obj), "application/json", headers)

    def _user(self):
        return auth.session(self.headers.get("Cookie")) if auth.enabled() else "local"

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/login":
            return self._send(200, LOGIN_PAGE)
        if path == "/logout":
            auth.logout(self.headers.get("Cookie"))
            return self._send(302, "", headers=[("Location", "/login"), ("Set-Cookie", COOKIE.format("", 0))])
        user = self._user()
        if not user:
            return self._send(302, "", headers=[("Location", "/login")])
        if path in ("/", "/index.html"):
            f = os.path.join(main.OUT, "index.html")
            if not os.path.exists(f):
                return self._send(200, "<h2>No plan yet.</h2><p>Run <code>python main.py</code> first.</p>")
            page = open(f, encoding="utf-8").read()
            if auth.enabled():
                page = page.replace("</body>", '<a href="/logout" style="position:fixed;bottom:14px;right:16px;'
                                    'font:12px system-ui;color:inherit;opacity:.75;background:var(--card);'
                                    'padding:6px 12px;border-radius:999px;border:1px solid var(--line);'
                                    f'text-decoration:none">{user} · log out</a></body>')
            return self._send(200, page)
        if path.startswith("/out/") and path.endswith((".json", ".txt")):
            f = os.path.join(main.OUT, os.path.basename(path))
            if os.path.exists(f):
                return self._send(200, open(f, "rb").read(),
                                  "application/json" if f.endswith(".json") else "text/plain; charset=utf-8")
        self._send(404, "not found")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(min(n, 5_000_000)).decode("utf-8"))
        except ValueError:
            return self._json(400, {"error": "bad JSON"})
        if self.path == "/api/otp/send":
            ok, msg = auth.send_code(body.get("email"))
            return self._json(200 if ok else 400, {"ok": ok, "msg": msg})
        if self.path == "/api/otp/verify":
            token, msg = auth.verify(body.get("email"), body.get("code"))
            if not token:
                return self._json(401, {"ok": False, "msg": msg})
            return self._json(200, {"ok": True}, [("Set-Cookie", COOKIE.format(token, auth.SESSION_TTL))])
        if self.path not in ("/api/message", "/api/upload"):
            return self._send(404, "not found")
        if not self._user():
            return self._json(401, {"error": "please log in"})
        text = (body.get("text") or "").strip()
        if not text:
            return self._json(400, {"error": "empty message"})
        buf = io.StringIO()
        with LOCK, contextlib.redirect_stdout(buf):
            # keep a copy in inbox/ so `python main.py` sees the same history and never repeats it
            os.makedirs(main.INBOX_DIR, exist_ok=True)
            name = re.sub(r"[^\w.-]", "_", os.path.basename(body.get("name") or "")) or "web_message"
            name = time.strftime("%H%M%S_") + (name if name.lower().endswith(".txt") else name + ".txt")
            with open(os.path.join(main.INBOX_DIR, name), "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            st = main.process(text, name)
        self._json(200, {"ok": st is not None, "output": buf.getvalue()})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Hackathon planner UI on http://localhost:{PORT}  (Ctrl+C to stop)")
    print("Login: " + (("email OTP via SMTP" if os.environ.get("SMTP_HOST") else
                        "email OTP, DEMO MODE: no SMTP set, codes are printed here") if auth.enabled() else "off"))
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
