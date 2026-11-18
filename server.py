"""Optional web UI:  python server.py   ->  http://localhost:8000

Shows the same dashboard as out/index.html and adds a box to submit a new message.
A submitted message goes through EXACTLY the same pipeline as `python main.py`
(main.process), so the trace, limits and rejection rules are identical.
Standard library only.
"""
import contextlib
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

LOCK = threading.Lock()
PORT = int(os.environ.get("PORT", "8000"))


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            f = os.path.join(main.OUT, "index.html")
            if not os.path.exists(f):
                return self._send(200, "<h2>No plan yet.</h2><p>Run <code>python main.py</code> first, "
                                       "or paste a whole message pack below.</p>" + FORM)
            return self._send(200, open(f, encoding="utf-8").read())
        if path.startswith("/out/") and path.endswith((".json", ".txt")):
            f = os.path.join(main.OUT, os.path.basename(path))
            if os.path.exists(f):
                return self._send(200, open(f, "rb").read(),
                                  "application/json" if f.endswith(".json") else "text/plain; charset=utf-8")
        self._send(404, "not found")

    def do_POST(self):
        if self.path != "/api/message":
            return self._send(404, "not found")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            text = json.loads(self.rfile.read(n).decode("utf-8")).get("text", "").strip()
        except ValueError:
            return self._send(400, json.dumps({"error": "bad JSON"}), "application/json")
        if not text:
            return self._send(400, json.dumps({"error": "empty message"}), "application/json")
        buf = io.StringIO()
        with LOCK, contextlib.redirect_stdout(buf):
            # keep a copy in the inbox file so `python main.py` sees the same history
            with open(main.INBOX, "a", encoding="utf-8") as fh:
                fh.write("\n\n" + text + "\n")
            st = main.process(text, "web form")
        self._send(200, json.dumps({"ok": st is not None, "output": buf.getvalue()}), "application/json")

    def log_message(self, *a):
        pass


FORM = """<form onsubmit="event.preventDefault();fetch('/api/message',{method:'POST',body:JSON.stringify({text:this.t.value})})
.then(r=>r.json()).then(()=>location.reload())"><textarea name="t" rows="8" cols="90"></textarea><br><button>Run</button></form>"""

if __name__ == "__main__":
    print(f"Hackathon planner UI on http://localhost:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
