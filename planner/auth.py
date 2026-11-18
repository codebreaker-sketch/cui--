"""Email OTP login for the web UI (server.py only; the CLI needs no login).

Flow: enter email -> a 6-digit code is emailed (valid 5 min, 5 tries) -> enter code -> session cookie (8 h).
Email is sent over SMTP when SMTP_HOST/SMTP_USER/SMTP_PASS are set in .env; otherwise (offline demo)
the code is printed in the server's terminal. ALLOWED_EMAILS (comma list) limits who may log in.
Codes and sessions are stored only as SHA-256 hashes in memory.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import time
from email.message import EmailMessage

OTP_TTL, SESSION_TTL, MAX_TRIES = 300, 8 * 3600, 5
_otps, _sessions, _last_sent = {}, {}, {}


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def enabled():
    return os.environ.get("LOGIN", "on").lower() not in ("off", "0", "false", "no")


def allowed(email):
    allow = [e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()]
    return not allow or email in allow


def send_code(email):
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        return False, "Please enter a valid email address."
    if not allowed(email):
        return False, "This email is not allowed to log in."
    if time.time() - _last_sent.get(email, 0) < 30:
        return False, "Please wait 30 seconds before asking for a new code."
    code = f"{secrets.randbelow(1_000_000):06d}"
    _otps[email] = {"h": _h(email + code), "exp": time.time() + OTP_TTL, "tries": 0}
    _last_sent[email] = time.time()
    host, user, pw = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if host and user and pw:
        msg = EmailMessage()
        msg["Subject"] = "Your Hackathon Planner login code"
        msg["From"] = os.environ.get("SMTP_FROM", user)
        msg["To"] = email
        msg.set_content(f"Your login code is {code}. It expires in 5 minutes.")
        try:
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=20) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                tok = base64.b64encode(f"\0{user}\0{pw}".encode()).decode()
                code_, resp = s.docmd("AUTH", "PLAIN " + tok)      # gives Gmail's real answer (smtplib hides it)
                if code_ != 235:
                    raise smtplib.SMTPAuthenticationError(code_, resp)
                s.send_message(msg)
            return True, f"A 6-digit code was sent to {email}. Check your inbox (and spam)."
        except Exception as e:                       # noqa: BLE001
            why = ("the email server rejected SMTP_USER / SMTP_PASS (for Gmail use a valid 16-letter app password)"
                   if isinstance(e, smtplib.SMTPAuthenticationError) else f"{type(e).__name__}")
            print(f"[login] EMAIL FAILED ({why}). Code for {email} is {code}", flush=True)
            return True, f"Email could not be sent: {why}. The code was printed in the server terminal instead."
    print(f"[login] DEMO MODE (no SMTP configured): code for {email} is {code}", flush=True)
    return True, "Demo mode (no email server set): the code is printed in the server terminal."


def verify(email, code):
    email = (email or "").strip().lower()
    rec = _otps.get(email)
    if not rec or time.time() > rec["exp"]:
        return None, "Code expired or not requested. Ask for a new one."
    rec["tries"] += 1
    if rec["tries"] > MAX_TRIES:
        _otps.pop(email, None)
        return None, "Too many wrong tries. Ask for a new code."
    if not hmac.compare_digest(rec["h"], _h(email + (code or "").strip())):
        return None, f"Wrong code ({MAX_TRIES - rec['tries']} tries left)."
    _otps.pop(email, None)
    token = secrets.token_urlsafe(32)
    _sessions[_h(token)] = {"email": email, "exp": time.time() + SESSION_TTL}
    return token, "ok"


def session(cookie_header):
    m = re.search(r"(?:^|;\s*)hp_session=([\w-]+)", cookie_header or "")
    if not m:
        return None
    s = _sessions.get(_h(m.group(1)))
    if not s or time.time() > s["exp"]:
        return None
    return s["email"]


def logout(cookie_header):
    m = re.search(r"(?:^|;\s*)hp_session=([\w-]+)", cookie_header or "")
    if m:
        _sessions.pop(_h(m.group(1)), None)
